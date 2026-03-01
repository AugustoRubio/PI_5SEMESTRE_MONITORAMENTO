# -*- coding: utf-8 -*-
with open('app/templates/simulation.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Modificar valor default do HOST e USER, sem alterar o resto da estetica.
text = re.sub(r'<input\s+type="text"\s+id="simDbHost"[^>]*>', '<input type="text" id="simDbHost" class="form-control" placeholder="10.10.100.4" value="10.10.100.4">', text)
text = re.sub(r'<input\s+type="text"\s+id="simDbUser"[^>]*>', '<input type="text" id="simDbUser" class="form-control" placeholder="admin" value="intranet_user">', text)

# Inserir botão de Limpar Dados
btn_markup = '''
                    <button class="btn btn-warning" onclick="clearSimData()">
                        <i class="fas fa-trash"></i> Limpar Dados [SIM]
                    </button>'''

if 'clearSimData()' not in text:
    text = text.replace(' <button class="btn btn-danger" onclick="stopSimulation()">Parar</button>',
                        ' <button class="btn btn-danger" onclick="stopSimulation()">Parar</button> ' + btn_markup)
    
# Inserir o script JS clearSimData com os Auth Headers em todas as requisicoes
js_script = '''
        function clearSimData() {
            if(!confirm("Atenção: Isso apagará apenas os registros que possuem a tag [SIM] do banco de dados. Deseja continuar?")) return;
            
            showSimToast("Iniciando limpeza dos dados de simulação...", "info");
            
            const config = {
                db_host: document.getElementById('simDbHost').value,
                db_port: document.getElementById('simDbPort').value,
                db_user: document.getElementById('simDbUser').value,
                db_pass: document.getElementById('simDbPass').value,
                db_name: document.getElementById('simDbName').value,
                profile: document.getElementById('simProfile').value,
                duration: 0
            };

            const token = localStorage.getItem("token");

            fetch('/api/simulation/clear_simulated_data', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify(config)
            })
            .then(res => res.json())
            .then(data => {
                if(data.message) {
                    showSimToast(data.message, "success");
                    addLogLine("<< LIMPEZA >> " + data.message, "text-warning");
                } else if(data.detail) {
                     showSimToast("Erro: " + data.detail, "danger");
                }
            })
            .catch(err => {
                showSimToast("Falha na requisição de limpeza", "danger");
            });
        }
'''

if 'function clearSimData' not in text:
    text = text.replace('</script>', js_script + '</script>')

# Adicionar Auth header no start
text = text.replace(
    "headers: { 'Content-Type': 'application/json' },",
    "headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + localStorage.getItem('token') },"
)

# Adicionar Auth header no stop e status
text = text.replace(
    "fetch('/api/simulation/stop', { method: 'POST' })",
    "fetch('/api/simulation/stop', { method: 'POST', headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } })"
)

text = text.replace(
    "fetch('/api/simulation/status')",
    "fetch('/api/simulation/status', { headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } })"
)

with open('app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(text)

