with open('web_panel/app/templates/simulation.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('\"\"', '\"')

with open('web_panel/app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(text)
