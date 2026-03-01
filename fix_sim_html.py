with open('web_panel/app/templates/simulation.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Trocar inputs padrao
text = text.replace('id="simDbHost" class="form-control" placeholder="10.10.100.4" required>', 'id="simDbHost" class="form-control" value="10.10.100.4" required>')
text = text.replace('id="simDbHost" class="form-control" placeholder="Ex: 10.10.100.4" required>', 'id="simDbHost" class="form-control" value="10.10.100.4" required>')
text = text.replace('value="root"', 'value="intranet_user"')
text = text.replace('value="127.0.0.1"', 'value="10.10.100.4"')
if 'value="10.10.100.4"' not in text:
    text = text.replace('<input type="text" id="simDbHost"', '<input type="text" id="simDbHost" value="10.10.100.4"')

# Adicionar Botao Claro no Panel de Controle
if 'id="btnSimClear"' not in text:
    old_btn = '<button type="button" class="btn btn-danger w-100" id="btnSimStop" onclick="stopSim()" disabled><i class="bi bi-stop-circle"></i> Parar</button>'
    new_btn = old_btn + '\n                            <button type="button" class="btn btn-warning w-100 mt-2" id="btnSimClear" onclick="clearSimData()"><i class="bi bi-trash"></i> Limpar Dados [SIM] do Banco</button>'
    text = text.replace(old_btn, new_btn)

# Adicionar Evento de click de limpeza no JS
js_func = '''        async function clearSimData() {
            if(!confirm("Atenção: Isto irá apagar todos os alunos, professores e turmas marcados com [SIM] criados pelo simulador. Deseja continuar?")) return;
            
            const config = {
                db_host: document.getElementById('simDbHost').value,
                db_port: parseInt(document.getElementById('simDbPort').value),
                db_user: document.getElementById('simDbUser').value,
                db_pass: document.getElementById('simDbPass').value,
                db_name: document.getElementById('simDbName').value,
                profile: 'calm',
                duration: 0
            };
            
            try {
                const response = await fetch('/api/simulation/clear_simulated_data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await response.json();
                if(response.ok) {
                    alert(result.message);
                } else {
                    alert("Erro: " + result.detail);
                }
            } catch (err) {
                alert("Erro ao conectar com o backend: " + err);
            }
        }
'''
if 'clearSimData' not in text:
    text = text.replace('async function startSim()', js_func + '\n        async function startSim()')

with open('web_panel/app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(text)
