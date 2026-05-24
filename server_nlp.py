# -*- coding: utf-8 -*-
"""
NLP MMD Controller + LLM API Server
启动: python server_nlp.py [端口号]
"""
import os, sys, json, re, hashlib, base64, socket, uuid, zipfile, shutil, tempfile
from datetime import datetime

# ── Windows 编码修复 ──
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from flask import Flask, send_from_directory, request, jsonify

ROOT = os.path.dirname(os.path.abspath(__file__))
CHARACTER_DIR = os.path.join(ROOT, 'nlp-controller', 'character')
MEMORY_DIR = os.path.join(CHARACTER_DIR, 'memory')
CONFIG_FILE = os.path.join(ROOT, 'llm_config.json')

app = Flask(__name__)


# ═══ 加密 ═══
def _machine_key():
    raw = f"{socket.gethostname()}-{uuid.getnode()}-mmd-fengyun-salt"
    h = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(h[:32])

def encrypt_api_key(plain):
    if not plain: return ''
    key = _machine_key()
    key_bytes = key * ((len(plain) // len(key)) + 1)
    encrypted = bytes(p ^ k for p, k in zip(plain.encode(), key_bytes))
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_api_key(encrypted):
    if not encrypted: return ''
    try:
        key = _machine_key()
        data = base64.urlsafe_b64decode(encrypted.encode())
        key_bytes = key * ((len(data) // len(key)) + 1)
        return bytes(d ^ k for d, k in zip(data, key_bytes)).decode()
    except: return ''

# ═══ 记忆 ═══
def read_file_safe(path):
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f: return f.read()
    except: pass
    return ''

def write_file_safe(path, content):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f: f.write(content)
    except: pass

def build_system_prompt():
    soul = read_file_safe(os.path.join(CHARACTER_DIR, 'SOUL.md'))
    profile = read_file_safe(os.path.join(CHARACTER_DIR, 'PROFILE.md'))
    today = datetime.now().strftime('%Y-%m-%d')
    daily = read_file_safe(os.path.join(MEMORY_DIR, f'{today}.md'))
    return f"""{soul}

{profile}

今日记录：
{daily}

---
# 控制指令（放在回复末尾，用户看不到）

## 表情标签
格式：[expression:表情名]
可用：happy, sad, angry, surprised, shy, cute, fear, disgust, neutral, wink, laugh, smirk, tearful

## 动作标签（只需要贴标签，不用写代码！）
格式：[action:动作名]

可用动作名：
wave(挥手) wave_both(双手挥) bow(鞠躬) jump(跳跃) dance(跳舞)
happy_spin(开心转圈) angry_stomp(生气跺脚) sad_droop(失落低头)
shy_fidget(害羞扭动) surprise_jump(惊讶跳起) celebrate(庆祝)
think(思考歪头) blow_kiss(飞吻) point(指向) peek(偷看)
stretch(伸懒腰) nudge(戳戳) shrug(耸肩) idle(恢复站立)

## 规则
1. 根据对话情绪选择合适的表情和动作标签
2. 标签放在回复最后一行，前面可以有文字
3. 纯聊天（无情绪波动）不加标签
4. 回复正文不要提及标签
5. 用自然的中文回复，加颜文字

## 示例
用户：「今天好开心！」
回复：是呢是呢～绯英也觉得今天特别棒！(〃▽〃)✨
[expression:happy]
[action:happy_spin]

用户：「气死我了！！」
回复：呜哇主人别生气！(´；ω；｀) 绯英帮你踩踩地板解气！
[expression:angry]
[action:angry_stomp]

用户：「给我跳个舞」
回复：来啦来啦～看我的！💃
[expression:happy]
[action:dance]

用户：「1+1等于几」
回复：当然是2啦～主人考我数学？(｀・ω・´)
（纯聊天，不加标签）
"""

def update_memory(user_msg, ai_reply):
    today = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(MEMORY_DIR, f'{today}.md')
    existing = read_file_safe(path)
    if not existing or '# ' not in existing:
        existing = f'# {today} 记忆\n\n## 今日对话\n'
    t = datetime.now().strftime('%H:%M')
    new_entry = f"\n- [{t}] 主人: {user_msg[:100]}\n- [{t}] 绯英: {ai_reply[:100]}\n"
    write_file_safe(path, existing.rstrip() + new_entry)

# ═══ LLM ═══
def get_llm_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return {'provider':'ollama','base_url':'http://localhost:11434/v1','model':'qwen2.5:7b','encrypted_api_key':'','active_provider':'ollama'}

def save_llm_config(config):
    if config.get('api_key'):
        config['encrypted_api_key'] = encrypt_api_key(config['api_key'])
    config.pop('api_key', None)
    os.makedirs(os.path.dirname(CONFIG_FILE) if os.path.dirname(CONFIG_FILE) else '.', exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def get_active_llm_params():
    config = get_llm_config()
    provider = config.get('active_provider', 'ollama')
    if provider == 'ollama':
        return {'base_url': config.get('base_url','http://localhost:11434/v1'), 'api_key': 'ollama', 'model': config.get('model','qwen2.5:7b')}
    elif provider == 'deepseek':
        return {'base_url': 'https://api.deepseek.com', 'api_key': decrypt_api_key(config.get('encrypted_api_key','')), 'model': config.get('model','deepseek-chat')}
    else:
        return {'base_url': config.get('base_url',''), 'api_key': decrypt_api_key(config.get('encrypted_api_key','')), 'model': config.get('model','')}

def call_llm(messages):
    import urllib.request, urllib.error
    params = get_active_llm_params()
    payload = json.dumps({'model':params['model'],'messages':messages,'temperature':0.9,'max_tokens':2048}).encode()
    req = urllib.request.Request(f"{params['base_url'].rstrip('/')}/chat/completions", data=payload, method='POST')
    req.add_header('Content-Type','application/json')
    req.add_header('Authorization',f"Bearer {params['api_key']}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'LLM API HTTP {e.code}: {e.read().decode(errors="replace")[:300]}')
    except Exception as e:
        raise RuntimeError(f'LLM API: {e}')

def test_llm_connection(base_url, api_key, model):
    import urllib.request
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = json.dumps({'model':model,'messages':[{'role':'user','content':'OK'}],'max_tokens':5}).encode()
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type','application/json')
    req.add_header('Authorization',f"Bearer {api_key}")
    start = datetime.now()
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
        return {'ok':True,'model':data.get('model',model),'latency_ms':round((datetime.now()-start).total_seconds()*1000)}

def parse_llm_response(text):
    result = {'reply':text,'expression':None,'action':None,'mplCode':None}
    # 提取 [expression:xxx]
    m = re.search(r'\[expression\s*:\s*(\w+)\]', text, re.IGNORECASE)
    if m:
        result['expression'] = m.group(1).lower()
        result['reply'] = result['reply'].replace(m.group(0),'').strip()
    # 提取 [action:xxx]（新增）
    m = re.search(r'\[action\s*:\s*(\w+)\]', text, re.IGNORECASE)
    if m:
        result['action'] = m.group(1).lower()
        result['reply'] = result['reply'].replace(m.group(0),'').strip()
    # 提取 ```mpl ... ```
    m = re.search(r'```(?:mpl|MPL)\s*\n(.*?)```', text, re.DOTALL)
    if not m:
        m = re.search(r'```(?:mpl|MPL)\s*\n(.+)', text, re.DOTALL)
    if not m:
        m = re.search(r'(@pose\s+\w+\s*\{.*?\}\s*main\s*\{.*?\})', text, re.DOTALL)
    if m:
        result['mplCode'] = m.group(1).strip()
        result['reply'] = result['reply'].replace(m.group(0),'').strip()
    return result

# ═══ 动作模板库（WASM 编译器格式，英文骨骼名）═══
ACTION_TEMPLATES = {
    'wave': (
        '@pose wave_pose {\n'
        '    shoulder_l turn right 40;\n'
        '    arm_l bend forward -30;\n'
        '    elbow_l bend forward 120;\n'
        '    wrist_l bend forward -30;\n'
        '}\n'
        'main {\n'
        '    wave_pose;\n'
        '}'
    ),
    'wave_both': (
        '@pose wave_both_pose {\n'
        '    shoulder_l turn right 40;\n'
        '    arm_l bend forward -30;\n'
        '    elbow_l bend forward 120;\n'
        '    wrist_l bend forward -30;\n'
        '    shoulder_r turn left 40;\n'
        '    arm_r bend forward -30;\n'
        '    elbow_r bend forward 120;\n'
        '    wrist_r bend forward -30;\n'
        '}\n'
        'main {\n'
        '    wave_both_pose;\n'
        '}'
    ),
    'bow': (
        '@pose bow_pose {\n'
        '    upper_body bend forward 60;\n'
        '    head bend forward 40;\n'
        '    arm_l bend forward 10;\n'
        '    arm_r bend forward 10;\n'
        '}\n'
        'main {\n'
        '    bow_pose;\n'
        '}'
    ),
    'jump': (
        '@pose jump_pose {\n'
        '    leg_l bend forward -20;\n'
        '    leg_r bend forward -20;\n'
        '    arm_l bend forward -40;\n'
        '    arm_r bend forward -40;\n'
        '    elbow_l bend forward 50;\n'
        '    elbow_r bend forward 50;\n'
        '}\n'
        'main {\n'
        '    jump_pose;\n'
        '}'
    ),
    'dance': (
        '@pose p1 {\n'
        '    shoulder_l turn right 25;\n'
        '    elbow_l bend forward 90;\n'
        '    elbow_r bend forward 70;\n'
        '    leg_l turn left 10;\n'
        '}\n'
        '@pose p2 {\n'
        '    elbow_l bend forward 130;\n'
        '    elbow_r bend forward 40;\n'
        '    leg_r turn right 10;\n'
        '    head turn left 5;\n'
        '}\n'
        '@pose p3 {\n'
        '    arm_l bend forward -20;\n'
        '    arm_r bend forward 20;\n'
        '    elbow_l bend forward 60;\n'
        '    leg_l turn left 8;\n'
        '}\n'
        '@pose p4 {\n'
        '    elbow_l bend forward 100;\n'
        '    arm_r bend forward -15;\n'
        '    leg_r turn right 8;\n'
        '    head turn right 5;\n'
        '}\n'
        '@animation dance_anim {\n'
        '    0: p1;\n'
        '    0.5: p2;\n'
        '    1: p3;\n'
        '    1.5: p4;\n'
        '    2: p1;\n'
        '    2.5: p2;\n'
        '    3: p3;\n'
        '}\n'
        'main {\n'
        '    dance_anim;\n'
        '}'
    ),
    'happy_spin': (
        '@pose spin_pose {\n'
        '    upper_body turn right 30;\n'
        '    arm_r bend forward 60;\n'
        '    arm_l bend forward -50;\n'
        '    leg_r turn right 15;\n'
        '    head turn right 10;\n'
        '}\n'
        'main {\n'
        '    spin_pose;\n'
        '}'
    ),
    'angry_stomp': (
        '@pose stomp_pose {\n'
        '    leg_r bend forward -25;\n'
        '    leg_l bend forward -25;\n'
        '    arm_l bend forward -30;\n'
        '    arm_r bend forward -30;\n'
        '    elbow_l bend forward 80;\n'
        '    elbow_r bend forward 80;\n'
        '}\n'
        'main {\n'
        '    stomp_pose;\n'
        '}'
    ),
    'sad_droop': (
        '@pose droop_pose {\n'
        '    upper_body bend forward 25;\n'
        '    head bend forward 20;\n'
        '    arm_l bend forward 15;\n'
        '    arm_r bend forward 15;\n'
        '}\n'
        'main {\n'
        '    droop_pose;\n'
        '}'
    ),
    'shy_fidget': (
        '@pose shy_pose {\n'
        '    upper_body turn left 10;\n'
        '    upper_body bend forward 8;\n'
        '    head bend forward 15;\n'
        '    head turn left 10;\n'
        '    arm_l bend forward 10;\n'
        '    arm_r bend forward -15;\n'
        '}\n'
        'main {\n'
        '    shy_pose;\n'
        '}'
    ),
    'surprise_jump': (
        '@pose surprise_pose {\n'
        '    upper_body bend backward 10;\n'
        '    arm_l bend forward -30;\n'
        '    arm_r bend forward -30;\n'
        '    leg_l bend forward -15;\n'
        '    leg_r bend forward -15;\n'
        '    head bend backward 10;\n'
        '}\n'
        'main {\n'
        '    surprise_pose;\n'
        '}'
    ),
    'celebrate': (
        '@pose celebrate_pose {\n'
        '    arm_r bend forward 100;\n'
        '    arm_l bend forward 100;\n'
        '    elbow_r bend forward 50;\n'
        '    elbow_l bend forward 50;\n'
        '    leg_r bend forward -15;\n'
        '    leg_l bend forward -15;\n'
        '}\n'
        'main {\n'
        '    celebrate_pose;\n'
        '}'
    ),
    'think': (
        '@pose think_pose {\n'
        '    head turn left 15;\n'
        '    head bend forward 8;\n'
        '    arm_r bend forward 20;\n'
        '    elbow_r bend forward 60;\n'
        '    wrist_r bend forward -10;\n'
        '}\n'
        'main {\n'
        '    think_pose;\n'
        '}'
    ),
    'blow_kiss': (
        '@pose kiss_pose {\n'
        '    arm_r bend forward 50;\n'
        '    elbow_r bend forward 80;\n'
        '    head bend forward 8;\n'
        '    wrist_r bend forward -20;\n'
        '}\n'
        'main {\n'
        '    kiss_pose;\n'
        '}'
    ),
    'point': (
        '@pose point_pose {\n'
        '    arm_r bend forward 70;\n'
        '    elbow_r bend forward 10;\n'
        '    shoulder_r turn right 25;\n'
        '    upper_body turn right 10;\n'
        '}\n'
        'main {\n'
        '    point_pose;\n'
        '}'
    ),
    'peek': (
        '@pose peek_pose {\n'
        '    upper_body bend forward 20;\n'
        '    head turn right 15;\n'
        '    upper_body sway right 10;\n'
        '}\n'
        'main {\n'
        '    peek_pose;\n'
        '}'
    ),
    'stretch': (
        '@pose stretch_pose {\n'
        '    arm_r bend forward 120;\n'
        '    arm_l bend forward 120;\n'
        '    elbow_r bend forward 30;\n'
        '    elbow_l bend forward 30;\n'
        '    upper_body bend backward 10;\n'
        '}\n'
        'main {\n'
        '    stretch_pose;\n'
        '}'
    ),
    'nudge': (
        '@pose nudge_pose {\n'
        '    arm_r bend forward 30;\n'
        '    elbow_r bend forward 15;\n'
        '    upper_body sway right 10;\n'
        '}\n'
        'main {\n'
        '    nudge_pose;\n'
        '}'
    ),
    'shrug': (
        '@pose shrug_pose {\n'
        '    arm_l bend forward -30;\n'
        '    arm_r bend forward -30;\n'
        '    elbow_l bend forward 60;\n'
        '    elbow_r bend forward 60;\n'
        '}\n'
        'main {\n'
        '    shrug_pose;\n'
        '}'
    ),
    'idle': (
        '@pose idle_pose {\n'
        '}\n'
        'main {\n'
        '    idle_pose;\n'
        '}'
    ),
    'greet': (
        '@pose greet_pose {\n'
        '    upper_body bend forward 35;\n'
        '}\n'
        'main {\n'
        '    greet_pose;\n'
        '}'
    ),
}

ACTION_ALIASES = {
    'twirl':'happy_spin','spin':'happy_spin','turn':'happy_spin','rotate':'happy_spin',
    'stomp':'angry_stomp','kick':'angry_stomp','stamp':'angry_stomp',
    'greet':'bow','hello':'wave','hi':'wave','bye':'wave','goodbye':'wave',
    'nod':'bow','cry':'sad_droop','sigh':'sad_droop','droop':'sad_droop',
    'surprised':'surprise_jump','shock':'surprise_jump','wow':'surprise_jump',
    'laugh':'celebrate','cheer':'celebrate','yay':'celebrate',
    'shy':'shy_fidget','embarrassed':'shy_fidget','blush':'shy_fidget',
    'kiss':'blow_kiss','flying_kiss':'blow_kiss',
    'thinking':'think','ponder':'think','hmm':'think',
    'yawn':'stretch','stretching':'stretch',
    'shrug':'shrug','meh':'shrug',
    'push':'nudge','poke':'nudge',
}

SENTIMENT_FALLBACK = [
    (['开心','高兴','哈哈','太好','棒','耶','庆祝','恭喜','喜','乐','嘿嘿','嘻嘻'], 'happy_spin'),
    (['难过','伤心','哭','泪','失落','叹气','唉','悲','忧郁','沮丧'], 'sad_droop'),
    (['生气','愤怒','气死','怒','火大','烦','暴躁','可恶','混蛋'], 'angry_stomp'),
    (['害羞','不好意思','羞','脸红','尴尬','难为情'], 'shy_fidget'),
    (['惊讶','天哪','不会吧','震惊','吓','哇','什么','真的假的'], 'surprise_jump'),
    (['再见','拜拜','回头见','下次','晚安','拜','88'], 'wave'),
    (['谢谢','感谢','感恩','辛苦','多谢'], 'bow'),
    (['加油','努力','冲','fight','干巴爹'], 'celebrate'),
    (['跳舞','舞','蹦','跳个'], 'dance'),
    (['挥手','招手','打招呼','hello','hi'], 'wave'),
]

def fuzzy_match(word, candidates):
    word = word.lower()
    best, best_score = None, 0
    for c in candidates:
        common = len(set(word) & set(c))
        score = common / max(len(word), len(c))
        if score > best_score and score > 0.35:
            best, best_score = c, score
    return best

def resolve_action(parsed, reply_text):
    """三级解析：标签 → 别名 → 情感兜底 → 纯聊天"""
    reply = (reply_text or '').lower()
    
    # 1: LLM 打了 [action:xxx]
    if parsed.get('action'):
        tag = parsed['action'].lower().strip()
        if tag in ACTION_TEMPLATES: return tag
        if tag in ACTION_ALIASES: return ACTION_ALIASES[tag]
        best = fuzzy_match(tag, list(ACTION_TEMPLATES.keys()))
        if best: return best
    
    # 2: 回复文字情感分析
    for keywords, action in SENTIMENT_FALLBACK:
        if any(kw in reply for kw in keywords):
            return action
    
    # 3: 纯聊天
    return None

# ═══ API 路由 ═══

@app.route('/api/llm/config', methods=['GET','POST'])
def api_config():
    if request.method == 'POST':
        try:
            cfg = request.get_json(force=True) or {}
            save_llm_config(cfg)
            return jsonify({'ok':True})
        except Exception as e:
            return jsonify({'ok':False,'error':str(e)}), 500
    cfg = get_llm_config()
    cfg['api_key'] = decrypt_api_key(cfg.get('encrypted_api_key',''))
    cfg.pop('encrypted_api_key',None)
    return jsonify(cfg)

@app.route('/api/llm/test', methods=['POST'])
def api_test():
    d = request.get_json(force=True) or {}
    provider = d.get('provider','ollama')
    base_url = d.get('base_url','')
    api_key = d.get('api_key','')
    model = d.get('model','')
    if provider == 'ollama': base_url = base_url or 'http://localhost:11434/v1'; api_key = 'ollama'
    elif provider == 'deepseek': base_url = 'https://api.deepseek.com'
    try:
        r = test_llm_connection(base_url, api_key, model)
        return jsonify(r)
    except Exception as e:
        return jsonify({'ok':False,'error':str(e)})

@app.route('/api/llm/chat', methods=['POST'])
def api_chat():
    try:
        d = request.get_json(force=True) or {}
        user_msg = d.get('message','').strip()
        history = d.get('history',[])
        if not user_msg: return jsonify({'error':'消息为空'}), 400
        messages = [{'role':'system','content':build_system_prompt()}]
        for h in history[-20:]:
            messages.append({'role':h.get('role','user'),'content':h.get('content','')})
        messages.append({'role':'user','content':user_msg})
        raw = call_llm(messages)
        print(f'\n[LLM RAW] ({len(raw)} chars):\n{raw[:500]}\n')
        parsed = parse_llm_response(raw)
        
        # 动作解析：三级 → 模板 → 返回 mplCode 给前端 WASM 编译
        action_name = resolve_action(parsed, parsed['reply'])
        mpl_code = None
        if action_name and action_name in ACTION_TEMPLATES:
            print(f'[LLM ACTION] resolved={action_name}')
            mpl_code = ACTION_TEMPLATES[action_name]
        elif parsed['mplCode']:
            print(f'[LLM ACTION] using raw MPL from LLM')
            mpl_code = parsed['mplCode']
        else:
            print(f'[LLM ACTION] no action (pure chat)')
        
        print(f'[LLM PARSED] expr={parsed["expression"]} action={action_name} mpl={bool(mpl_code)}')
        try: update_memory(user_msg, parsed['reply'])
        except: pass
        return jsonify({
            'reply': parsed['reply'],
            'expression': parsed['expression'],
            'action': action_name,
            'mplCode': mpl_code
        })
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/api/llm/memory', methods=['GET'])
def api_memory_get():
    t = request.args.get('type','soul')
    m = {'soul':os.path.join(CHARACTER_DIR,'SOUL.md'),'profile':os.path.join(CHARACTER_DIR,'PROFILE.md'),'memory':os.path.join(CHARACTER_DIR,'MEMORY.md'),'daily':os.path.join(MEMORY_DIR,f"{datetime.now().strftime('%Y-%m-%d')}.md")}
    p = m.get(t)
    return jsonify({'content':read_file_safe(p)}) if p else (jsonify({'error':'unknown type'}),400)

@app.route('/api/llm/memory', methods=['POST'])
def api_memory_post():
    d = request.get_json(force=True) or {}
    t = d.get('type',''); c = d.get('content','')
    m = {'profile':os.path.join(CHARACTER_DIR,'PROFILE.md'),'memory':os.path.join(CHARACTER_DIR,'MEMORY.md')}
    p = m.get(t)
    if p: write_file_safe(p,c); return jsonify({'ok':True})
    return jsonify({'error':'unknown type'}),400

# ═══ 静态文件 ═══
@app.route('/nlp-controller/')
def serve_nlp_index():
    return send_from_directory('nlp-controller', 'index.html')

@app.route('/nlp-controller/<path:subpath>')
def serve_nlp(subpath):
    return send_from_directory('nlp-controller', subpath)

@app.route('/nlp-controller-r175/')
def serve_nlp_r175_index():
    return send_from_directory('nlp-controller-r175', 'index.html')

@app.route('/nlp-controller-r175/<path:subpath>')
def serve_nlp_r175(subpath):
    return send_from_directory('nlp-controller-r175', subpath)

@app.route('/nlp-controller-r170/')
def serve_nlp_r170_index():
    return send_from_directory('nlp-controller-r170', 'index.html')

@app.route('/nlp-controller-r170/<path:subpath>')
def serve_nlp_r170(subpath):
    return send_from_directory('nlp-controller-r170', subpath)

@app.route('/nlp-controller-r171/')
def serve_nlp_r171_index():
    return send_from_directory('nlp-controller-r171', 'index.html')

@app.route('/nlp-controller-r171/<path:subpath>')
def serve_nlp_r171(subpath):
    return send_from_directory('nlp-controller-r171', subpath)

@app.route('/nlp-controller-r164/')
def serve_nlp_r164_index():
    return send_from_directory('nlp-controller-r164', 'index.html')

@app.route('/nlp-controller-r164/<path:subpath>')
def serve_nlp_r164(subpath):
    return send_from_directory('nlp-controller-r164', subpath)

@app.route('/nlp-controller-r146/')
def serve_nlp_r146_index():
    return send_from_directory('nlp-controller-r146', 'index.html')

@app.route('/nlp-controller-r146/<path:subpath>')
def serve_nlp_r146(subpath):
    return send_from_directory('nlp-controller-r146', subpath)

@app.route('/js/<path:path>')
def serve_js(path):
    return send_from_directory('js', path)

@app.route('/assets/<path:path>')
def serve_assets(path):
    return send_from_directory('assets', path)

@app.route('/')
def serve_main():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    full = os.path.join(ROOT, path)
    if os.path.isfile(full): return send_from_directory(ROOT, path)
    return send_from_directory('.', 'index.html')

# ═══ 模型列表 ═══
MODEL_DIR = os.path.join(ROOT, 'assets', 'mmd_model')

@app.route('/api/models')
def list_models():
    models = []
    if os.path.isdir(MODEL_DIR):
        for name in sorted(os.listdir(MODEL_DIR)):
            d = os.path.join(MODEL_DIR, name)
            if not os.path.isdir(d): continue
            pmx = os.path.join(d, f'{name}.pmx')
            if os.path.isfile(pmx):
                models.append({'name': name, 'path': f'../assets/mmd_model/{name}/{name}.pmx'})
    return jsonify(models)

@app.route('/api/models/upload', methods=['POST'])
def upload_model_zip():
    """上传 ZIP 压缩包，自动解压到 assets/mmd_model/ 下"""
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': '未选择文件'}), 400
    
    f = request.files['file']
    if not f.filename or not f.filename.lower().endswith('.zip'):
        return jsonify({'ok': False, 'error': '只支持 .zip 文件'}), 400
    
    def fix_zip_encoding(path):
        """修复 ZIP 中文文件名：CP437→GBK"""
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files + dirs:
                old = os.path.join(root, name)
                try:
                    fixed = name.encode('cp437').decode('gbk', errors='ignore')
                    if fixed != name:
                        new = os.path.join(root, fixed)
                        if not os.path.exists(new):
                            os.rename(old, new)
                except Exception:
                    pass
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zf = zipfile.ZipFile(f, 'r')
            zf.extractall(tmpdir)
            
            # 修复中文文件名
            fix_zip_encoding(tmpdir)
            
            # 找 PMX 文件
            pmx_path = None
            for root, dirs, files in os.walk(tmpdir):
                for fn in files:
                    if fn.lower().endswith('.pmx'):
                        pmx_path = os.path.join(root, fn)
                        break
                if pmx_path: break
            
            if not pmx_path:
                return jsonify({'ok': False, 'error': '压缩包内未找到 .pmx 文件'}), 400
            
            # 清理 Mac 垃圾
            for root, dirs, files in os.walk(tmpdir, topdown=False):
                for d in dirs:
                    if d == '__MACOSX' or d.startswith('._'):
                        shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                for fn in files:
                    if fn.startswith('._') or fn == '.DS_Store':
                        try: os.remove(os.path.join(root, fn))
                        except: pass
            
            # 模型名 = PMX 文件名去掉扩展名
            model_name = os.path.splitext(os.path.basename(pmx_path))[0]
            model_name = re.sub(r'[\\/:*?"<>|]', '_', model_name).strip()
            
            target_dir = os.path.join(MODEL_DIR, model_name)
            if os.path.exists(target_dir):
                i = 2
                while os.path.exists(f'{target_dir}_{i}'):
                    i += 1
                model_name = f'{model_name}_{i}'
                target_dir = os.path.join(MODEL_DIR, model_name)
            
            # 确定源目录：如果 PMX 在一级子目录里，把子目录内容提升到目标根
            pmx_dir = os.path.dirname(pmx_path)
            if pmx_dir == tmpdir:
                src_dir = tmpdir
            else:
                src_dir = pmx_dir
            
            # 拷贝源目录内容到目标目录
            os.makedirs(target_dir, exist_ok=True)
            for item in os.listdir(src_dir):
                s = os.path.join(src_dir, item)
                d = os.path.join(target_dir, item)
                if item == '__MACOSX' or item.startswith('._'): continue
                if os.path.isdir(s):
                    if not os.path.exists(d):
                        shutil.copytree(s, d, ignore=lambda _d, files: [f for f in files if f.startswith('._')])
                else:
                    shutil.copy2(s, d)
            
            # 如果 src_dir != tmpdir，也把 tmpdir 根的非目录非 PMX 文件拷过去（说明档等）
            if src_dir != tmpdir:
                for item in os.listdir(tmpdir):
                    s = os.path.join(tmpdir, item)
                    d = os.path.join(target_dir, item)
                    if os.path.isfile(s) and not item.startswith('._') and not os.path.exists(d):
                        shutil.copy2(s, d)
            
            # 确保 PMX 在根目录且名为 模型名.pmx
            final_pmx = os.path.join(target_dir, f'{model_name}.pmx')
            if not os.path.isfile(final_pmx):
                for root, dirs, files in os.walk(target_dir):
                    for fn in files:
                        if fn.lower().endswith('.pmx') and not fn.startswith('._'):
                            actual = os.path.join(root, fn)
                            if actual != final_pmx:
                                shutil.move(actual, final_pmx)
                            break
                    if os.path.isfile(final_pmx): break
            
            print(f'[MODEL] 导入成功: {model_name}')
            
            return jsonify({
                'ok': True,
                'name': model_name,
                'path': f'../assets/mmd_model/{model_name}/{model_name}.pmx'
            })
            
    except zipfile.BadZipFile:
        return jsonify({'ok': False, 'error': '不是有效的 ZIP 文件'}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

# ═══ 灯光配置存取 ═══
LIGHT_CONFIG_DIR = os.path.join(ROOT, 'light_configs')
os.makedirs(LIGHT_CONFIG_DIR, exist_ok=True)

@app.route('/api/light-config/list')
def list_light_configs():
    files = []
    for f in os.listdir(LIGHT_CONFIG_DIR):
        if f.endswith('.json'):
            files.append(f.replace('.json', ''))
    return jsonify(sorted(files))

@app.route('/api/light-config/save', methods=['POST'])
def save_light_config():
    name = request.json.get('name', 'default')
    data = request.json.get('data', '{}')
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
    path = os.path.join(LIGHT_CONFIG_DIR, f'{safe_name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True, 'name': safe_name})

@app.route('/api/light-config/load')
def load_light_config():
    name = request.args.get('name', 'default')
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
    path = os.path.join(LIGHT_CONFIG_DIR, f'{safe_name}.json')
    if not os.path.exists(path):
        return jsonify({'ok': False, 'error': f'配置 "{name}" 不存在'})
    with open(path, 'r', encoding='utf-8') as f:
        return jsonify({'ok': True, 'data': f.read()})

@app.route('/api/light-config/delete', methods=['POST'])
def delete_light_config():
    name = request.json.get('name', '')
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
    path = os.path.join(LIGHT_CONFIG_DIR, f'{safe_name}.json')
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'not found'})

if __name__ == '__main__':
    user_port = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    if user_port:
        port = user_port
    else:
        port = 8887
        for p in range(port, port+100):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', p)) != 0:
                    port = p
                    break
    
    print('=' * 50)
    print(' NLP MMD Controller + LLM')
    print('=' * 50)
    print(f' URL: http://localhost:{port}/nlp-controller/')
    print('=' * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
