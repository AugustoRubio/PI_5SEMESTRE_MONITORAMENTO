from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import asyncio
import time
import random
import string
import pymysql

router = APIRouter()

simulation_status = {
    "is_running": False,
    "profile": "",
    "target": "",
    "actions_performed": 0,
    "start_time": 0,
    "logs": []
}

class SimConfig(BaseModel):
    db_host: str
    db_port: int
    db_user: str
    db_pass: str
    db_name: str
    profile: str
    duration: int

SIM_MARKER = "[SIM]"

def random_string(length=8):
    return ''.join(random.choices(string.ascii_letters, k=length))

async def perform_simulation(config: SimConfig):
    global simulation_status
    simulation_status["is_running"] = True
    simulation_status["actions_performed"] = 0
    simulation_status["target"] = config.db_host
    simulation_status["profile"] = config.profile
    simulation_status["start_time"] = time.time()
    simulation_status["logs"] = ["Tentando conexão com o banco de dados..."]

    try:
        conn = pymysql.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_pass,
            database=config.db_name,
            port=config.db_port,
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        simulation_status["is_running"] = False
        simulation_status["logs"].insert(0, f"Erro ao conectar: {str(e)}")
        simulation_status["logs"].insert(0, "Simulação abortada.")
        return
        
    simulation_status["logs"].insert(0, "Iniciando simulação completa...")

    delay = 5.0 if config.profile == "calm" else 0.05
    end_time = time.time() + config.duration

    while time.time() < end_time and simulation_status["is_running"]:
        action = random.choice(["create_student", "create_professor", "create_class", "edit", "delete", "enroll_student", "add_grade", "add_attendance"])

        try:
            with conn.cursor() as cursor:
                if action == "create_student":
                    name = f"{SIM_MARKER} Aluno_{random_string(4)}"
                    reg = f"SIM-{random.randint(1000, 99999)}"
                    # Criptografa a senha simulada usando a hash exata que a intranet espera
                    # Para não adicionar a dependência do passlib aqui, pode-se usar um hash bcrypt fixo de 'sim'
                    # ou salvar uma hash gerada previamente. $2b$12$Nq/EwA2/O0bS.u0XgYyKHeH9o.uS2TzRyC.W7lYjZp0Q3Lp9LqXg2 é hash de 'sim'
                    cursor.execute("INSERT INTO students (name, registration, password, course) VALUES (%s, %s, '$2b$12$Nq/EwA2/O0bS.u0XgYyKHeH9o.uS2TzRyC.W7lYjZp0Q3Lp9LqXg2', 'Simulação')", (name, reg))
                    conn.commit()
                    log_msg = f"Criou aluno: {name} (Senha: sim)"

                elif action == "create_professor":
                    name = f"{SIM_MARKER} Prof_{random_string(4)}"
                    usr = f"sim_pr_{random_string(3)}"
                    cursor.execute("INSERT INTO professors (username, password, name, department) VALUES (%s, '$2b$12$Nq/EwA2/O0bS.u0XgYyKHeH9o.uS2TzRyC.W7lYjZp0Q3Lp9LqXg2', %s, 'Simulação')", (usr, name))
                    conn.commit()
                    log_msg = f"Criou professor: {name} (Senha: sim)"

                elif action == "create_class":
                    cursor.execute("SELECT id FROM professors WHERE name LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                    prof = cursor.fetchone()
                    prof_id = prof['id'] if prof else None
                    name = f"{SIM_MARKER} Turma_{random_string(3)}"
                    cursor.execute("INSERT INTO classes (name, professor_id) VALUES (%s, %s)", (name, prof_id))
                    conn.commit()
                    log_msg = f"Criou turma: {name}"

                elif action == "edit":
                    table = random.choice(['students', 'professors', 'classes'])
                    col_name = "username" if table == "professors" else "name"
                    cursor.execute(f"SELECT id, {col_name} FROM {table} WHERE {col_name} LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                    result = cursor.fetchone()
                    if result:
                        new_name = f"{SIM_MARKER} Edit_{random_string(3)}"
                        cursor.execute(f"UPDATE {table} SET {col_name} = %s WHERE id = %s", (new_name, result['id']))
                        conn.commit()
                        log_msg = f"Editou {table} ID {result['id']} -> {new_name}"
                    else:
                        log_msg = f"Tentou editar {table}, mas nada encontrado."

                elif action == "delete":
                    table = random.choice(['students', 'professors', 'classes'])
                    col_name = "username" if table == "professors" else "name"
                    cursor.execute(f"SELECT id FROM {table} WHERE {col_name} LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                    result = cursor.fetchone()
                    if result:
                        try:
                            cursor.execute(f"DELETE FROM {table} WHERE id = %s", (result['id'],))
                            conn.commit()
                            log_msg = f"Deletou de {table} ID {result['id']}"
                        except:
                            log_msg = f"Ignorado erro de FK ao deletar {table} ID {result['id']}"
                    else:
                        log_msg = f"Tentou deletar {table}, mas nada encontrado."

                elif action == "enroll_student":
                    cursor.execute("SELECT id FROM students WHERE name LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                    st = cursor.fetchone()
                    cursor.execute("SELECT id FROM classes WHERE name LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                    cls = cursor.fetchone()
                    if st and cls:
                        st_id, cls_id = st['id'], cls['id']
                        cursor.execute("SELECT * FROM student_class WHERE student_id=%s AND class_id=%s", (st_id, cls_id))
                        if not cursor.fetchone():
                            cursor.execute("INSERT INTO student_class (student_id, class_id) VALUES (%s, %s)", (st_id, cls_id))
                            conn.commit()
                            log_msg = f"Vinculou Estudante ID {st_id} à Turma ID {cls_id}"
                        else:
                            log_msg = "Vínculo já existente, ignorado."
                    else:
                        log_msg = "Tentou vincular aluno a turma, mas faltam dados."

                elif action == "add_grade":
                    cursor.execute("""
                        SELECT sc.student_id, sc.class_id 
                        FROM student_class sc
                        JOIN students s ON sc.student_id = s.id 
                        WHERE s.name LIKE %s 
                        ORDER BY RAND() LIMIT 1
                    """, (f"{SIM_MARKER}%",))
                    rel = cursor.fetchone()
                    if rel:
                        grade_val = str(round(random.uniform(2.0, 10.0), 1))
                        desc = random.choice(["Prova 1", "Prova 2", "Trabalho", "Seminário", "Projeto Final"])
                        cursor.execute("INSERT INTO grades (student_id, class_id, value, description) VALUES (%s, %s, %s, %s)", 
                                       (rel['student_id'], rel['class_id'], grade_val, desc))
                        conn.commit()
                        log_msg = f"Lançou nota {grade_val} para Aluno ID {rel['student_id']} (Turma {rel['class_id']})"
                    else:
                        log_msg = "Tentou lançar nota, mas nenhum aluno matriculado."

                elif action == "add_attendance":
                    cursor.execute("""
                        SELECT sc.student_id, sc.class_id 
                        FROM student_class sc
                        JOIN students s ON sc.student_id = s.id 
                        WHERE s.name LIKE %s 
                        ORDER BY RAND() LIMIT 1
                    """, (f"{SIM_MARKER}%",))
                    rel = cursor.fetchone()
                    if rel:
                        date_str = f"2026-03-{random.randint(1,28):02d}"
                        cursor.execute("INSERT INTO attendances (student_id, class_id, date, absent) VALUES (%s, %s, %s, 1)", 
                                       (rel['student_id'], rel['class_id'], date_str))
                        conn.commit()
                        log_msg = f"Registrou falta para Aluno ID {rel['student_id']} (Turma {rel['class_id']})"
                    else:
                        log_msg = "Tentou registrar falta, mas nenhum aluno matriculado."

                simulation_status["actions_performed"] += 1
                simulation_status["logs"].insert(0, log_msg)

                if len(simulation_status["logs"]) > 15:
                    simulation_status["logs"].pop()
        except Exception as e:
            simulation_status["logs"].insert(0, f"Falha na ação: {str(e)}")
            if len(simulation_status["logs"]) > 15:
                simulation_status["logs"].pop()
            
        await asyncio.sleep(delay)

    if conn and conn.open:
        conn.close()
    
    simulation_status["is_running"] = False
    simulation_status["logs"].insert(0, "Simulação finalizada.")

@router.post("/start")
async def start_sim(config: SimConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    global simulation_status
    
    if simulation_status["is_running"]:
        if time.time() > (simulation_status["start_time"] + simulation_status.get("duration", 3600)):
            simulation_status["is_running"] = False
        else:
            raise HTTPException(status_code=400, detail="Simulação já em execução.")
            
    # Guarda o tempo exato para destrancar timeout
    simulation_status["duration"] = config.duration        
    background_tasks.add_task(perform_simulation, config)
    return {"message": "Simulação iniciada."}

@router.post("/stop")
async def stop_sim(current_user: dict = Depends(get_current_user)):
    global simulation_status
    if not simulation_status["is_running"]:
        return {"message": "Nenhuma simulação rodando."}
    simulation_status["is_running"] = False
    return {"message": "Sinal de parada enviado."}

@router.post("/clear_simulated_data")
async def clear_simulated_data(config: SimConfig, current_user: dict = Depends(get_current_user)):
    try:
        conn = pymysql.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_pass,
            database=config.db_name,
            port=config.db_port
        )
        
        with conn.cursor() as cursor:
            # Apaga primeiro turmas pq têm chave pros professores
            cursor.execute("DELETE FROM classes WHERE name LIKE %s", (f"{SIM_MARKER}%",))
            d_classes = cursor.rowcount
            
            cursor.execute("DELETE FROM professors WHERE username LIKE %s OR name LIKE %s", (f"{SIM_MARKER}%", f"{SIM_MARKER}%"))
            d_prof = cursor.rowcount
            
            cursor.execute("DELETE FROM students WHERE name LIKE %s", (f"{SIM_MARKER}%",))
            d_stud = cursor.rowcount
            
            conn.commit()
            
        conn.close()
        return {"message": f"Limpeza feita: {d_classes} Turmas, {d_prof} Professores e {d_stud} Estudantes."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_sim_status(current_user: dict = Depends(get_current_user)):
    global simulation_status
    if simulation_status["is_running"] and simulation_status["start_time"] > 0:
        if len(simulation_status["logs"]) > 0 and "finalizada" in simulation_status["logs"][0]:
            simulation_status["is_running"] = False
    return simulation_status
