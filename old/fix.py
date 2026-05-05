import sys
with open('web_panel/app/templates/simulation.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('bg-dark text-light', 'bg-light border text-dark shadow-sm')
content = content.replace('let classColors = "html-text-success";', 'let classColors = "text-secondary";')
content = content.replace('classColors = "text-info";', 'classColors = "text-primary fw-bold";')
content = content.replace('classColors = "text-success";', 'classColors = "text-success fw-bold";')
content = content.replace('classColors = "text-danger";', 'classColors = "text-danger fw-bold";')
content = content.replace('} aatch (error) {', '} catch (error) {')

with open('web_panel/app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated File!')
