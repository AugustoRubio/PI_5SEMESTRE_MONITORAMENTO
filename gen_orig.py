# -*- coding: utf-8 -*-
content = '''{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-12 mb-4">
        <h2 class="text-primary"><i class="bi bi-robot"></i> Simulação de Uso - Banco de Dados (Intranet)</h2>
        <p class="text-muted">Simula as ações normais dos usuários (Criação, Edição e Exclusão de alunos, turmas e professores) diretamente no banco da intranet.</p>
    </div>
</div>

<div class="row">
    <!-- Bloco de Controle -->
    <div class="col-md-5">
        <div class="card border-primary">
            <div class="card-header bg-primary text-white text-uppercase fw-bold">
                Controle da Simulação
            </div>
            <div class="card-body bg-light">
                <form id="simForm">
                    <div class="mb-3">
                        <label class="form-label fw-bold">Host do Banco de Dados (IP)</label>
                        <input type="text" class="form-control" id="dbTarget" value="10.10.100.4" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">Porta</label>
                        <input type="number" class="form-control" id="dbPort" value="3306" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">User e Password</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="dbUser" value="intranet_user" placeholder="User">
                            <input type="password" class="form-control" id="dbPass" value="bcd127" placeholder="Pass" maxlength="64">
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">Nome do Banco (Database)</label>
                        <input type="text" class="form-control" id="dbName" value="intranet_db" required>
                    </div>

                    <div class="mb-3">
                        <label class="form-label fw-bold">Perfil de Tráfego</label>
                        <select class="form-select" id="simProfile">
                            <option value="calm">Calmo (Ação a cada 5 segundos)</option>
                            <option value="aggressive">Agressivo (Ação a cada 0.5 segundos)</option>
                        </select>
                    </div>

                    <div class="mb-4">
                        <label class="form-label fw-bold">Duração da Simulação (segundos)</label>
                        <input type="number" class="form-control" id="simDuration" value="60" required>
                    </div>

                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-success" id="btnStart"><i class="bi bi-play-fill"></i> Iniciar Simulação</button>
                        <button type="button" class="btn btn-danger" id="btnStop"><i class="bi bi-stop-fill"></i> Parar Simulação</button>
                        <button type="button" class="btn btn-warning text-dark fw-bold mt-2" id="btnClear"><i class="bi bi-trash-fill"></i> Limpar Dados da Simulação</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Bloco de Status e Logs -->
    <div class="col-md-7">
        <div class="card h-100 border-info">
            <div class="card-header bg-info text-dark text-uppercase fw-bold">
                Dashboard de Status
            </div>
            <div class="card-body">
                <div class="row text-center mb-4">
                    <div class="col">
                        <h6 class="text-muted text-uppercase mb-1">Status</h6>
                        <span class="badge bg-secondary fs-6" id="statusBadge">PARADO</span>
                    </div>
                    <div class="col">
                        <h6 class="text-muted text-uppercase mb-1">Perfil</h6>
                        <span class="fw-bold fs-5 text-dark" id="statusProfile">-</span>
                    </div>
                    <div class="col">
                        <h6 class="text-muted text-uppercase mb-1">Ações Realizadas</h6>
                        <span class="fw-bold fs-5 text-primary" id="statusActions">0</span>
                    </div>
                </div>

                <h6 class="fw-bold border-bottom pb-2 mt-4"><i class="bi bi-journal-text"></i> Console de Execução MySQL</h6>
                <div class="bg-dark text-light p-3 rounded" style="height: 350px; overflow-y: auto; font-family: monospace; font-size: 0.85rem;" id="logsContainer">
                    <span class="text-muted">Aguardando início...</span>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    const token = localStorage.getItem("token");
    if (!token) { window.location.href = "/login"; }

    const headers = {
        "Content-Type": "application/json",
        "Authorization": Bearer \
    };

    let statusInterval;

    function getSimConfig() {
        return {
            db_host: document.getElementById("dbTarget").value,
            db_port: parseInt(document.getElementById("dbPort").value, 10),
            db_user: document.getElementById("dbUser").value,
            db_pass: document.getElementById("dbPass").value,
            db_name: document.getElementById("dbName").value,
            profile: document.getElementById("simProfile").value,
            duration: parseInt(document.getElementById("simDuration").value, 10)
        };
    }

    document.getElementById("simForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const payload = getSimConfig();

        try {
            const res = await fetch("/api/simulation/start", {
                method: "POST",
                headers: headers,
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                alert("Simulação iniciada com sucesso!");
                startStatusPolling();
            } else {
                const data = await res.json();
                alert("Erro: " + (data.detail || "Falha ao iniciar"));
            }
        } catch(err) {
            console.error(err);
            alert("Erro de comunicação.");
        }
    });

    document.getElementById("btnStop").addEventListener("click", async () => {
        try {
            const res = await fetch("/api/simulation/stop", { method: "POST", headers: headers });
            if(res.ok) {
                alert("Comando de parada enviado!");
            }
        } catch(err) {
            console.error(err);
        }
    });

    document.getElementById("btnClear").addEventListener("click", async () => {
        if(!confirm("Atenção: Isso apagará apenas os registros gerados pela simulação (que possuem a tag [SIM]). Deseja continuar?")) return;
        
        const payload = getSimConfig();
        payload.duration = 0;

        try {
            const res = await fetch("/api/simulation/clear_simulated_data", {
                method: "POST",
                headers: headers,
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok) {
                alert("Sucesso: " + data.message);
                const logsContainer = document.getElementById("logsContainer");
                const div = document.createElement("div");
                const timeStr = new Date().toLocaleTimeString();
                div.className = "mb-1 text-warning fw-bold";
                div.innerHTML = [\] > << LIMPEZA CONCLUÍDA >> \;
                if(logsContainer.children[0] && logsContainer.children[0].className.includes("text-muted")) {
                    logsContainer.innerHTML = '';
                }
                logsContainer.prepend(div);
            } else {
                alert("Erro ao limpar dados: " + (data.detail || "Falha desconhecida"));
            }
        } catch(err) {
            console.error(err);
            alert("Erro de comunicação ao limpar dados.");
        }
    });

    function startStatusPolling() {
        if(statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(fetchStatus, 1000);
        fetchStatus();
    }

    async function fetchStatus() {
        try {
            const res = await fetch("/api/simulation/status", { headers: headers });
            if (res.ok) {
                const data = await res.json();

                const badge = document.getElementById("statusBadge");
                if (data.is_running) {
                    badge.textContent = "RODANDO";
                    badge.className = "badge bg-success fs-6";
                } else {
                    badge.textContent = "PARADA";
                    badge.className = "badge bg-secondary fs-6";
                    clearInterval(statusInterval);
                }

                document.getElementById("statusProfile").textContent = data.profile ? (data.profile === "calm" ? "Calmo" : "Agressivo") : "-";
                document.getElementById("statusActions").textContent = data.actions_performed;
                
                const logsContainer = document.getElementById("logsContainer");
                
                if (data.logs && data.logs.length > 0) {
                    logsContainer.innerHTML = "";
                    data.logs.forEach(log => {
                        const div = document.createElement("div");
                        let textColor = "text-success";
                        if(log.toLowerCase().includes("erro") || log.toLowerCase().includes("falha")) {
                            textColor = "text-danger";
                        } else if(log.toLowerCase().includes("finalizada") || log.toLowerCase().includes("parada")) {
                            textColor = "text-info";
                        }
                        
                        div.className = "mb-1 " + textColor;
                        const timeStr = new Date().toLocaleTimeString();
                        div.innerHTML = [\] > \;
                        logsContainer.appendChild(div);
                    });
                } else if (data.logs.length === 0 && !data.is_running && statusInterval == null) {
                   if (!logsContainer.innerHTML.includes("Aguardando")) {
                       // logsContainer.innerHTML = '<span class="text-muted">Aguardando início...</span>';
                   }
                }
            }
        } catch (error) {
            console.error(error);
        }
    }

    // Inicializa polling caso já tenha algo rodando após refresh
    startStatusPolling();
</script>
{% endblock %}
'''

with open('web_panel/app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Restaurado e corrigido 100%")
