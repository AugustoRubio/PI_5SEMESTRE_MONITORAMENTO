from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import os
import time
import random

import urllib.parse

# Variáveis globais para o banco de dados
engine = None
SessionLocal = None
Base = declarative_base()
DB_CONFIGURED = False

# Modelo de Aluno
class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    registration = Column(String(50), unique=True, index=True)
    course = Column(String(255))

# Modelo de Professor
class Professor(Base):
    __tablename__ = "professors"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(255))
    name = Column(String(255))
    department = Column(String(255))

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

# Monta a pasta de arquivos estáticos (para a logo e css)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Middleware para redirecionar para a página de setup se o DB não estiver configurado
@app.middleware("http")
async def check_setup(request: Request, call_next):
    if not DB_CONFIGURED and request.url.path not in ["/setup", "/docs", "/openapi.json"] and not request.url.path.startswith("/static"):
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
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_post(request: Request, db_host: str = Form(...), db_port: str = Form(...), db_user: str = Form(...), db_pass: str = Form(...), db_name: str = Form(...)):
    # Trata o caso onde a senha pode conter caracteres especiais como '@' que quebram a URL do SQLAlchemy
    safe_pass = urllib.parse.quote_plus(db_pass)
    
    db_url = f"mysql+pymysql://{db_user}:{safe_pass}@{db_host}:{db_port}/{db_name}"
    success, msg = init_db(db_url)
    
    if success:
        # Salva as configurações no arquivo .env
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        with open(env_path, "w") as f:
            f.write(f"DB_HOST={db_host}\nDB_PORT={db_port}\nDB_USER={db_user}\nDB_PASSWORD={db_pass}\nDB_NAME={db_name}\n")
        return RedirectResponse(url="/login", status_code=303)
    else:
        # Retorna os dados preenchidos para não perder o que foi digitado
        form_data = {
            "db_host": db_host,
            "db_port": db_port,
            "db_user": db_user,
            "db_name": db_name,
            "db_pass": db_pass
        }
        return templates.TemplateResponse("setup.html", {"request": request, "error": f"Erro ao conectar: {msg}", "form_data": form_data})

# --- ROTAS FRONTEND ---

@app.get("/")
async def root_redirect():
    if DB_CONFIGURED:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/setup", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Verifica se o professor existe no banco de dados
    professor = db.query(Professor).filter(Professor.username == username, Professor.password == password).first()
    
    # Fallback para o admin padrão caso o banco esteja vazio
    if professor or (username == "professor" and password == "senha123"):
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(key="session", value="authenticated")
        # Define se é admin (o admin padrão ou alguém do departamento "Admin")
        is_admin = "true" if (username == "professor" and password == "senha123") or (professor and professor.department == "Admin") else "false"
        response.set_cookie(key="is_admin", value=is_admin)
        return response
    return RedirectResponse(url="/login?error=1", status_code=302)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    response.delete_cookie("is_admin")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse(url="/login", status_code=302)
    
    is_admin = request.cookies.get("is_admin") == "true"
    students = db.query(Student).all()
    professors = db.query(Professor).all() if is_admin else []
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "students": students, 
        "professors": professors,
        "is_admin": is_admin
    })

@app.post("/students")
async def create_student(request: Request, name: str = Form(...), registration: str = Form(...), course: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse(url="/login", status_code=302)
    
    new_student = Student(name=name, registration=registration, course=course)
    db.add(new_student)
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/professors")
async def create_professor_web(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    name: str = Form(...), 
    department: str = Form(...), 
    db: Session = Depends(get_db)
):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/dashboard", status_code=302)
    
    # Verifica se já existe
    existing = db.query(Professor).filter(Professor.username == username).first()
    if not existing:
        new_prof = Professor(username=username, password=password, name=name, department=department)
        db.add(new_prof)
        db.commit()
        
    return RedirectResponse(url="/dashboard", status_code=302)

@app.post("/professors/delete/{prof_id}")
async def delete_professor_web(request: Request, prof_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("is_admin") != "true":
        return RedirectResponse(url="/dashboard", status_code=302)
        
    prof = db.query(Professor).filter(Professor.id == prof_id).first()
    if prof:
        db.delete(prof)
        db.commit()
        
    return RedirectResponse(url="/dashboard", status_code=302)

# --- ROTAS DE ADMINISTRAÇÃO (API PARA ZABBIX/PAINEL) ---

@app.get("/api/professors")
async def get_professors(db: Session = Depends(get_db)):
    """Retorna a lista de professores (útil para monitoramento/painel)."""
    professors = db.query(Professor).all()
    return [{"id": p.id, "username": p.username, "name": p.name, "department": p.department} for p in professors]

@app.post("/api/professors")
async def create_professor(username: str = Form(...), password: str = Form(...), name: str = Form(...), department: str = Form(...), db: Session = Depends(get_db)):
    """Cria um novo professor via API."""
    # Verifica se já existe
    existing = db.query(Professor).filter(Professor.username == username).first()
    if existing:
        return {"error": "Professor já existe"}
        
    new_prof = Professor(username=username, password=password, name=name, department=department)
    db.add(new_prof)
    db.commit()
    return {"message": "Professor criado com sucesso", "username": username}

@app.delete("/api/professors/{prof_id}")
async def delete_professor(prof_id: int, db: Session = Depends(get_db)):
    """Deleta um professor via API."""
    prof = db.query(Professor).filter(Professor.id == prof_id).first()
    if not prof:
        return {"error": "Professor não encontrado"}
    
    db.delete(prof)
    db.commit()
    return {"message": "Professor deletado com sucesso"}

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