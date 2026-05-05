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

# Carrega as variáveis do .env no início para persistir após reinícios
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Variáveis globais para o banco de dados
engine = None
SessionLocal = None
Base = declarative_base()
DB_CONFIGURED = False

# Association table for students and classes
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
    value = Column(String(10)) # Podem ser notas com decimais ou conceitos
    description = Column(String(255))
    
    student = relationship("Student", back_populates="grades")
    course_class = relationship("Class")

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
    absent = Column(Integer, default=1) # 1 for absent
    
    student = relationship("Student")
    course_class = relationship("Class", back_populates="attendances")

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(50), index=True)
    username = Column(String(255))
    timestamp = Column(Integer) # Unix timestamp
    success = Column(Integer, default=0) # 0 for failure, 1 for success

def init_db(db_url):
    global engine, SessionLocal, DB_CONFIGURED
    try:
        # Aumentado significativamente o pool_size e max_overflow para suportar o teste de estresse
        temp_engine = create_engine(
            db_url, 
            pool_size=100, 
            max_overflow=200, 
            pool_pre_ping=True, 
            pool_recycle=1800
        )
        # Testa a conexão
        with temp_engine.connect() as connection:
            pass
        
        # Se conectou, configura as variáveis globais
        engine = temp_engine
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        DB_CONFIGURED = True
        
        # Seed account admin
        db = SessionLocal()
        admin = db.query(Admin).filter(Admin.username == "admin").first()
        hashed_pwd = pwd_context.hash("admin")
        if not admin:
            new_admin = Admin(username="admin", password=hashed_pwd)
            db.add(new_admin)
            db.commit()
        else:
            admin.password = hashed_pwd
            db.commit()
        db.close()
        
        return True, "Conectado com sucesso!"
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        return False, str(e)

# Tenta carregar as configurações iniciais do .env
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "intranet_db")

if DB_USER and DB_PASSWORD:
    safe_pass = urllib.parse.quote_plus(DB_PASSWORD)
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{safe_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    init_db(SQLALCHEMY_DATABASE_URL)

app = FastAPI(title="Intranet Faculdade")
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Middleware para redirecionar para a página de setup
@app.middleware("http")
async def check_setup(request: Request, call_next):
    allowed_paths = ["/setup", "/docs", "/openapi.json", "/security/metrics", "/security/metrics/"]
    if not DB_CONFIGURED and request.url.path not in allowed_paths and not request.url.path.startswith("/static"):
        return RedirectResponse(url="/setup")
    return await call_next(request)

# Dependência do DB
def get_db():
    if not engine:
        return None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ENDPOINT DE SEGURANÇA ---
@app.get("/security/metrics")
@app.get("/security/metrics/")
def security_metrics(db: Session = Depends(get_db)):
    if db is None:
        return {"total_failures": 0, "error": "Banco de dados não configurado"}
    
    now = int(time.time())
    total_failures = db.query(LoginAttempt).filter(LoginAttempt.success == 0).count()
    failures_last_hour = db.query(LoginAttempt).filter(LoginAttempt.success == 0, LoginAttempt.timestamp > now - 3600).count()
    active_ips = db.query(LoginAttempt.ip_address).filter(LoginAttempt.timestamp > now - 300).distinct().count()
    
    recent_logs = db.query(LoginAttempt).filter(LoginAttempt.success == 0).order_by(LoginAttempt.timestamp.desc()).limit(10).all()
    logs = [{"ip": l.ip_address, "user": l.username, "time": datetime.datetime.fromtimestamp(l.timestamp).strftime("%H:%M:%S")} for l in recent_logs]

    return {
        "total_failures": total_failures,
        "failures_last_hour": failures_last_hour,
        "active_ips": active_ips,
        "recent_failed_attempts": logs,
        "system_time": now
    }

# --- ROTAS DE SETUP ---
@app.get("/setup", response_class=HTMLResponse)
def setup_get(request: Request):
    if DB_CONFIGURED:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request=request, name="setup.html", context={"form_data": None})

@app.post("/setup")
def setup_post(request: Request, db_host: str = Form(...), db_port: str = Form(...), db_user: str = Form(...), db_pass: str = Form(...), db_name: str = Form(...)):
    safe_pass = urllib.parse.quote_plus(db_pass)
    db_url = f"mysql+pymysql://{db_user}:{safe_pass}@{db_host}:{db_port}/{db_name}"
    success, msg = init_db(db_url)
    
    if success:
        with open(env_path, "w") as f:
            f.write(f"DB_HOST={db_host}\nDB_PORT={db_port}\nDB_USER={db_user}\nDB_PASSWORD={db_pass}\nDB_NAME={db_name}\n")
        return RedirectResponse(url="/login", status_code=303)
    else:
        form_data = {"db_host": db_host, "db_port": db_port, "db_user": db_user, "db_name": db_name}
        return templates.TemplateResponse(request=request, name="setup.html", context={"error": f"Erro ao conectar: {msg}", "form_data": form_data})

# --- ROTAS FRONTEND ---
@app.get("/", response_class=HTMLResponse)
def root_redirect(request: Request):
    if DB_CONFIGURED:
        return templates.TemplateResponse(request=request, name="index.html", context={})
    return RedirectResponse(url="/setup", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, type: str = "admin"):
    return templates.TemplateResponse(request=request, name="login.html", context={"type": type})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), login_type: str = Form(...), db: Session = Depends(get_db)):
    if db is None: return RedirectResponse(url="/setup")
        
    ip = request.client.host
    now = int(time.time())
    
    authenticated = False
    user_id = None

    if login_type == 'admin':
        admin = db.query(Admin).filter(Admin.username == username.strip()).first()
        if admin and pwd_context.verify(password.strip(), admin.password):
            authenticated, user_id, target_url, role = True, admin.id, "/admin_dashboard", "admin"
    elif login_type == 'professor':
        professor = db.query(Professor).filter(Professor.username == username.strip()).first()
        if professor and pwd_context.verify(password.strip(), professor.password):
            authenticated, user_id, target_url, role = True, professor.id, "/prof_dashboard", "professor"
    elif login_type == 'student':
        student = db.query(Student).filter(Student.registration == username.strip()).first()
        if student and student.password and pwd_context.verify(password.strip(), student.password):
            authenticated, user_id, target_url, role = True, student.id, "/student_dashboard", "student"

    new_attempt = LoginAttempt(ip_address=ip, username=username, timestamp=now, success=1 if authenticated else 0)
    db.add(new_attempt)
    db.commit()

    if authenticated:
        response = RedirectResponse(url=target_url, status_code=302)
        response.set_cookie(key="session", value="authenticated")
        response.set_cookie(key="role", value=role)
        response.set_cookie(key="user_id", value=str(user_id))
        return response

    return RedirectResponse(url=f"/login?error=1&type={login_type}", status_code=302)

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    for k in ["session", "role", "user_id"]: response.delete_cookie(k)
    return response

# --- DASHBOARDS ---
@app.get("/admin_dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login")
    if db is None: return RedirectResponse(url="/setup")
    
    return templates.TemplateResponse(request=request, name="admin_dashboard.html", context={
        "students": db.query(Student).all(), 
        "professors": db.query(Professor).all(),
        "classes": db.query(Class).all(),
        "admins": db.query(Admin).all(),
        "current_admin": db.query(Admin).filter(Admin.id == request.cookies.get("user_id")).first()
    })

@app.post("/students")
def create_student(request: Request, name: str = Form(...), registration: str = Form(...), course: str = Form(...), db: Session = Depends(get_db)):
    if db:
        new_student = Student(name=name, registration=registration, course=course)
        db.add(new_student)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/professors")
def create_professor_web(request: Request, username: str = Form(...), password: str = Form(...), name: str = Form(...), department: str = Form(...), db: Session = Depends(get_db)):
    if db and not db.query(Professor).filter(Professor.username == username).first():
        db.add(Professor(username=username, password=pwd_context.hash(password), name=name, department=department))
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.get("/prof_dashboard", response_class=HTMLResponse)
def prof_dashboard(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "professor":
        return RedirectResponse(url="/login")
    prof_id = int(request.cookies.get("user_id"))
    is_impersonating = request.cookies.get("impersonator_admin_id") is not None
    return templates.TemplateResponse(request=request, name="prof_dashboard.html", context={
        "professor": db.query(Professor).filter(Professor.id == prof_id).first(),
        "classes": db.query(Class).filter(Class.professor_id == prof_id).all(),
        "is_impersonating": is_impersonating
    })

@app.get("/prof_dashboard/class/{class_id}", response_class=HTMLResponse)
def prof_class_view(request: Request, class_id: int, date: str = "", db: Session = Depends(get_db)):
    prof_id = int(request.cookies.get("user_id"))
    cls = db.query(Class).filter(Class.id == class_id, Class.professor_id == prof_id).first()
    today = date if date else datetime.datetime.now().strftime("%Y-%m-%d")
    absent_ids = [a.student_id for a in db.query(Attendance).filter(Attendance.class_id == class_id, Attendance.date == today).all()]
    is_impersonating = request.cookies.get("impersonator_admin_id") is not None
    return templates.TemplateResponse(request=request, name="prof_class.html", context={
        "cls": cls, "today": today, "absent_student_ids": absent_ids, "is_impersonating": is_impersonating
    })

@app.get("/student_dashboard", response_class=HTMLResponse)
def student_dashboard(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "student":
        return RedirectResponse(url="/login")
    sid = int(request.cookies.get("user_id"))
    is_impersonating = request.cookies.get("impersonator_admin_id") is not None
    return templates.TemplateResponse(request=request, name="student_dashboard.html", context={
        "student": db.query(Student).filter(Student.id == sid).first(), 
        "is_impersonating": is_impersonating
    })

# Outras rotas administrativas (resets e deletes) seguem o mesmo padrão...
@app.post("/students/delete/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    st = db.query(Student).filter(Student.id == student_id).first()
    if st: db.delete(st); db.commit()
    return RedirectResponse(url="/admin_dashboard")

@app.post("/professors/delete/{prof_id}")
def delete_professor(prof_id: int, db: Session = Depends(get_db)):
    p = db.query(Professor).filter(Professor.id == prof_id).first()
    if p: db.delete(p); db.commit()
    return RedirectResponse(url="/admin_dashboard")

@app.post("/classes")
def create_class(name: str = Form(...), professor_id: int = Form(...), student_ids: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    new_class = Class(name=name, professor_id=professor_id)
    new_class.students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    db.add(new_class); db.commit()
    return RedirectResponse(url="/admin_dashboard")

@app.post("/classes/delete/{class_id}")
def delete_class(class_id: int, db: Session = Depends(get_db)):
    c = db.query(Class).filter(Class.id == class_id).first()
    if c: db.delete(c); db.commit()
    return RedirectResponse(url="/admin_dashboard")

@app.post("/prof_dashboard/class/{class_id}/attendance")
def mark_attendance(class_id: int, date: str = Form(...), absent_students: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    db.query(Attendance).filter(Attendance.class_id == class_id, Attendance.date == date).delete()
    for s_id in absent_students:
        db.add(Attendance(student_id=s_id, class_id=class_id, date=date, absent=1))
    db.commit()
    return RedirectResponse(url=f"/prof_dashboard/class/{class_id}?date={date}")

@app.post("/prof_dashboard/class/{class_id}/grade")
def give_grade(class_id: int, student_id: int = Form(...), value: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):
    db.add(Grade(student_id=student_id, class_id=class_id, value=value, description=description))
    db.commit()
    return RedirectResponse(url=f"/prof_dashboard/class/{class_id}")

@app.post("/prof_dashboard/class/{class_id}/grade/delete/{grade_id}")
def delete_grade(class_id: int, grade_id: int, db: Session = Depends(get_db)):
    g = db.query(Grade).filter(Grade.id == grade_id).first()
    if g: db.delete(g); db.commit()
    return RedirectResponse(url=f"/prof_dashboard/class/{class_id}")

# --- NOVAS ROTAS ADMINISTRATIVAS (IMPERSONATE E SENHAS) ---
@app.get("/admin/impersonate/{role}/{user_id}")
def impersonate_user(role: str, user_id: int, request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login")
    
    admin_id = request.cookies.get("user_id")

    if role == "student":
        user = db.query(Student).filter(Student.id == user_id).first()
        target_url = "/student_dashboard"
    elif role == "professor":
        user = db.query(Professor).filter(Professor.id == user_id).first()
        target_url = "/prof_dashboard"
    else:
        return RedirectResponse(url="/admin_dashboard")

    if not user:
        return RedirectResponse(url="/admin_dashboard?error=UserNotFound")

    response = RedirectResponse(url=target_url, status_code=302)
    response.set_cookie(key="session", value="authenticated")
    response.set_cookie(key="role", value=role)
    response.set_cookie(key="user_id", value=str(user_id))
    response.set_cookie(key="impersonator_admin_id", value=str(admin_id))
    return response

@app.get("/admin/stop_impersonate")
def stop_impersonate(request: Request):
    admin_id = request.cookies.get("impersonator_admin_id")
    if not admin_id:
        return RedirectResponse(url="/login")
        
    response = RedirectResponse(url="/admin_dashboard", status_code=302)
    response.set_cookie(key="session", value="authenticated")
    response.set_cookie(key="role", value="admin")
    response.set_cookie(key="user_id", value=str(admin_id))
    response.delete_cookie(key="impersonator_admin_id")
    return response

@app.post("/students/reset_password/{student_id}")
def reset_student_password(student_id: int, request: Request, db: Session = Depends(get_db), new_password: str = Form(...)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login")
    st = db.query(Student).filter(Student.id == student_id).first()
    if st:
        st.password = pwd_context.hash(new_password)
        db.commit()
    return RedirectResponse(url="/admin_dashboard")

@app.post("/professors/reset_password/{prof_id}")
def reset_prof_password(prof_id: int, request: Request, db: Session = Depends(get_db), new_password: str = Form(...)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login")
    p = db.query(Professor).filter(Professor.id == prof_id).first()
    if p:
        p.password = pwd_context.hash(new_password)
        db.commit()
    return RedirectResponse(url="/admin_dashboard")

@app.post("/admin/change_password")
def change_admin_password(request: Request, db: Session = Depends(get_db), new_password: str = Form(...)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login")
    admin_id = request.cookies.get("user_id")
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin:
        admin.password = pwd_context.hash(new_password)
        db.commit()
    return RedirectResponse(url="/admin_dashboard")

