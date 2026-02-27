from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import os
import time
import random

# Configuração do Banco de Dados MariaDB
# Usando localhost como padrão para rodar nativamente sem Docker
DB_USER = os.getenv("DB_USER", "intranet_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "intranet_pass")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "intranet_db")

SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Tenta conectar ao banco de dados com retries
engine = None
for i in range(5):
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
        engine.connect()
        print("Conectado ao MariaDB com sucesso!")
        break
    except Exception as e:
        print(f"Aguardando banco de dados... ({i+1}/5)")
        time.sleep(2)

if not engine:
    print("AVISO: Não foi possível conectar ao MariaDB. Verifique se o serviço está rodando.")
    print("O sistema tentará iniciar, mas as rotas que dependem do banco falharão.")
else:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    # Modelo de Aluno
    class Student(Base):
        __tablename__ = "students"
        id = Column(Integer, primary_key=True, index=True)
        name = Column(String, index=True)
        registration = Column(String, unique=True, index=True)
        course = Column(String)

    # Cria as tabelas automaticamente no MariaDB se elas não existirem
    # É assim que a estrutura do banco é injetada!
    Base.metadata.create_all(bind=engine)

app = FastAPI(title="Intranet Faculdade")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Dependência do DB
def get_db():
    if not engine:
        raise Exception("Banco de dados não conectado.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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