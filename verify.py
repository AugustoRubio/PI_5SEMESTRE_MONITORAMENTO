from passlib.context import CryptContext
ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
h = "$2b$12$Nq/EwA2/O0bS.u0XgYyKHeH9o.uS2TzRyC.W7lYjZp0Q3Lp9LqXg2"
print(ctx.verify("sim", h))
