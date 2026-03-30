from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import snmp, attacks, auth, admin, stress, simulation, bruteforce, web_traffic
from app.auth import get_current_user
import os
import subprocess
import json

app = FastAPI(
    title="Painel de Controle - Simulação de Redes e Segurança",
    description="Painel para controle do simulador SNMP e disparos de ataques controlados.",
    version="1.2.0"
)

# Configuração de arquivos estáticos e templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Incluindo as rotas (routers)
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(snmp.router, prefix="/api/snmp", tags=["SNMP"], dependencies=[Depends(get_current_user)])
app.include_router(attacks.router, prefix="/api/attacks", tags=["Ataques"], dependencies=[Depends(get_current_user)])
app.include_router(admin.router, prefix="/api/admin", tags=["Administração"], dependencies=[Depends(get_current_user)])
app.include_router(stress.router, prefix="/api/stress", tags=["Estresse"], dependencies=[Depends(get_current_user)])
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulação"], dependencies=[Depends(get_current_user)])
app.include_router(bruteforce.router, prefix="/api/bruteforce", tags=["Brute Force"], dependencies=[Depends(get_current_user)])
app.include_router(web_traffic.router, prefix="/api/traffic", tags=["Tráfego Web"], dependencies=[Depends(get_current_user)])

@app.get("/api/docker/stats/public")
async def get_docker_stats_public():
    def run_docker_cmd(args_list):
        for base in [["docker"], ["/usr/bin/docker"], ["/usr/local/bin/docker"]]:
            try:
                cmd = base + args_list
                result = subprocess.run(cmd, capture_output=True, text=True)
                return result.returncode == 0, result.stdout if result.returncode == 0 else result.stderr
            except FileNotFoundError:
                continue
        return False, "Comando docker não encontrado no PATH."

    success, out = run_docker_cmd(["stats", "--no-stream", "--format", '{"name":"{{.Name}}", "cpu":"{{.CPUPerc}}", "mem":"{{.MemPerc}}"}'])
    data = []
    if success and out.strip():
        for line in out.strip().split('\n'):
            if line.strip():
                try:
                    c = json.loads(line)
                    cpu_val = c.get('cpu', '').replace('%', '').strip()
                    mem_val = c.get('mem', '').replace('%', '').strip()
                    
                    # Trata o caso de containers da botnet recém-criados que mostram '--'
                    c['cpu'] = float(cpu_val) if cpu_val and cpu_val != '--' else 0.0
                    c['mem'] = float(mem_val) if mem_val and mem_val != '--' else 0.0
                    data.append(c)
                except Exception:
                    pass
    return data

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login"})

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Dashboard Principal"})

@app.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request):
    return templates.TemplateResponse("devices.html", {"request": request, "title": "Gerenciamento de Dispositivos"})

@app.get("/docker_manager", response_class=HTMLResponse)
async def docker_manager_page(request: Request):
    return templates.TemplateResponse("docker_manager.html", {"request": request, "title": "Gerenciamento Docker"})

@app.get("/attacks", response_class=HTMLResponse)
async def attacks_page(request: Request):
    return templates.TemplateResponse("attacks.html", {"request": request, "title": "Central de Ataques"})

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request, "title": "Configurações do Ambiente"})

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "title": "Administração de Usuários"})

@app.get("/stress", response_class=HTMLResponse)
async def stress_page(request: Request):
    return templates.TemplateResponse("stress.html", {"request": request, "title": "Testes de Estresse"})

@app.get("/simulation", response_class=HTMLResponse)
async def simulation_page(request: Request):
    return templates.TemplateResponse("simulation.html", {"request": request, "title": "Simulação de Uso"})

@app.get("/traffic", response_class=HTMLResponse)
async def traffic_page(request: Request):
    return templates.TemplateResponse("traffic.html", {"request": request, "title": "Simulador de Tráfego Web"})
