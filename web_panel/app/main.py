from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import snmp, attacks, auth
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

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login"})

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # A verificação de token no frontend será feita via JavaScript, 
    # mas a página principal só carrega os dados se o JS enviar o token válido.
    return templates.TemplateResponse("index.html", {"request": request, "title": "Dashboard Principal"})
