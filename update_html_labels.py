import re

file_path = 'web_panel/app/templates/simulation.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Update Concurrencia to Quantidade de Agentes Docker
content = content.replace('<label class="form-label fw-bold mb-0"><small>Concorrencia Carga</small></label>',
                          '<label class="form-label fw-bold mb-0"><small>Docker Scalability (Bots)</small></label>')
content = content.replace('id="concurrency" class="form-control form-control-sm" value="200"',
                          'id="concurrency" class="form-control form-control-sm" value="50"')

# Update titles and buttons
content = content.replace('<h6 class="text-secondary"><i class="bi bi-activity"></i> 1. Flood (Stress)',
                          '<h6 class="text-secondary"><i class="bi bi-activity"></i> 1. Botnet Docker (C2)')

content = content.replace('title="Subjuga limites de conexao e RAM (Tecnicas de Random UserAgent, Nginx Bypass e Conexoes Presas)"></i></h6>',
                          'title="Instancia conteineres Alpine para flood e navegacao na subrede isolada"></i></h6>')

content = content.replace('<i class="bi bi-browser-chrome"></i> HTTP Flood (Nginx)',
                          '<i class="bi bi-browser-chrome"></i> Botnet: Alunos (Nginx)')
                          
content = content.replace('<i class="bi bi-database-down"></i> DB Read',
                          '<i class="bi bi-database-down"></i> Bot: Aluno Leitura')
                          
content = content.replace('<i class="bi bi-database-up"></i> DB Write',
                          '<i class="bi bi-database-up"></i> Bot: DDoS / Prof')

# Change Stress Requirements Count string to reflect Botnet Nodes
content = content.replace('<span class="text-light fw-bold">Requisições Stress:</span>',
                          '<span class="text-light fw-bold">Tráfego Agentes (Botnet):</span>')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Modificados front ends")
