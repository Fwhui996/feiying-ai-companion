import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('nlp-controller/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '星穹' in line:
        print(f'{i+1}: {line.strip()[:150]}')
