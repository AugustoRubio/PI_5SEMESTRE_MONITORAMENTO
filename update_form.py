import sys
with open('web_panel/app/templates/simulation.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("document.getElementById('simForm').addEventListener('submit', async (e) => {", 
"document.getElementById('btnStart').addEventListener('click', async (e) => {")

content = content.replace('<button type="submit" class="btn btn-success" id="btnStart"', '<button type="button" class="btn btn-success" id="btnStart"')

# Removing required from forms just in case the browser intercept is failing.
content = content.replace('required>', '>')
content = content.replace('<form id="simForm">', '<form id="simForm" onsubmit="event.preventDefault(); return false;">')

with open('web_panel/app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated simForm')
