from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import os
import time
import random

# Variáveis globais para o banco de dados
engine = None
SessionLocal = None
Base = declarative_base()
DB_CONFIGURED = False

# Modelo de Aluno
class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    registration = Column(String, unique=True, index=True)
    course = Column(String)

def init_db(db_url):
    global engine, SessionLocal, DB_CONFIGURED
    try:
        temp_engine = create_engine(db_url, pool_pre_ping=True)
        # Testa a conexão
        with temp_engine.connect() as connection:
            pass
        
        # Se conectou, configura as variáveis globais
        engine = temp_engine
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        DB_CONFIGURED = True
        return True, "Conectado com sucesso!"
    except Exception as e:
        return False, str(e)

# Tenta carregar as configurações iniciais do .env
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "intranet_db")

if DB_USER and DB_PASSWORD:
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    init_db(SQLALCHEMY_DATABASE_URL)

app = FastAPI(title="Intranet Faculdade")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Middleware para redirecionar para a página de setup se o DB não estiver configurado
@app.middleware("http")
async def check_setup(request: Request, call_next):
    if not DB_CONFIGURED and request.url.path not in ["/setup", "/docs", "/openapi.json"]:
        return RedirectResponse(url="/setup")
    return await call_next(request)

# Dependência do DB
def get_db():
    if not engine:
        raise Exception("Banco de dados não conectado.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ROTAS DE SETUP ---

@app.get("/setup", response_class=HTMLResponse)
async def setup_get(request: Request):
    if DB_CONFIGURED:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_post(request: Request, db_host: str = Form(...), db_port: str = Form(...), db_user: str = Form(...), db_pass: str = Form(...), db_name: str = Form(...)):
    db_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    success, msg = init_db(db_url)
    
    if success:
        # Salva as configurações no arquivo .env
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        with open(env_path, "w") as f:
            f.write(f"DB_HOST={db_host}\nDB_PORT={db_port}\nDB_USER={db_user}\nDB_PASSWORD={db_pass}\nDB_NAME={db_name}\n")
        return RedirectResponse(url="/", status_code=303)
    else:
        return templates.TemplateResponse("setup.html", {"request": request, "error": f"Erro ao conectar: {msg}"})

# --- ROTAS FRONTEND ---

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    # Login simples hardcoded para o professor
    if username == "professor" and password == "senha123":
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(key="session", value="authenticated")
        return response
    return RedirectResponse(url="/?error=1", status_code=302)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse(url="/", status_code=302)
    
    students = db.query(Student).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "students": students})

@app.post("/students")
async def create_student(request: Request, name: str = Form(...), registration: str = Form(...), course: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse(url="/", status_code=302)
    
    new_student = Student(name=name, registration=registration, course=course)
    db.add(new_student)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)

# --- ROTAS PARA TESTE DE ESTRESSE (MONITORAMENTO ZABBIX) ---

@app.get("/api/stress/read")
async def stress_read(db: Session = Depends(get_db)):
    """Simula uma carga pesada de leitura no banco de dados."""
    results = []
    # Faz múltiplas queries pesadas para forçar uso de CPU e I/O de disco
    for _ in range(50):
        students = db.query(Student).order_by(Student.name.desc()).all()
        results.extend(students)
    return {"message": "Leitura pesada concluída", "records_processed": len(results)}

@app.post("/api/stress/write")
async def stress_write(db: Session = Depends(get_db)):
    """Simula uma carga pesada de escrita no banco de dados."""
    batch_size = 100
    # Insere múltiplos registros de uma vez para forçar I/O de disco
    for i in range(batch_size):
        dummy = Student(
            name=f"Aluno Teste {random.randint(1000,9999)}",
            registration=f"RA{int(time.time())}{i}{random.randint(10,99)}",
            course="Engenharia de Software"
        )
        db.add(dummy)
    db.commit()
    return {"message": f"{batch_size} registros inseridos com sucesso"}