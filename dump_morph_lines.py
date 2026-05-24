import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('nlp-controller/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print(f'Total lines: {len(lines)}')
count = 0
for i, line in enumerate(lines):
    lower = line.lower()
    if 'morph' in lower or 'expression' in lower:
        print(f'{i+1}: {line.strip()[:200]}')
        count += 1
        if count >= 20:
            break
