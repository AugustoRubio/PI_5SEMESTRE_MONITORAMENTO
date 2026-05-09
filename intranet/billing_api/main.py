from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import random
import sqlite3
import os
import time
from faker import Faker

app = FastAPI(title="Billing Microservice API", description="API Isolada de Pagamentos e Faturas", version="1.0.0")
fake = Faker('pt_BR')

DB_FILE = "/app/billing.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS invoices 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  student_id INTEGER, 
                  amount REAL, 
                  status TEXT, 
                  card_number TEXT, 
                  card_cvv TEXT)''')
    
    # Seeding database locally for this container replica
    c.execute("SELECT COUNT(*) FROM invoices")
    count = c.fetchone()[0]
    if count == 0:
        print(f"[{os.environ.get('HOSTNAME', 'BillingAPI')}] Seeding mock database with fake credit cards...")
        # Create 500 fake invoices for students ID 1 to 500
        for i in range(1, 501):
            status = "PENDING" if random.random() > 0.5 else "PAID"
            amount = round(random.uniform(500.0, 2500.0), 2)
            # Gerando um número de cartão de crédito real (fake logic) para o Suricata capturar (DLP)
            card = fake.credit_card_number(card_type="visa")
            cvv = fake.credit_card_security_code(card_type="visa")
            c.execute("INSERT INTO invoices (student_id, amount, status, card_number, card_cvv) VALUES (?, ?, ?, ?, ?)",
                      (i, amount, status, card, cvv))
        conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
@app.get("/status")
def status():
    return {
        "status": "Online", 
        "service": "Billing API (Microservice)", 
        "replica": os.environ.get("HOSTNAME", "unknown")
    }

billing_metrics_cache = {
    "data": None,
    "timestamp": 0
}

@app.get("/metrics")
def billing_metrics():
    now = time.time()
    if billing_metrics_cache["data"] and (now - billing_metrics_cache["timestamp"] < 30):
        return billing_metrics_cache["data"]

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Total de Faturas Geradas
    c.execute("SELECT COUNT(*) FROM invoices")
    total_invoices = c.fetchone()[0]
    
    # Valor Total Não Pago (PENDING)
    c.execute("SELECT SUM(amount) FROM invoices WHERE status = 'PENDING'")
    unpaid_result = c.fetchone()[0]
    unpaid_amount = float(unpaid_result) if unpaid_result is not None else 0.0
    
    conn.close()
    
    billing_metrics_cache["data"] = {
        "total_invoices": total_invoices,
        "unpaid_amount": unpaid_amount
    }
    billing_metrics_cache["timestamp"] = now
    
    return billing_metrics_cache["data"]

class PaymentRequest(BaseModel):
    invoice_id: int
    amount: float

@app.get("/invoices")
def get_all_invoices(limit: int = 100):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, student_id, amount, status, card_number, card_cvv FROM invoices ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# =========================================================================
# VULNERABILITY 1: BOLA (Broken Object Level Authorization)
# Permite que o Aluno 1 visualize os dados (incluindo o cartão de crédito) do Aluno 2
# apenas mudando o ID na URL. Não há verificação de Sessão/Token aqui (SOA design flaw).
# Isso dispara as regras de DLP do Suricata por vazar dados sensíveis!
# =========================================================================
@app.get("/invoices/{student_id}")
def get_invoices(student_id: int, request: Request):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Busca as faturas existentes para este aluno
    c.execute("SELECT id, student_id, amount, status, card_number, card_cvv FROM invoices WHERE student_id = ?", (student_id,))
    rows = c.fetchall()
    
    # Se o aluno não tiver faturas (aluno novo criado na Intranet ou não "semeado" ainda), 
    # fabricamos faturas falsas na hora (Auto-Healing Mock).
    if not rows:
        num_invoices = random.randint(1, 3)
        for _ in range(num_invoices):
            status = "PENDING" if random.random() > 0.3 else "PAID"
            amount = round(random.uniform(300.0, 1800.0), 2)
            card = fake.credit_card_number(card_type="visa")
            cvv = fake.credit_card_security_code(card_type="visa")
            
            c.execute("INSERT INTO invoices (student_id, amount, status, card_number, card_cvv) VALUES (?, ?, ?, ?, ?)",
                      (student_id, amount, status, card, cvv))
        
        conn.commit()
        
        # Busca novamente as faturas recém-criadas
        c.execute("SELECT id, student_id, amount, status, card_number, card_cvv FROM invoices WHERE student_id = ?", (student_id,))
        rows = c.fetchall()
        
    conn.close()
    
    return [dict(row) for row in rows]

# =========================================================================
# VULNERABILITY 2: Parameter Tampering (Fraude no Valor)
# Confia no 'amount' (valor) enviado pelo Cliente (Navegador) ao invés de buscar no Banco
# =========================================================================
@app.post("/pay")
def pay_invoice(payment: PaymentRequest):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, amount, status FROM invoices WHERE id = ?", (payment.invoice_id,))
    invoice = c.fetchone()
    
    if not invoice:
        conn.close()
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")
    if invoice[2] == "PAID":
        conn.close()
        raise HTTPException(status_code=400, detail="Fatura já foi paga.")
        
    # O atacante pode mandar 1.00 ao invés do valor real da fatura (ex: 2000.00).
    c.execute("UPDATE invoices SET status = 'PAID', amount = ? WHERE id = ?", (payment.amount, payment.invoice_id))
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": f"Pagamento de R$ {payment.amount} processado com sucesso para a Fatura #{payment.invoice_id}!"}
