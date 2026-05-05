import sys
with open('web_panel/app/templates/simulation.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('<span class="text-muted">Aguardando', '<span class="text-secondary fw-bold">Aguardando')

with open('web_panel/app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated span!')
