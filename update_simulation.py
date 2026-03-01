import sys

with open('web_panel/app/routers/simulation.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the broad except block inside the while loop to actually log the DB exceptions
content = content.replace(
'''        except Exception as e:
            pass''',
'''        except Exception as e:
            simulation_status["logs"].insert(0, f"Falha na ação: {str(e)}")
            if len(simulation_status["logs"]) > 15:
                simulation_status["logs"].pop()'''
)

# Replace the connection setup string encoding fix
content = content.replace("Iniciando simulaÃ§Ã£o completaa...", "Iniciando simulação completa...")
content = content.replace("SimulaÃ§Ã£o jÃ¡ em exec\\nuÃ§Ã£o.", "Simulação já em execução.")
content = content.replace("Nenhuma simulaÃ§Ã£o rodando.", "Nenhuma simulação rodando.")
content = content.replace("SimulaÃ§Ã£o finalizada.", "Simulação finalizada.")
content = content.replace("SimulaÃ§Ã£o", "Simulação")

with open('web_panel/app/routers/simulation.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated simulation.py")
