import sys

# Script seguro para trocar o arquivo inteiro. Em routers o estado eh mantido globalmente e precisa limpar as variaveis corretamente.

content = '''from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
    simulation_status["logs"] = ["Iniciando simula��o..."]

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
        simulation_status["logs"].append(f"Erro ao conectar no banco: {str(e)}")
        return

    delay = 5.0 if config.profile == "calm" else 0.5
    end_time = time.time() + config.duration

    while time.time() < end_time and simulation_status["is_running"]:
        action = random.choice(["create_student", "create_professor", "create_class", "edit", "delete"])

        try:
            with conn.cursor() as cursor:
                if action == "create_student":
                    name = f"{SIM_MARKER} Aluno_{random_string(4)}"
                    reg = f"SIM-{random.randint(1000, 99999)}"
                    course = "Simulação"
                    cursor.execute("INSERT INTO students (name, registration, course) VALUES (%s, %s, %s)", (name, reg, course))
                    conn.commit()
                    log_msg = f"Criou aluno: {name}"

                elif action == "create_professor":
                    name = f"{SIM_MARKER} Prof_{random_string(4)}"
                    usr = f"sim_prof_{random_string(3)}"
                    pwd = "sim"
                    dep = "Simulação"
                    cursor.execute("INSERT INTO professors (username, password, name, department) VALUES (%s, %s, %s, %s)", (usr, pwd, name, dep))
                    conn.commit()
                    log_msg = f"Criou professor: {name}"

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
                    col_name = "username" if table == "professors" else "name" # Usa a coluna certa
                    cursor.execute(f"SELECT id, {col_name} FROM {table} WHERE {col_name} LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                    result = cursor.fetchone()
                    if result:
                        new_name = f"{SIM_MARKER} Edit_{random_string(3)}"
                        cursor.execute(f"UPDATE {table} SET {col_name} = %s WHERE id = %s", (new_name, result['id']))
                        conn.commit()
                        log_msg = f"Editou {table} ID {result['id']} -> {new_name}"
                    else:
                        log_msg = f"Tentou editar {table}, mas nenhum simulado encontrado."

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
                            log_msg = f"Ignorado erro de Foreign Key ao deletar {table} ID {result['id']}"
                    else:
                        log_msg = f"Tentou deletar {table}, mas nenhum simulado encontrado."

                simulation_status["actions_performed"] += 1
                simulation_status["logs"].insert(0, log_msg)

                if len(simulation_status["logs"]) > 15:
                    simulation_status["logs"].pop()
        except Exception as e:
            simulation_status["logs"].insert(0, f"Erro na ação {action}: {str(e)}")
            
        await asyncio.sleep(delay)

    if conn and conn.open:
        conn.close()
    
    simulation_status["is_running"] = False
    simulation_status["logs"].insert(0, "Simulação finalizada.")

@router.post("/start")
async def start_sim(config: SimConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    global simulation_status
    
    # O timeout do FastAPI pode deixar is_running travado em true se matar mal. Garantir reset se tempo estourou.
    if simulation_status["is_running"]:
        if time.time() > (simulation_status["start_time"] + 3600): # Trava de seguran�a 1h
            simulation_status["is_running"] = False
        else:
            raise HTTPException(status_code=400, detail="Simulação já em execução.")
            
    background_tasks.add_task(perform_simulation, config)
    return {"message": "Simulação de Uso iniciada no background."}

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
            # Apaga na ordem correta para evitar erros de FK
            cursor.execute("DELETE FROM classes WHERE name LIKE %s", (f"{SIM_MARKER}%",))
            deleted_classes = cursor.rowcount
            
            cursor.execute("DELETE FROM professors WHERE username LIKE %s OR name LIKE %s", (f"{SIM_MARKER}%", f"{SIM_MARKER}%"))
            deleted_professors = cursor.rowcount
            
            cursor.execute("DELETE FROM students WHERE name LIKE %s", (f"{SIM_MARKER}%",))
            deleted_students = cursor.rowcount
            
            conn.commit()
            
        conn.close()
        return {"message": f"Limpeza concluída: {deleted_classes} Turmas, {deleted_professors} Professores e {deleted_students} Estudantes simulados foram removidos!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao limpar dados: {str(e)}")

@router.get("/status")
async def get_sim_status(current_user: dict = Depends(get_current_user)):
    global simulation_status
    # Auto-restaurar estado caso tenha parado silenciosamente
    if simulation_status["is_running"] and simulation_status["start_time"] > 0:
        # Se os logs indicam que parou, mas a var bool ta presa
        if len(simulation_status["logs"]) > 0 and "finalizada" in simulation_status["logs"][0]:
            simulation_status["is_running"] = False
            
    return simulation_status
'''

open('web_panel/app/routers/simulation.py', 'w', encoding='utf-8').write(content)
