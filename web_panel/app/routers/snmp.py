from fastapi import APIRouter

router = APIRouter()

@router.post("/temperature/increase")
async def increase_temperature():
    # Aqui implementaremos a lógica para alterar o arquivo .snmprec do snmpsim
    # simulando o aumento de temperatura no sensor.
    return {"status": "success", "message": "Temperatura aumentada com sucesso no simulador."}

@router.post("/temperature/decrease")
async def decrease_temperature():
    # Lógica para diminuir a temperatura
    return {"status": "success", "message": "Temperatura diminuída com sucesso no simulador."}

@router.post("/ups/power-fail")
async def simulate_power_fail():
    # Lógica para alterar o status do Nobreak para "Bateria"
    return {"status": "success", "message": "Queda de energia simulada. Nobreak em modo bateria."}

@router.post("/ups/power-restore")
async def simulate_power_restore():
    # Lógica para alterar o status do Nobreak para "Online"
    return {"status": "success", "message": "Energia restaurada. Nobreak em modo online."}
