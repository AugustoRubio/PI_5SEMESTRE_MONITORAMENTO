from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import time
import os
from dotenv import load_dotenv

import json

load_dotenv()

# Tempo de início do servidor (usado para invalidar tokens antigos ao reiniciar)
SERVER_START_TIME = datetime.utcnow().timestamp()

# Configurações de Segurança
SECRET_KEY = os.getenv("SECRET_KEY", "chave_fallback_insegura_apenas_para_dev")
ALGORITHM = "HS256"
# Tempo de expiração do token (padrão 30 minutos, pode ser alterado no .env)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", 30))

# Configurações de Brute Force
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME_SECONDS = 300 # 5 minutos

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

def load_users():
    if not os.path.exists(USERS_FILE):
        # Cria o arquivo com o usuário padrão se não existir
        default_users = {
            "Augusto": {
                "username": "Augusto",
                "hashed_password": pwd_context.hash("breath"),
                "disabled": False,
            }
        }
        save_users(default_users)
        return default_users
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users_db):
    with open(USERS_FILE, "w") as f:
        json.dump(users_db, f, indent=4)

# Carrega os usuários na inicialização
USERS_DB = load_users()

# Dicionário para rastrear tentativas de login falhas por IP
# Formato: {"ip_address": {"attempts": int, "lockout_until": float}}
failed_login_attempts = {}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        return db[username]
    return None

def check_brute_force(ip_address: str) -> bool:
    """Verifica se o IP está bloqueado. Retorna True se permitido, False se bloqueado."""
    current_time = time.time()
    if ip_address in failed_login_attempts:
        record = failed_login_attempts[ip_address]
        if record["lockout_until"] and current_time < record["lockout_until"]:
            return False # Ainda bloqueado
        elif record["lockout_until"] and current_time >= record["lockout_until"]:
            # Tempo de bloqueio expirou, reseta as tentativas
            failed_login_attempts[ip_address] = {"attempts": 0, "lockout_until": None}
    return True

def record_failed_login(ip_address: str):
    """Registra uma tentativa falha e aplica bloqueio se necessário."""
    current_time = time.time()
    if ip_address not in failed_login_attempts:
        failed_login_attempts[ip_address] = {"attempts": 1, "lockout_until": None}
    else:
        failed_login_attempts[ip_address]["attempts"] += 1
        if failed_login_attempts[ip_address]["attempts"] >= MAX_LOGIN_ATTEMPTS:
            failed_login_attempts[ip_address]["lockout_until"] = current_time + LOCKOUT_TIME_SECONDS

def reset_failed_login(ip_address: str):
    """Reseta as tentativas falhas após um login bem-sucedido."""
    if ip_address in failed_login_attempts:
        del failed_login_attempts[ip_address]

def authenticate_user(username: str, password: str, ip_address: str):
    user = get_user(USERS_DB, username)
    if not user or not verify_password(password, user["hashed_password"]):
        record_failed_login(ip_address)
        return False
    reset_failed_login(ip_address)
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Adiciona o tempo de expiração e o tempo de criação (iat)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow().timestamp()
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais ou a sessão expirou",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        iat: float = payload.get("iat")
        
        if username is None:
            raise credentials_exception
            
        # Se o token foi gerado antes do servidor iniciar, ele é inválido
        if iat is None or iat < SERVER_START_TIME:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    user = get_user(USERS_DB, username)
    if user is None:
        raise credentials_exception
    return user
