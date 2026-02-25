from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from app.auth import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, check_brute_force

router = APIRouter()

@router.post("/token")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    client_ip = request.client.host
    
    # Verifica se o IP está bloqueado por brute force
    if not check_brute_force(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login falhas. Tente novamente mais tarde."
        )

    user = authenticate_user(form_data.username, form_data.password, client_ip)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
