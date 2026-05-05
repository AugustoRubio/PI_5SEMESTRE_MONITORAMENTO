with open('web_panel/app/templates/base.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('Simulação de Uso DB', 'Simulação & Estresse')

with open('web_panel/app/templates/base.html', 'w', encoding='utf-8') as f:
    f.write(text)
