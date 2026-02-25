from fastapi import APIRouter

router = APIRouter()

# --- ATAQUES EXTERNOS (Origem: VPS) ---

@router.post("/external/ddos/start")
async def start_external_ddos():
    # Lógica: SSH na VPS -> Executar hping3 contra o IP Público do pfSense
    return {"status": "success", "message": "Ataque DDoS EXTERNO (SYN Flood) iniciado a partir da VPS."}

@router.post("/external/ddos/stop")
async def stop_external_ddos():
    return {"status": "success", "message": "Ataque DDoS EXTERNO interrompido."}

@router.post("/external/bruteforce/start")
async def start_external_bruteforce():
    # Lógica: SSH na VPS -> Executar Hydra contra porta SSH/FTP exposta
    return {"status": "success", "message": "Ataque de Força Bruta EXTERNO iniciado."}

@router.post("/external/bruteforce/stop")
async def stop_external_bruteforce():
    return {"status": "success", "message": "Ataque de Força Bruta EXTERNO interrompido."}

# --- ATAQUES INTERNOS (Origem: VM no GNS3) ---

@router.post("/internal/ddos/start")
async def start_internal_ddos():
    # Lógica: SSH na VM Atacante Interna -> Executar hping3 contra servidor na mesma LAN
    return {"status": "success", "message": "Ataque DDoS INTERNO (UDP Flood) iniciado na LAN."}

@router.post("/internal/ddos/stop")
async def stop_internal_ddos():
    return {"status": "success", "message": "Ataque DDoS INTERNO interrompido."}

@router.post("/internal/mitm/start")
async def start_internal_mitm():
    # Lógica: SSH na VM Atacante Interna -> Executar Ettercap/Bettercap (ARP Poisoning)
    return {"status": "success", "message": "Ataque Man-in-the-Middle (ARP Poisoning) INTERNO iniciado."}

@router.post("/internal/mitm/stop")
async def stop_internal_mitm():
    return {"status": "success", "message": "Ataque Man-in-the-Middle INTERNO interrompido."}
