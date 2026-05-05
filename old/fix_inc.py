import sys
with open('web_panel/app/templates/simulation.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("includes('text-muted')", "includes('text-secondary')")

with open('web_panel/app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated include!')
