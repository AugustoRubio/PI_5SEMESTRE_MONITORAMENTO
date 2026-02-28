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

def random_string(length=8):
    return ''.join(random.choices(string.ascii_letters, k=length))

async def perform_simulation(config: SimConfig):
    global simulation_status
    simulation_status["is_running"] = True
    simulation_status["actions_performed"] = 0
    simulation_status["target"] = config.db_host
    simulation_status["profile"] = config.profile
    simulation_status["start_time"] = time.time()
    simulation_status["logs"] = []

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
        action = random.choice(["create", "edit", "delete"])
        
        try:
            with conn.cursor() as cursor:
                if action == "create":
                    name = f"Simulado_{random_string(4)}"
                    reg = f"SIM-{random.randint(1000, 9999)}"
                    course = "Simulação"
                    cursor.execute("INSERT INTO students (name, registration, course) VALUES (%s, %s, %s)", (name, reg, course))
                    conn.commit()
                    log_msg = f"Criou aluno: {name}"

                elif action == "edit":
                    cursor.execute("SELECT id FROM students WHERE name LIKE 'Simulado_%' ORDER BY RAND() LIMIT 1")
                    result = cursor.fetchone()
                    if result:
                        new_course = f"Curso {random_string(3)}"
                        cursor.execute("UPDATE students SET course = %s WHERE id = %s", (new_course, result['id']))
                        conn.commit()
                        log_msg = f"Editou aluno ID {result['id']} -> novo curso: {new_course}"
                    else:
                        log_msg = "Tentou editar, mas nenhum aluno simulado foi encontrado."

                elif action == "delete":
                    cursor.execute("SELECT id FROM students WHERE name LIKE 'Simulado_%' ORDER BY RAND() LIMIT 1")
                    result = cursor.fetchone()
                    if result:
                        cursor.execute("DELETE FROM students WHERE id = %s", (result['id'],))
                        conn.commit()
                        log_msg = f"Deletou aluno ID {result['id']}"
                    else:
                        log_msg = "Tentou deletar, mas nenhum aluno simulado foi encontrado."

                simulation_status["actions_performed"] += 1
                simulation_status["logs"].insert(0, log_msg)
                
                if len(simulation_status["logs"]) > 15:
                    simulation_status["logs"].pop()
        except Exception as e:
            simulation_status["logs"].insert(0, f"Erro na ação {action}: {str(e)}")

        await asyncio.sleep(delay)

    conn.close()
    simulation_status["is_running"] = False
    simulation_status["logs"].insert(0, "Simulação finalizada.")

@router.post("/start")
async def start_sim(config: SimConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    global simulation_status
    if simulation_status["is_running"]:
        raise HTTPException(status_code=400, detail="Simulação jÃ¡ em execuÃ§Ã£o.")
    
    background_tasks.add_task(perform_simulation, config)
    return {"message": "Simulação de Uso iniciada no background."}

@router.post("/stop")
async def stop_sim(current_user: dict = Depends(get_current_user)):
    global simulation_status
    if not simulation_status["is_running"]:
        return {"message": "Nenhuma simulação rodando."}
    simulation_status["is_running"] = False
    return {"message": "Sinal de parada enviado."}

@router.get("/status")
async def get_sim_status(current_user: dict = Depends(get_current_user)):
    return simulation_status