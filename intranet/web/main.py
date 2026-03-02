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
async def setup_get(request: Request):
    if DB_CONFIGURED:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("setup.html", {"request": request})

@app.post("/setup")
async def setup_post(request: Request, db_host: str = Form(...), db_port: str = Form(...), db_user: str = Form(...), db_pass: str = Form(...), db_name: str = Form(...)):
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
async def root_redirect(request: Request):
    if DB_CONFIGURED:
        return templates.TemplateResponse("index.html", {"request": request})
    return RedirectResponse(url="/setup", status_code=302)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, type: str = "admin"):
    return templates.TemplateResponse("login.html", {"request": request, "type": type})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...), login_type: str = Form(...), db: Session = Depends(get_db)):
    if login_type == 'admin':
        admin = db.query(Admin).filter(Admin.username == username).first()
        if admin and pwd_context.verify(password, admin.password):
            response = RedirectResponse(url="/admin_dashboard", status_code=302)
            response.set_cookie(key="session", value="authenticated")
            response.set_cookie(key="role", value="admin")
            response.set_cookie(key="user_id", value=str(admin.id))
            return response
    elif login_type == 'professor':
        professor = db.query(Professor).filter(Professor.username == username).first()
        if professor and pwd_context.verify(password, professor.password):
            response = RedirectResponse(url="/prof_dashboard", status_code=302)
            response.set_cookie(key="session", value="authenticated")
            response.set_cookie(key="role", value="professor")
            response.set_cookie(key="user_id", value=str(professor.id))
            return response
    elif login_type == 'student':
        student = db.query(Student).filter(Student.registration == username).first()
        if student and student.password and pwd_context.verify(password, student.password):
            response = RedirectResponse(url="/student_dashboard", status_code=302)
            response.set_cookie(key="session", value="authenticated")
            response.set_cookie(key="role", value="student")
            response.set_cookie(key="user_id", value=str(student.id))
            return response

    return RedirectResponse(url=f"/login?error=1&type={login_type}", status_code=302)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    response.delete_cookie("role")
    response.delete_cookie("user_id")
    return response

# --- ADMIN DASHBOARD ---
@app.get("/admin_dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
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
async def change_admin_password(request: Request, new_password: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    admin_id = request.cookies.get("user_id")
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin:
        admin.password = pwd_context.hash(new_password)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/students")
async def create_student(request: Request, name: str = Form(...), registration: str = Form(...), course: str = Form(...), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated":
        return RedirectResponse(url="/login", status_code=302)
    
    if not db.query(Student).filter(Student.registration == registration).first():
        new_student = Student(name=name, registration=registration, course=course)
        db.add(new_student)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/students/delete/{student_id}")
async def delete_student(request: Request, student_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    st = db.query(Student).filter(Student.id == student_id).first()
    if st:
        db.delete(st)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/professors")
async def create_professor_web(
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

@app.post("/professors/delete/{prof_id}")
async def delete_professor_web(request: Request, prof_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    prof = db.query(Professor).filter(Professor.id == prof_id).first()
    if prof:
        db.delete(prof)
        db.commit()
        
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/classes")
async def create_class(request: Request, name: str = Form(...), professor_id: int = Form(...), student_ids: list[int] = Form(default=[]), db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    new_class = Class(name=name, professor_id=professor_id)
    students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    new_class.students = students
    db.add(new_class)
    db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

@app.post("/classes/delete/{class_id}")
async def delete_class(request: Request, class_id: int, db: Session = Depends(get_db)):
    if request.cookies.get("session") != "authenticated" or request.cookies.get("role") != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    cls = db.query(Class).filter(Class.id == class_id).first()
    if cls:
        db.delete(cls)
        db.commit()
    return RedirectResponse(url="/admin_dashboard", status_code=302)

# --- PROFESSOR DASHBOARD ---
@app.get("/prof_dashboard", response_class=HTMLResponse)
async def prof_dashboard(request: Request, db: Session = Depends(get_db)):
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
async def prof_class_view(request: Request, class_id: int, date: str = "", db: Session = Depends(get_db)):
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
async def mark_attendance(request: Request, class_id: int, date: str = Form(...), absent_students: list[int] = Form(default=[]), db: Session = Depends(get_db)):
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
#   - - -   S T U D E N T   D A S H B O A R D   - - -  
 @ a p p . g e t ( " / s t u d e n t _ d a s h b o a r d " ,   r e s p o n s e _ c l a s s = H T M L R e s p o n s e )  
 a s y n c   d e f   s t u d e n t _ d a s h b o a r d ( r e q u e s t :   R e q u e s t ,   d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) ) :  
         i f   r e q u e s t . c o o k i e s . g e t ( " s e s s i o n " )   ! =   " a u t h e n t i c a t e d "   o r   r e q u e s t . c o o k i e s . g e t ( " r o l e " )   ! =   " s t u d e n t " :  
                 r e t u r n   R e d i r e c t R e s p o n s e ( u r l = " / l o g i n " ,   s t a t u s _ c o d e = 3 0 2 )  
         s t u d e n t _ i d   =   i n t ( r e q u e s t . c o o k i e s . g e t ( " u s e r _ i d " ) )  
         s t u d e n t   =   d b . q u e r y ( S t u d e n t ) . f i l t e r ( S t u d e n t . i d   = =   s t u d e n t _ i d ) . f i r s t ( )  
         i f   n o t   s t u d e n t :  
                 r e t u r n   R e d i r e c t R e s p o n s e ( u r l = " / l o g i n " ,   s t a t u s _ c o d e = 3 0 2 )  
         r e t u r n   t e m p l a t e s . T e m p l a t e R e s p o n s e ( " s t u d e n t _ d a s h b o a r d . h t m l " ,   { " r e q u e s t " :   r e q u e s t ,   " s t u d e n t " :   s t u d e n t } )  
  
 #   - - -   G R A D E S   ( P r o f e s s o r   s i d e )   - - -  
 @ a p p . p o s t ( " / p r o f _ d a s h b o a r d / c l a s s / { c l a s s _ i d } / g r a d e " )  
 a s y n c   d e f   g i v e _ g r a d e ( r e q u e s t :   R e q u e s t ,   c l a s s _ i d :   i n t ,   s t u d e n t _ i d :   i n t   =   F o r m ( . . . ) ,   v a l u e :   s t r   =   F o r m ( . . . ) ,   d e s c r i p t i o n :   s t r   =   F o r m ( . . . ) ,   d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) ) :  
         i f   r e q u e s t . c o o k i e s . g e t ( " s e s s i o n " )   ! =   " a u t h e n t i c a t e d "   o r   r e q u e s t . c o o k i e s . g e t ( " r o l e " )   ! =   " p r o f e s s o r " :  
                 r e t u r n   R e d i r e c t R e s p o n s e ( u r l = " / l o g i n " ,   s t a t u s _ c o d e = 3 0 2 )  
         p r o f _ i d   =   i n t ( r e q u e s t . c o o k i e s . g e t ( " u s e r _ i d " ) )  
         c l s   =   d b . q u e r y ( C l a s s ) . f i l t e r ( C l a s s . i d   = =   c l a s s _ i d ,   C l a s s . p r o f e s s o r _ i d   = =   p r o f _ i d ) . f i r s t ( )  
         i f   n o t   c l s :  
                 r e t u r n   R e d i r e c t R e s p o n s e ( u r l = " / p r o f _ d a s h b o a r d " ,   s t a t u s _ c o d e = 3 0 2 )  
         g r a d e   =   G r a d e ( s t u d e n t _ i d = s t u d e n t _ i d ,   c l a s s _ i d = c l a s s _ i d ,   v a l u e = v a l u e ,   d e s c r i p t i o n = d e s c r i p t i o n )  
         d b . a d d ( g r a d e )  
         d b . c o m m i t ( )  
         r e t u r n   R e d i r e c t R e s p o n s e ( u r l = f " / p r o f _ d a s h b o a r d / c l a s s / { c l a s s _ i d } " ,   s t a t u s _ c o d e = 3 0 2 )  
  
 @ a p p . p o s t ( " / p r o f _ d a s h b o a r d / c l a s s / { c l a s s _ i d } / g r a d e / d e l e t e / { g r a d e _ i d } " )  
 a s y n c   d e f   d e l e t e _ g r a d e ( r e q u e s t :   R e q u e s t ,   c l a s s _ i d :   i n t ,   g r a d e _ i d :   i n t ,   d b :   S e s s i o n   =   D e p e n d s ( g e t _ d b ) ) :  
         i f   r e q u e s t . c o o k i e s . g e t ( " s e s s i o n " )   ! =   " a u t h e n t i c a t e d "   o r   r e q u e s t . c o o k i e s . g e t ( " r o l e " )   ! =   " p r o f e s s o r " :  
                 r e t u r n   R e d i r e c t R e s p o n s e ( u r l = " / l o g i n " ,   s t a t u s _ c o d e = 3 0 2 )  
         p r o f _ i d   =   i n t ( r e q u e s t . c o o k i e s . g e t ( " u s e r _ i d " ) )  
         c l s   =   d b . q u e r y ( C l a s s ) . f i l t e r ( C l a s s . i d   = =   c l a s s _ i d ,   C l a s s . p r o f e s s o r _ i d   = =   p r o f _ i d ) . f i r s t ( )  
         i f   n o t   c l s :  
                 r e t u r n   R e d i r e c t R e s p o n s e ( u r l = " / p r o f _ d a s h b o a r d " ,   s t a t u s _ c o d e = 3 0 2 )  
         g r a d e   =   d b . q u e r y ( G r a d e ) . f i l t e r ( G r a d e . i d   = =   g r a d e _ i d ,   G r a d e . c l a s s _ i d   = =   c l a s s _ i d ) . f i r s t ( )  
         i f   g r a d e :  
                 d b . d e l e t e ( g r a d e )  
                 d b . c o m m i t ( )  
         r e t u r n   R e d i r e c t R e s p o n s e ( u r l = f " / p r o f _ d a s h b o a r d / c l a s s / { c l a s s _ i d } " ,   s t a t u s _ c o d e = 3 0 2 )  
 