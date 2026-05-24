import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('nlp-controller/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_marker = "// ============================================================\n// \U0001f3ad Morph Control Panel UI\n// ============================================================"
next_marker = "// 模型加载后自动检测 morph"

idx_start = content.find(old_marker)
idx_end = content.find(next_marker, idx_start)

print(f"idx_start={idx_start}, idx_end={idx_end}")
if idx_start == -1 or idx_end == -1:
    print("MARKERS NOT FOUND")
    sys.exit(1)

new_code = r"""// ============================================================
// 🎭 Morph Control Panel UI
// ============================================================
let _morphSliderCache = {};  // { morphName: sliderEl }

function detectModelMorphs() {
  const panel = document.getElementById('morph-panel');
  const container = document.getElementById('morph-sliders-container');
  if (!$.model) { panel.style.display = 'none'; return; }

  panel.style.display = 'block';

  // 填充预设表情下拉
  const select = document.getElementById('morph-expr-select');
  select.innerHTML = '<option value="">-- 选择预设表情 --</option>';
  if ($.expressionController) {
    for (const [key, expr] of Object.entries($.expressionController.expressions)) {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = expr.desc;
      select.appendChild(opt);
    }
  }

  // ===== 收集所有 material -> {name, opacity} =====
  const allMaterials = [];
  $.model.traverse(function(child) {
    if (child.isSkinnedMesh) {
      const mList = Array.isArray(child.material) ? child.material : [child.material];
      for (let i = 0; i < mList.length; i++) {
        const m = mList[i];
        if (m && m.name !== undefined) {
          allMaterials.push({ idx: i, name: m.name, mat: m, origOpacity: m.opacity, origTransparent: m.transparent });
        }
      }
    }
  });

  // ===== 辅助：模糊匹配 morph 名 -> material =====
  function matchMaterials(morphName) {
    // 去掉后缀修饰：ON, OFF, +, 数字
    var stripped = morphName.replace(/(ON|OFF|[+＋]\d*|\d+)$/g, '').trim();
    if (!stripped) stripped = morphName;
    
    const results = [];
    const morphChars = new Set(stripped.split(''));
    for (const mi of allMaterials) {
      if (!mi.name) continue;
      const matChars = new Set(mi.name.split(''));
      let common = 0;
      for (const c of morphChars) if (matChars.has(c)) common++;
      const score = common / Math.max(1, Math.min(morphChars.size, matChars.size));
      if (score >= 0.5) {
        results.push({ idx: mi.idx, name: mi.name, mat: mi.mat, origOpacity: mi.origOpacity, score: score });
      }
    }
    results.sort(function(a, b) { return b.score - a.score; });
    return results;
  }

  // ===== 收集所有 morph =====
  // 1. 顶点 morph
  const vertexMorphs = {};
  $.model.traverse(function(child) {
    if (child.isSkinnedMesh && child.morphTargetDictionary) {
      for (const [name, idx] of Object.entries(child.morphTargetDictionary)) {
        if (!(name in vertexMorphs)) {
          vertexMorphs[name] = { mesh: child, index: idx };
        }
      }
    }
  });

  // 2. 材质 morph (MaterialMorphController)
  const materialMorphs = {};
  if ($.materialMorphController && $.materialMorphController.morphMap) {
    for (const [k, v] of Object.entries($.materialMorphController.morphMap)) {
      materialMorphs[v.name] = { id: parseInt(k), type: v.type, materialIndex: v.materialIndex };
    }
  }

  // 3. 动态材质匹配：为每个 morph 找到关联 material
  const dynamicMatMorphs = {};
  for (const name of Object.keys(vertexMorphs)) {
    if (materialMorphs[name]) continue;
    const faceOnly = /^[あいうえおかきくけこなにぬねのはひふへほ]{1,3}$/.test(name);
    if (faceOnly) continue;
    const matches = matchMaterials(name);
    if (matches.length > 0 && matches[0].score >= 0.45) {
      const bestScore = matches[0].score;
      const top = matches.filter(function(m) { return m.score >= bestScore * 0.5; }).slice(0, 5);
      const isOn = name.includes('ON') || name.includes('+');
      const isOff = name.includes('OFF') || name.includes('消');
      dynamicMatMorphs[name] = {
        mats: top.map(function(m) { return { mat: m.mat, origOpacity: m.origOpacity }; }),
        isOn: isOn, isOff: isOff
      };
    }
  }

  const allNames = [].concat(Object.keys(vertexMorphs), Object.keys(materialMorphs));
  if (allNames.length === 0) {
    container.innerHTML = '<div style="font-size:10px; color:var(--text-dim);">未检测到 morph</div>';
    return;
  }

  // 重建滑块
  const nVert = Object.keys(vertexMorphs).length;
  const nMat = Object.keys(materialMorphs).length;
  const nDyn = Object.keys(dynamicMatMorphs).length;
  container.innerHTML = '<div style="font-size:10px; color:var(--text-dim); margin-bottom:2px;">Morph (顶点:' + nVert + ' 固定材质:' + nMat + ' 动态材质:' + nDyn + '):</div>';
  _morphSliderCache = {};

  for (const name of allNames) {
    const vInfo = vertexMorphs[name];
    const mInfo = materialMorphs[name];
    const dInfo = dynamicMatMorphs[name];
    const isDynMat = !!dInfo;
    const isMat = !!mInfo;
    const isVertex = !!vInfo;

    const row = document.createElement('div');
    row.style.cssText = 'display:flex; align-items:center; gap:4px; margin:1px 0;';

    const label = document.createElement('span');
    label.style.cssText = 'font-size:10px; color:var(--text-dim); min-width:70px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;';
    label.textContent = name;
    label.title = name + (isVertex ? ' [顶点]' : '') + (isMat ? ' [材质]' : '') + (isDynMat ? ' [D:' + dInfo.mats.map(function(m){return m.mat.name;}).join(',') + ']' : '');

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.min = 0;
    slider.max = 100;
    slider.value = 0;
    slider.style.cssText = 'flex:1; height:3px; accent-color:' + (isDynMat ? '#ff9800' : (isMat ? '#00bcd4' : 'var(--pink)')) + '; cursor:pointer;';
    slider.dataset.morphName = name;

    slider.addEventListener('input', function () {
      const val = parseInt(this.value) / 100;
      // 顶点 morph
      const vi = vertexMorphs[this.dataset.morphName];
      if (vi && vi.mesh.morphTargetInfluences) {
        vi.mesh.morphTargetInfluences[vi.index] = val;
      }
      // 固定材质 morph
      const mi = materialMorphs[this.dataset.morphName];
      if (mi && $.materialMorphController) {
        $.materialMorphController.setMorph(mi.name, val);
      }
      // 动态材质 morph：直接操作 material opacity
      const di = dynamicMatMorphs[this.dataset.morphName];
      if (di) {
        for (var j = 0; j < di.mats.length; j++) {
          var entry = di.mats[j];
          var mat = entry.mat;
          var orig = entry.origOpacity;
          if (di.isOn) {
            mat.opacity = orig + (1.0 - orig) * val;
          } else if (di.isOff) {
            mat.opacity = orig + (0.0 - orig) * val;
          } else {
            mat.opacity = orig + (1.0 - orig) * val;
          }
          mat.transparent = mat.opacity < 0.99;
          mat.depthWrite = !mat.transparent;
          mat.needsUpdate = true;
        }
      }
      const valSpan = this.nextElementSibling;
      if (valSpan) valSpan.textContent = val.toFixed(2);
    });

    const valSpan = document.createElement('span');
    valSpan.style.cssText = 'font-size:9px; color:' + (isDynMat ? '#ff9800' : (isMat ? '#00bcd4' : 'var(--pink)')) + '; min-width:28px; text-align:right;';
    valSpan.textContent = '0.00';

    row.appendChild(label);
    row.appendChild(slider);
    row.appendChild(valSpan);
    container.appendChild(row);
    _morphSliderCache[name] = slider;
  }
}

"""

content = content[:idx_start] + new_code + content[idx_end:]

with open('nlp-controller/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! New file size:", len(content))
