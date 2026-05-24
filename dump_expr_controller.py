import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('nlp-controller/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Print ExpressionController class
in_class = False
brace_depth = 0
for i, line in enumerate(lines):
    if 'class ExpressionController' in line:
        in_class = True
    if in_class:
        print(f'{i+1}: {line}', end='')
        brace_depth += line.count('{') - line.count('}')
        if brace_depth <= 0 and i > 750:
            print(f'--- end at {i+1} ---')
            break
