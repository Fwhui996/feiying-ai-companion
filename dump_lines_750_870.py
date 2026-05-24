import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('nlp-controller/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(750, 870):
    print(f'{i+1}: {lines[i]}', end='')
