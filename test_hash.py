
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
hash_str = '\\\/EwA2/O0bS.u0XgYyKHeH9o.uS2TzRyC.W7lYjZp0Q3Lp9LqXg2'
print(pwd_context.verify('sim', hash_str))

