import os
from dotenv import load_dotenv
import pymysql

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "intranet_db")

print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}")
if not DB_USER:
    print("Database credentials not found in .env")
else:
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=int(DB_PORT)
        )
        
        with conn.cursor() as cursor:
            # 1. Add password column to students
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN password VARCHAR(255)")
                conn.commit()
                print("SUCCESS: Added 'password' column to 'students' table.")
            except pymysql.err.OperationalError as e:
                if e.args[0] == 1060:
                    print("INFO: 'password' column already exists in 'students'.")
                else:
                    print(f"ERROR adding password column: {e}")
                    
            # 2. Add grades table
            try:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS grades (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    student_id INT,
                    class_id INT,
                    value VARCHAR(10),
                    description VARCHAR(255),
                    FOREIGN KEY (student_id) REFERENCES students(id),
                    FOREIGN KEY (class_id) REFERENCES classes(id)
                )
                """)
                conn.commit()
                print("SUCCESS: Ensured 'grades' table exists.")
            except Exception as e:
                print(f"ERROR creating grades table: {e}")
                
        conn.close()
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
