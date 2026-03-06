from fastapi import FastAPI, Request, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from dotenv import load_dotenv
import os
import time
import random
import datetime

import urllib.parse
from passlib.context import CryptContext

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
        temp_engine = create_engine(db_url, pool_pre_ping=True)
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
            # Forçar atualização da senha para garantir que está com hash (caso tenha vindo de versão anterior em clear text)
            admin.password = hashed_pwd
            db.commit()
        db.close()
        
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
    safe_pass = urllib.parse.quote_plus(DB_PASSWORD)
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{safe_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    init_db(SQLALCHEMY_DATABASE_URL)

app = FastAPI(title="Intranet Faculdade")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Middleware para redirecionar para a página de setup
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
def setup_get(request: Request):
    if DB_CONFIGURED:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
def setup_post(request: Request, db_host: str = Form(...), db_port: str = Form(...), db_user: str = Form(...), db_pass: str = Form(...), db_name: str = Form(...)):
    safe_pass = urllib.parse.quote_plus(db_pass)
    db_url = f"mysql+pymysql://{db_user}:{safe_pass}@{db_host}:{db_port}/{db_name}"
    success, msg = init_db(db_url)
    
    if success:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        with open(env_path, "w") as f:
            f.write(f"DB_HOST={db_host}\nDB_PORT={db_port}\nDB_USER={db_user}\nDB_PASSWORD={db_pass}\nDB_NAME={db_name}\n")
        return RedirectResponse(url="/login", status_code=303)
    else:
        form_data = {"db_host": db_host, "db_port": db_port, "db_user": db_user, "db_name": db_name, "db_pass": db_pass}
        return templates.TemplateResponse("setup.html", {"request": request, "error": f"Erro ao conectar: {msg}", "form_data": form_data})

# --- ROTAS FRONTEND ---
@app.get("/", response_class=HTMLResponse)
def root_redirect(request: Request):
    if DB_CONFIGURED:
        return templates.TemplateResponse("index.html", {"request": request})
    return RedirectResponse(url="/setup", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, type: str = "admin"):
    return templates.TemplateResponse("login.html", {"request": request, "type": type})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), login_type: str = Form(...), db: Session = Depends(get_db)):
    ip = request.client.host
    now = int(time.time())
    
    # Check for block (5 failures in last 60 seconds)
    recent_failures = db.query(LoginAttempt).filter(
        LoginAttempt.ip_address == ip,
        LoginAttempt.success == 0,
        LoginAttempt.timestamp > now - 60
    ).count()
    
    if recent_failures >= 5:
        # Record attempt even if blocked to prolong the block if they keep trying
        new_attempt = LoginAttempt(ip_address=ip, username=username, timestamp=now, success=0)
        db.add(new_attempt)
        db.commit()
        return RedirectResponse(url=f"/login?error=blocked&type={login_type}", status_code=302)

    authenticated = False
    user_id = None

    if login_type == 'admin':
        clean_user = username.strip()
        admin = db.query(Admin).filter(Admin.username == clean_user).first()
        if admin and pwd_context.verify(password.strip(), admin.password):
            authenticated = True
            user_id = admin.id
            target_url = "/admin_dashboard"
            role = "admin"
    elif login_type == 'professor':
        clean_user = username.strip()
        professor = db.query(Professor).filter((Professor.username == clean_user) | (Professor.name == clean_user)).first()
        if professor and pwd_context.verify(password.strip(), professor.password):
            authenticated = True
            user_id = professor.id
            target_url = "/prof_dashboard"
            role = "professor"
    elif login_type == 'student':
        clean_user = username.strip()
        student = db.query(Student).filter((Student.registration == clean_user) | (Student.name == clean_user)).first()
        if student and student.password and pwd_context.verify(password.strip(), student.password):
            authenticated = True
            user_id = student.id
            target_url = "/student_dashboard"
            role = "student"

    # Record attempt
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

@app.get("/security/metrics")
def security_metrics(db: Session = Depends(get_db)):
    now = int(time.time())
    total_failures = db.query(LoginAttempt).filter(LoginAttempt.success == 0).count()
    failures_last_hour = db.query(LoginAttempt).filter(LoginAttempt.success == 0, LoginAttempt.timestamp > now - 3600).count()
    
    # Group by IP to see who is currently "blocked" or "active"
    # This is simplified for the API
    active_ips = db.query(LoginAttempt.ip_address).filter(LoginAttempt.timestamp > now - 300).distinct().count()
    
    # Get last 10 failed attempts for the dashboard
    recent_logs = db.query(LoginAttempt).filter(LoginAttempt.success == 0).order_by(LoginAttempt.timestamp.desc()).limit(10).all()
    logs = [{"ip": l.ip_address, "user": l.username, "time": datetime.datetime.fromtimestamp(l.timestamp).strftime("%H:%M:%S")} for l in recent_logs]

    return {
        "total_failures": total_failures,
        "failures_last_hour": failures_last_hour,
        "active_ips": active_ips,
        "recent_failed_attempts": logs,
        "system_time": now
    }

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    response.delete_cookie("role")
    response.delete_cookie("user_id")
    return response

# --- ADMIN DASHBOARD ---
@app.get("/admin_dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    students = db.query(Student).all()
    professors = db.query(Professor).all()
    classes = db.query(Class).all()
    admins = db.query(Admin).all()
    admin_id = request.cookies.get("user_id")
    current_admin = db.query(Admin).filter(Admin.id == admin_id).first()
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "students": students, 
        "professors": professors,
        "classes": classes,
        "admins": admins,
        "current_admin": current_admin
    })

@app.post("/admin/change_password")
def change_admin_password(request: Request, new_password: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    admin_id = request.cookies.get("user_id")
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin:
        admin.password = pwd_context.hash(new_password)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/students")
def create_student(request: Request, name: str = Form(...), registration: str = Form(...), course: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse(url="/login", status_code=302)
    
    if not db.query(Student).filter(Student.registration == registration).first():
        new_student = Student(name=name, registration=registration, course=course)
        db.add(new_student)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/students/reset_password/{student_id}")
def reset_student_password(request: Request, student_id: int, new_password: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login?type=admin", status_code=302)
    st = db.query(Student).filter(Student.id == student_id).first()
    if st:
        st.password = pwd_context.hash(new_password)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.get("/admin/impersonate/student/{student_id}")
def impersonate_student(request: Request, student_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login?type=admin", status_code=302)
    st = db.query(Student).filter(Student.id == student_id).first()
    if st:
        response = RedirectResponse(url="/student_dashboard", status_code=302)
        response.set_cookie(key="session", value="authenticated")
        response.set_cookie(key="role", value="student")
        response.set_cookie(key="user_id", value=str(st.id))
        return response
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/students/delete/{student_id}")
def delete_student(request: Request, student_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    st = db.query(Student).filter(Student.id == student_id).first()
    if st:
        db.delete(st)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/professors")
def create_professor_web(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...), 
    name: str = Form(...), 
    department: str = Form(...), 
    db: Session = Depends(get_db)
):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    if not db.query(Professor).filter(Professor.username == username).first():
        new_prof = Professor(username=username, password=pwd_context.hash(password), name=name, department=department)
        db.add(new_prof)
        db.commit()

    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/professors/reset_password/{prof_id}")
def reset_professor_password(request: Request, prof_id: int, new_password: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login?type=admin", status_code=302)
    prof = db.query(Professor).filter(Professor.id == prof_id).first()
    if prof:
        prof.password = pwd_context.hash(new_password)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.get("/admin/impersonate/professor/{prof_id}")
def impersonate_professor(request: Request, prof_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login?type=admin", status_code=302)
    prof = db.query(Professor).filter(Professor.id == prof_id).first()
    if prof:
        response = RedirectResponse(url="/prof_dashboard", status_code=302)
        response.set_cookie(key="session", value="authenticated")
        response.set_cookie(key="role", value="professor")
        response.set_cookie(key="user_id", value=str(prof.id))
        return response
    return RedirectResponse(url="/admin_dashboard", status_code=302)


@app.post("/professors/delete/{prof_id}")
def delete_professor_web(request: Request, prof_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    prof = db.query(Professor).filter(Professor.id == prof_id).first()
    if prof:
        db.delete(prof)
        db.commit()
        
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/classes")
def create_class(request: Request, name: str = Form(...), professor_id: int = Form(...), student_ids: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    new_class = Class(name=name, professor_id=professor_id)
    students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    new_class.students = students
    db.add(new_class)
    db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/classes/delete/{class_id}")
def delete_class(request: Request, class_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    cls = db.query(Class).filter(Class.id == class_id).first()
    if cls:
        db.delete(cls)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

# --- PROFESSOR DASHBOARD ---
@app.get("/prof_dashboard", response_class=HTMLResponse)
def prof_dashboard(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "professor":
        return RedirectResponse(url="/login", status_code=302)
    
    prof_id = int(request.cookies.get("user_id"))
    professor = db.query(Professor).filter(Professor.id == prof_id).first()
    classes = db.query(Class).filter(Class.professor_id == prof_id).all()
    
    return templates.TemplateResponse("prof_dashboard.html", {
        "request": request, 
        "professor": professor,
        "classes": classes
    })

@app.get("/prof_dashboard/class/{class_id}", response_class=HTMLResponse)
def prof_class_view(request: Request, class_id: int, date: str = "", db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "professor":
        return RedirectResponse(url="/login", status_code=302)
    
    prof_id = int(request.cookies.get("user_id"))
    cls = db.query(Class).filter(Class.id == class_id, Class.professor_id == prof_id).first()
    if not cls:
        return RedirectResponse(url="/prof_dashboard", status_code=302)

    today = date if date else datetime.datetime.now().strftime("%Y-%m-%d")
    attendances_today = db.query(Attendance).filter(Attendance.class_id == class_id, Attendance.date == today).all()
    absent_student_ids = [a.student_id for a in attendances_today]

    return templates.TemplateResponse("prof_class.html", {
        "request": request, 
        "cls": cls,
        "today": today,
        "absent_student_ids": absent_student_ids
    })

@app.post("/prof_dashboard/class/{class_id}/attendance")
def mark_attendance(request: Request, class_id: int, date: str = Form(...), absent_students: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "professor":
        return RedirectResponse(url="/login", status_code=302)
    
    prof_id = int(request.cookies.get("user_id"))
    cls = db.query(Class).filter(Class.id == class_id, Class.professor_id == prof_id).first()
    if not cls:
        return RedirectResponse(url="/prof_dashboard", status_code=302)
    
    # Remove old attendance
    db.query(Attendance).filter(Attendance.class_id == class_id, Attendance.date == date).delete()
    
    # Insert new absences
    for s_id in absent_students:
        att = Attendance(student_id=s_id, class_id=class_id, date=date, absent=1)
        db.add(att)
        
    db.commit()
    return RedirectResponse(url=f"/prof_dashboard/class/{class_id}?date={date}", status_code=302)
# --- STUDENT DASHBOARD ---

@app.get("/student_dashboard", response_class=HTMLResponse)

async def student_dashboard(request: Request, db: Session = Depends(get_db)):

    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "student":

        return RedirectResponse(url="/login", status_code=302)

    student_id = int(request.cookies.get("user_id"))

    student = db.query(Student).filter(Student.id == student_id).first()

    if not student:

        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("student_dashboard.html", {"request": request, "student": student})



# --- GRADES (Professor side) ---

@app.post("/prof_dashboard/class/{class_id}/grade")

async def give_grade(request: Request, class_id: int, student_id: int = Form(...), value: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):

    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "professor":

        return RedirectResponse(url="/login", status_code=302)

    prof_id = int(request.cookies.get("user_id"))

    cls = db.query(Class).filter(Class.id == class_id, Class.professor_id == prof_id).first()

    if not cls:

        return RedirectResponse(url="/prof_dashboard", status_code=302)

    grade = Grade(student_id=student_id, class_id=class_id, value=value, description=description)

    db.add(grade)

    db.commit()

    return RedirectResponse(url=f"/prof_dashboard/class/{class_id}", status_code=302)



@app.post("/prof_dashboard/class/{class_id}/grade/delete/{grade_id}")

async def delete_grade(request: Request, class_id: int, grade_id: int, db: Session = Depends(get_db)):

    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "professor":

        return RedirectResponse(url="/login", status_code=302)

    prof_id = int(request.cookies.get("user_id"))

    cls = db.query(Class).filter(Class.id == class_id, Class.professor_id == prof_id).first()

    if not cls:

        return RedirectResponse(url="/prof_dashboard", status_code=302)

    grade = db.query(Grade).filter(Grade.id == grade_id, Grade.class_id == class_id).first()

    if grade:

        db.delete(grade)

        db.commit()

    return RedirectResponse(url=f"/prof_dashboard/class/{class_id}", status_code=302)

