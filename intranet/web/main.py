from fastapi import FastAPI, Request, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, func, desc
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from dotenv import load_dotenv
import os
import time
import random
import datetime
import urllib.parse
from passlib.context import CryptContext
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# Configurações iniciais
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = None
SessionLocal = None
Base = declarative_base()
DB_CONFIGURED = False

# Modelos (Mantidos conforme sua estrutura)
student_class = Table('student_class', Base.metadata,
    Column('student_id', Integer, ForeignKey('students.id')),
    Column('class_id', Integer, ForeignKey('classes.id'))
)

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(255))

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    registration = Column(String(50), unique=True, index=True)
    password = Column(String(255), nullable=True)
    course = Column(String(255))
    classes = relationship("Class", secondary=student_class, back_populates="students")
    grades = relationship("Grade", back_populates="student", cascade="all, delete-orphan")

class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    class_id = Column(Integer, ForeignKey('classes.id'))
    value = Column(String(10))
    description = Column(String(255))
    student = relationship("Student", back_populates="grades")

class Professor(Base):
    __tablename__ = "professors"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(255))
    name = Column(String(255))
    department = Column(String(255))
    classes = relationship("Class", back_populates="professor", cascade="all, delete-orphan")

class Class(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    professor_id = Column(Integer, ForeignKey('professors.id'))
    professor = relationship("Professor", back_populates="classes")
    students = relationship("Student", secondary=student_class, back_populates="classes")
    attendances = relationship("Attendance", back_populates="course_class", cascade="all, delete-orphan")

class Attendance(Base):
    __tablename__ = "attendances"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey('students.id'))
    class_id = Column(Integer, ForeignKey('classes.id'))
    date = Column(String(50))
    absent = Column(Integer, default=1)
    course_class = relationship("Class", back_populates="attendances")

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(50), index=True)
    username = Column(String(255))
    timestamp = Column(Integer)
    success = Column(Integer, default=0)

def init_db(db_url):
    global engine, SessionLocal, DB_CONFIGURED
    try:
        temp_engine = create_engine(db_url, pool_size=50, max_overflow=100, pool_pre_ping=True)
        with temp_engine.connect() as conn: pass
        engine = temp_engine
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        DB_CONFIGURED = True
        
        db = SessionLocal()
        if not db.query(Admin).filter(Admin.username == "admin").first():
            db.add(Admin(username="admin", password=pwd_context.hash("admin")))
            db.commit()
        db.close()
        return True, "Sucesso"
    except Exception as e:
        print(f"ERRO DB: {e}")
        return False, str(e)

# Carregamento automático do DB se o .env existir
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
if DB_USER and DB_PASS:
    url = f"mysql+pymysql://{DB_USER}:{urllib.parse.quote_plus(DB_PASS)}@{os.getenv('DB_HOST','127.0.0.1')}:{os.getenv('DB_PORT','3306')}/{os.getenv('DB_NAME','intranet_db')}"
    init_db(url)

app = FastAPI(title="Intranet Faculdade")
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir): os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

@app.middleware("http")
async def check_setup(request: Request, call_next):
    allowed = ["/setup", "/docs", "/openapi.json", "/security/metrics", "/security/metrics/"]
    if not DB_CONFIGURED and request.url.path not in allowed and not request.url.path.startswith("/static"):
        return RedirectResponse(url="/setup")
    return await call_next(request)

def get_db():
    if not SessionLocal: return None
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.get("/setup", response_class=HTMLResponse)
def setup_get(request: Request):
    if DB_CONFIGURED: return RedirectResponse(url="/login")
    return templates.TemplateResponse("setup.html", {"request": request, "form_data": None})

@app.post("/setup")
def setup_post(request: Request, db_host: str = Form(...), db_port: str = Form(...), db_user: str = Form(...), db_pass: str = Form(...), db_name: str = Form(...)):
    url = f"mysql+pymysql://{db_user}:{urllib.parse.quote_plus(db_pass)}@{db_host}:{db_port}/{db_name}"
    success, msg = init_db(url)
    if success:
        with open(env_path, "w") as f:
            f.write(f"DB_HOST={db_host}\nDB_PORT={db_port}\nDB_USER={db_user}\nDB_PASSWORD={db_pass}\nDB_NAME={db_name}\n")
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("setup.html", {"request": request, "error": msg, "form_data": locals()})

@app.get("/", response_class=HTMLResponse)
def root_redirect(request: Request):
    if DB_CONFIGURED:
        return templates.TemplateResponse("index.html", {"request": request})
    return RedirectResponse(url="/setup")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, type: str = "admin"):
    return templates.TemplateResponse("login.html", {"request": request, "type": type})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), login_type: str = Form(...), db: Session = Depends(get_db)):
    if not db: return RedirectResponse(url="/setup")
    user = None
    if login_type == 'admin':
        user = db.query(Admin).filter(Admin.username == username).first()
        target = "/admin_dashboard"
    elif login_type == 'professor':
        user = db.query(Professor).filter(Professor.username == username).first()
        target = "/prof_dashboard"
    elif login_type == 'student':
        user = db.query(Student).filter(Student.registration == username).first()
        target = "/student_dashboard"

    if user and pwd_context.verify(password, user.password):
        res = RedirectResponse(url=target, status_code=302)
        res.set_cookie(key="session", value="authenticated")
        res.set_cookie(key="role", value=login_type)
        res.set_cookie(key="user_id", value=str(user.id))
        return res
    return RedirectResponse(url=f"/login?error=1&type={login_type}")

@app.get("/logout")
def logout():
    res = RedirectResponse(url="/login")
    for k in ["session", "role", "user_id"]: res.delete_cookie(k)
    return res

# Rota de métricas simplificada para teste
@app.get("/security/metrics")
def metrics(db: Session = Depends(get_db)):
    return {"status": "online", "db": "ok" if db else "error"}
