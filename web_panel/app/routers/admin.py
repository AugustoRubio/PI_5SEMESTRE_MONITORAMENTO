from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.auth import get_current_user, get_password_hash, USERS_DB, save_users

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password: str

class PasswordUpdate(BaseModel):
    new_password: str

@router.get("/users")
async def get_users(current_user: dict = Depends(get_current_user)):
    # Retorna a lista de usuários (sem as senhas)
    return {"users": [user for user in USERS_DB.keys()]}

@router.post("/users")
async def add_user(user: UserCreate, current_user: dict = Depends(get_current_user)):
    if user.username in USERS_DB:
        raise HTTPException(status_code=400, detail="Usuário já existe")
    
    USERS_DB[user.username] = {
        "username": user.username,
        "hashed_password": get_password_hash(user.password),
        "disabled": False
    }
    save_users(USERS_DB)
    return {"message": f"Usuário {user.username} criado com sucesso"}

@router.delete("/users/{username}")
async def delete_user(username: str, current_user: dict = Depends(get_current_user)):
    if username not in USERS_DB:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Você não pode deletar a si mesmo")
        
    del USERS_DB[username]
    save_users(USERS_DB)
    return {"message": f"Usuário {username} deletado com sucesso"}

@router.put("/users/{username}/password")
async def update_password(username: str, data: PasswordUpdate, current_user: dict = Depends(get_current_user)):
    if username not in USERS_DB:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
    USERS_DB[username]["hashed_password"] = get_password_hash(data.new_password)
    save_users(USERS_DB)
    return {"message": f"Senha do usuário {username} atualizada com sucesso"}
