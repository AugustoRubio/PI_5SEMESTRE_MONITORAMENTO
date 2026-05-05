from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import asyncio
import time
import random
import string
import aiomysql

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
    simulation_status["logs"] = ["Tentando conexão ASSÍNCRONA com o banco de dados..."]

    try:
        # Usamos pool para ser mais robusto sob carga
        pool = await aiomysql.create_pool(
            host=config.db_host,
            user=config.db_user,
            password=config.db_pass,
            db=config.db_name,
            port=config.db_port,
            autocommit=True,
            minsize=1, maxsize=10,
            connect_timeout=5
        )
    except Exception as e:
        simulation_status["is_running"] = False
        simulation_status["logs"].insert(0, f"Erro ao conectar (aiomysql): {str(e)}")
        simulation_status["logs"].insert(0, "Simulação abortada.")
        return
        
    simulation_status["logs"].insert(0, "Iniciando simulação assíncrona agressiva...")

    delay = 1.0 if config.profile == "calm" else 0.01
    batch_size = 1 if config.profile == "calm" else 30
    end_time = time.time() + config.duration

    while time.time() < end_time and simulation_status["is_running"]:
        actions_in_this_loop = 0
        try:
            # Envolve todo o bloco de conexão e batching em um timeout máximo.
            # Se a rede bloquear o tráfego (Drop do pfSense/Suricata), a conexão pendurada
            # será interrompida e o erro será mostrado no console, evitando o travamento silencioso.
            async def execute_batch():
                acts = 0
                log_msgs = []
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        for _ in range(batch_size):
                            if not simulation_status["is_running"]: break
                            
                            await asyncio.sleep(0) # Yield control to the event loop
                            action = random.choice(["create_student", "create_professor", "create_class", "edit", "enroll_student", "add_grade", "add_attendance"])
                            log_msg = ""

                            if action == "create_student":
                                name = f"{SIM_MARKER} Aluno_{random_string(4)}"
                                reg = f"SIM-{random.randint(1000, 9999999)}_{random_string(4)}"
                                await cursor.execute("INSERT INTO students (name, registration, password, course) VALUES (%s, %s, '$2b$12$Nq/EwA2/O0bS.u0XgYyKHeH9o.uS2TzRyC.W7lYjZp0Q3Lp9LqXg2', 'Simulação')", (name, reg))
                                log_msg = f"Criou aluno: {name}"

                            elif action == "create_professor":
                                name = f"{SIM_MARKER} Prof_{random_string(4)}"
                                usr = f"sim_pr_{random_string(8)}"
                                await cursor.execute("INSERT INTO professors (username, password, name, department) VALUES (%s, '$2b$12$Nq/EwA2/O0bS.u0XgYyKHeH9o.uS2TzRyC.W7lYjZp0Q3Lp9LqXg2', %s, 'Simulação')", (usr, name))
                                log_msg = f"Criou professor: {name}"

                            elif action == "create_class":
                                await cursor.execute("SELECT id FROM professors WHERE name LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                                prof = await cursor.fetchone()
                                prof_id = prof['id'] if prof else None
                                name = f"{SIM_MARKER} Turma_{random_string(3)}"
                                await cursor.execute("INSERT INTO classes (name, professor_id) VALUES (%s, %s)", (name, prof_id))
                                log_msg = f"Criou turma: {name}"

                            elif action == "edit":
                                table = random.choice(['students', 'professors', 'classes'])
                                col_name = "name"
                                await cursor.execute(f"SELECT id, {col_name} FROM {table} WHERE {col_name} LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                                result = await cursor.fetchone()
                                if result:
                                    new_name = f"{SIM_MARKER} Edit_{random_string(4)}"
                                    await cursor.execute(f"UPDATE {table} SET {col_name} = %s WHERE id = %s", (new_name, result['id']))
                                    log_msg = f"Editou {table} ID {result['id']} -> {new_name}"
                                else:
                                    log_msg = f"Tentou editar {table}, mas nada encontrado."

                            elif action == "enroll_student":
                                await cursor.execute("SELECT id FROM students WHERE name LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                                st = await cursor.fetchone()
                                await cursor.execute("SELECT id FROM classes WHERE name LIKE %s ORDER BY RAND() LIMIT 1", (f"{SIM_MARKER}%",))
                                cls = await cursor.fetchone()
                                if st and cls:
                                    st_id, cls_id = st['id'], cls['id']
                                    await cursor.execute("SELECT * FROM student_class WHERE student_id=%s AND class_id=%s", (st_id, cls_id))
                                    if not await cursor.fetchone():
                                        await cursor.execute("INSERT INTO student_class (student_id, class_id) VALUES (%s, %s)", (st_id, cls_id))
                                        log_msg = f"Vinculou Estudante ID {st_id} à Turma ID {cls_id}"
                                    else:
                                        log_msg = "Vínculo já existente, ignorado."
                                else:
                                    log_msg = "Tentou vincular aluno a turma, mas faltam dados."

                            elif action == "add_grade":
                                await cursor.execute("""
                                    SELECT sc.student_id, sc.class_id 
                                    FROM student_class sc
                                    JOIN students s ON sc.student_id = s.id 
                                    WHERE s.name LIKE %s 
                                    ORDER BY RAND() LIMIT 1
                                """, (f"{SIM_MARKER}%",))
                                rel = await cursor.fetchone()
                                if rel:
                                    grade_val = str(round(random.uniform(2.0, 10.0), 1))
                                    desc = random.choice(["Prova 1", "Prova 2", "Trabalho", "Seminário", "Projeto Final"])
                                    await cursor.execute("INSERT INTO grades (student_id, class_id, value, description) VALUES (%s, %s, %s, %s)", 
                                                   (rel['student_id'], rel['class_id'], grade_val, desc))
                                    log_msg = f"Lançou nota {grade_val} para Aluno ID {rel['student_id']} (Turma {rel['class_id']})"
                                else:
                                    log_msg = "Tentou lançar nota, mas nenhum aluno matriculado."

                            elif action == "add_attendance":
                                await cursor.execute("""
                                    SELECT sc.student_id, sc.class_id 
                                    FROM student_class sc
                                    JOIN students s ON sc.student_id = s.id 
                                    WHERE s.name LIKE %s 
                                    ORDER BY RAND() LIMIT 1
                                """, (f"{SIM_MARKER}%",))
                                rel = await cursor.fetchone()
                                if rel:
                                    date_str = f"2026-03-{random.randint(1,28):02d}"
                                    await cursor.execute("INSERT INTO attendances (student_id, class_id, date, absent) VALUES (%s, %s, %s, 1)", 
                                                   (rel['student_id'], rel['class_id'], date_str))
                                    log_msg = f"Registrou falta para Aluno ID {rel['student_id']} (Turma {rel['class_id']})"
                                else:
                                    log_msg = "Tentou registrar falta, mas nenhum aluno matriculado."

                            acts += 1
                            if log_msg: log_msgs.append(log_msg)
                return acts, log_msgs

            # Aplica um timeout de segurança (ex: 8 segundos). Se o pfSense bloquear silenciosamente, ele estoura aqui.
            actions_in_this_loop, final_log_msgs = await asyncio.wait_for(execute_batch(), timeout=8.0)
            
            simulation_status["actions_performed"] += actions_in_this_loop
                        
            # Registra o log do último evento do batch
            if final_log_msgs:
                timestamp = time.strftime('%H:%M:%S')
                simulation_status["logs"].insert(0, f"[{timestamp}] (Batch {actions_in_this_loop}) {final_log_msgs[-1]}")
                if len(simulation_status["logs"]) > 1000:
                    simulation_status["logs"].pop()
                    
        except asyncio.TimeoutError:
            timestamp = time.strftime('%H:%M:%S')
            simulation_status["logs"].insert(0, f"[{timestamp}] [!] Alerta de Rede: Conexão DB travou (Possível bloqueio do pfSense/Suricata). Reconectando...")
            # Força o encerramento do pool antigo e cria um novo para se recuperar do bloqueio
            try:
                pool.close()
                await pool.wait_closed()
            except: pass
            pool = await aiomysql.create_pool(host=config.db_host, user=config.db_user, password=config.db_pass, db=config.db_name, port=config.db_port, autocommit=True, minsize=1, maxsize=5)
            await asyncio.sleep(2)
        except Exception as e:
            timestamp = time.strftime('%H:%M:%S')
            simulation_status["logs"].insert(0, f"[{timestamp}] Falha na ação: {str(e)[:60]}")
            if len(simulation_status["logs"]) > 1000:
                simulation_status["logs"].pop()
            
        await asyncio.sleep(delay)

    pool.close()
    await pool.wait_closed()
    
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
            
    # Validação rápida de conexão antes de iniciar a thread de background
    try:
        conn = await aiomysql.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_pass,
            db=config.db_name,
            port=config.db_port,
            connect_timeout=5
        )
        conn.close()
    except Exception as e:
        error_msg = f"Falha na conexão inicial: {str(e)}"
        simulation_status["is_running"] = False
        simulation_status["logs"] = [error_msg, "Simulação não iniciada."]
        raise HTTPException(status_code=400, detail=error_msg)

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
        # Para limpeza pontual podemos usar o pool temporário
        pool = await aiomysql.create_pool(
            host=config.db_host,
            user=config.db_user,
            password=config.db_pass,
            db=config.db_name,
            port=config.db_port,
            autocommit=True
        )
        
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Limpa dependencias
                await cursor.execute("DELETE FROM grades WHERE class_id IN (SELECT id FROM classes WHERE name LIKE %s)", (f"{SIM_MARKER}%",))
                await cursor.execute("DELETE FROM attendances WHERE class_id IN (SELECT id FROM classes WHERE name LIKE %s)", (f"{SIM_MARKER}%",))
                await cursor.execute("DELETE FROM student_class WHERE class_id IN (SELECT id FROM classes WHERE name LIKE %s)", (f"{SIM_MARKER}%",))
                await cursor.execute("DELETE FROM grades WHERE student_id IN (SELECT id FROM students WHERE name LIKE %s)", (f"{SIM_MARKER}%",))
                await cursor.execute("DELETE FROM attendances WHERE student_id IN (SELECT id FROM students WHERE name LIKE %s)", (f"{SIM_MARKER}%",))
                await cursor.execute("DELETE FROM student_class WHERE student_id IN (SELECT id FROM students WHERE name LIKE %s)", (f"{SIM_MARKER}%",))

                await cursor.execute("DELETE FROM classes WHERE name LIKE %s", (f"{SIM_MARKER}%",))
                d_classes = cursor.rowcount
                await cursor.execute("DELETE FROM professors WHERE username LIKE %s OR name LIKE %s", (f"{SIM_MARKER}%", f"{SIM_MARKER}%"))
                d_prof = cursor.rowcount
                await cursor.execute("DELETE FROM students WHERE name LIKE %s", (f"{SIM_MARKER}%",))
                d_stud = cursor.rowcount
                
        pool.close()
        await pool.wait_closed()
        return {"message": f"Limpeza feita: {d_classes} Turmas, {d_prof} Professores e {d_stud} Estudantes."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_sim_status(current_user: dict = Depends(get_current_user)):
    global simulation_status
    return {**simulation_status, "server_time": time.time()}
