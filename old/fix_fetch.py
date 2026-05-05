import pathlib

file_path = pathlib.Path('web_panel/app/templates/simulation.html')
lines = file_path.read_text(encoding='utf-8').splitlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if 'async function fetchStatus()' in line:
        start_idx = i
        break
for i in range(start_idx, len(lines)):
    if 'function startUnifiedPolling()' in lines[i]:
        end_idx = i
        break

fetch_code = '''    async function fetchStatus() {
        let isAnyRunning = false;
        let statusData = { stress: null, sim: null };

        // 1. Fetch Stress Status
        try {
            const resStress = await fetch('/api/stress/status', { headers });
            if (resStress.ok) {
                const data = await resStress.json();
                statusData.stress = data;
                const badge = document.getElementById('stressBadge');
                if (data.is_running) {
                    isAnyRunning = true;
                    if(badge) {
                        badge.className = 'badge bg-warning text-dark blink';
                        badge.childNodes[0].nodeValue = 'STRESS RODANDO';
                    }

                    let timeRemaining = "N/A";
                    if(data.start_time && data.duration) {
                        const now = Date.now() / 1000;
                        const elapsed = now - data.start_time;
                        let left = Math.max(0, data.duration - elapsed);
                        timeRemaining = left.toFixed(0) + "s";
                    }
                    if(document.getElementById('stressTime')) document.getElementById('stressTime').textContent = " (" + timeRemaining + " restantes)";
                    if(document.getElementById('stressReqCount')) document.getElementById('stressReqCount').textContent = data.requests_sent;
                } else {
                    if(badge) {
                        badge.className = 'badge bg-secondary';
                        badge.childNodes[0].nodeValue = 'Stress: Parado';
                    }
                    if(document.getElementById('stressTime')) document.getElementById('stressTime').textContent = "";
                }

                // Processar logs do Estresse WEB
                const strLogsContainer = document.getElementById('logsContainer');
                if(data.logs && data.logs.length > 0 && strLogsContainer) {
                    if(!window.lastStressLogStr) window.lastStressLogStr = [];
                    for(let i = data.logs.length - 1; i >= 0; i--) {
                        const log = data.logs[i];
                        if (window.lastStressLogStr.includes(log)) continue;

                        window.lastStressLogStr.push(log);
                        if(window.lastStressLogStr.length > 100) window.lastStressLogStr.shift();

                        const div = document.createElement('div');
                        let classColors = 'text-light';
                        if(log.toLowerCase().includes('erro') || log.toLowerCase().includes('falha')) {
                            classColors = 'text-danger fw-bold';
                        } else if(log.toLowerCase().includes('finalizado')) {
                            classColors = 'text-info fw-bold';
                        } else if(log.toLowerCase().includes('iniciando') || log.toLowerCase().includes('camuflando')) {
                            classColors = 'text-warning fw-bold';
                        } else {
                            classColors = 'text-success fw-bold';
                        }

                        div.className = 'mb-1 ' + classColors;
                        const timeStr = new Date().toLocaleTimeString();
                        div.innerText = '[' + timeStr + '] > [WEB STRESS] ' + log;

                        if(strLogsContainer.children.length > 0 && strLogsContainer.children[0].innerText.includes('[Ready]')) {
                            strLogsContainer.innerHTML = '';
                        }
                        strLogsContainer.prepend(div);
                    }
                }
            }
        } catch (e) {
            console.error('Erro no fetchStatus Stress:', e);
        }

        // 2. Fetch Sim Status
        try {
            const resSim = await fetch('/api/simulation/status', { headers });
            if (resSim.ok) {
                const data = await resSim.json();
                statusData.sim = data;
                const badge = document.getElementById('simBadge');
                if (data.is_running) {
                    isAnyRunning = true;
                    if(badge) {
                        badge.className = 'badge bg-success blink';
                        badge.childNodes[0].nodeValue = 'SIMULAÇÃO RODANDO';
                    }

                    let timeRemaining = "N/A";
                    if(data.start_time && data.duration) {
                        const now = Date.now() / 1000;
                        const elapsed = now - data.start_time;
                        let left = Math.max(0, data.duration - elapsed);
                        timeRemaining = left.toFixed(0) + "s";
                    }
                    if(document.getElementById('simTime')) document.getElementById('simTime').textContent = " (" + timeRemaining + " restantes)";
                    if(document.getElementById('simActionsCount')) document.getElementById('simActionsCount').textContent = data.actions_performed;
                } else {
                    if(badge) {
                        badge.className = 'badge bg-secondary';
                        badge.childNodes[0].nodeValue = 'Simulação: Parada';
                    }
                    if(document.getElementById('simTime')) document.getElementById('simTime').textContent = "";
                }

                // Processar logs da simulacao
                const logsContainer = document.getElementById('logsContainer');
                if(data.logs && data.logs.length > 0 && logsContainer) {
                    if(!window.lastSimLogStr) {
                        window.lastSimLogStr = []; 
                    }
                    
                    for(let i = data.logs.length - 1; i >= 0; i--) {
                        const log = data.logs[i];
                        
                        if (window.lastSimLogStr.includes(log)) {
                            continue;
                        }
                        
                        window.lastSimLogStr.push(log);
                        if(window.lastSimLogStr.length > 100) window.lastSimLogStr.shift(); 
                        
                        const div = document.createElement('div');
                        let classColors = 'text-light';
                        if(log.toLowerCase().includes('erro') || log.toLowerCase().includes('falha') || log.toLowerCase().includes('except') || log.toLowerCase().includes('nenhuma')) {
                            classColors = 'text-danger fw-bold';
                        } else if(log.toLowerCase().includes('finalizada') || log.toLowerCase().includes('parada')) {
                            classColors = 'text-info fw-bold';
                        } else if(log.toLowerCase().includes('iniciando')) {
                            classColors = 'text-warning fw-bold';
                        } else {
                            classColors = 'text-success fw-bold';
                        }

                        div.className = 'mb-1 ' + classColors;
                        const timeStr = new Date().toLocaleTimeString();
                        div.innerText = '[' + timeStr + '] > ' + log;
                        
                        if(logsContainer.children.length > 0 && logsContainer.children[0].innerText.includes('[Ready]')) {
                            logsContainer.innerHTML = '';
                        }
                        
                        logsContainer.prepend(div);
                    }
                }
            }
        } catch (e) {
            console.error('Erro no fetchStatus Sim:', e);
        }

        // 3. Atualizar painel de resumo de Alvo Ativo
        let types = [];
        let targets = [];
        if(statusData.stress && statusData.stress.is_running) {
            targets.push(statusData.stress.target);
            types.push(statusData.stress.type || 'STRESS HTTP');
        }
        if(statusData.sim && statusData.sim.is_running) {
            targets.push(statusData.sim.target);
            types.push('COMPORTAMENTO DB (' + (statusData.sim.profile || 'N/A').toUpperCase() + ')');
        }
        
        const summaryPanel = document.getElementById('targetSummary');
        if(isAnyRunning && (targets.length > 0)) {
            let uniqueTargets = [...new Set(targets)];
            if(document.getElementById('activeTargetsInfo')) document.getElementById('activeTargetsInfo').textContent = uniqueTargets.join(', ');
            if(document.getElementById('activeTypesInfo')) document.getElementById('activeTypesInfo').textContent = types.join(' + ');
            if(summaryPanel) summaryPanel.style.display = 'block';
        } else {
            if(summaryPanel) summaryPanel.style.display = 'none';
        }

        if (!isAnyRunning && pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }
'''

new_lines = lines[:start_idx] + fetch_code.splitlines() + lines[end_idx:]
file_path.write_text('\n'.join(new_lines), encoding='utf-8')
print("Successfully replaced fetchStatus")
