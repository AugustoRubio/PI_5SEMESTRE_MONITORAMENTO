from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import snmp, attacks, auth, admin, stress, simulation
from app.auth import get_current_user
import os

app = FastAPI(
    title="Painel de Controle - Simulação de Redes e Segurança",
    description="Painel para controle do simulador SNMP e disparos de ataques controlados.",
    version="1.0.0"
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

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login"})

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Dashboard Principal"})

@app.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request):
    return templates.TemplateResponse("devices.html", {"request": request, "title": "Gerenciamento de Dispositivos"})

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

