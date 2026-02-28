import glob

html_files = glob.glob('web_panel/app/templates/*.html')
for file in html_files:
    try:
        # Se os desenvolvedores salvaram no git em UTF-8 mas com a conversão corrompida:
        with open(file, 'rb') as f:
            b_text = f.read()
            
        text = b_text.decode('utf-8')
        
        # Sinais de double encoding UTF-8
        if 'Ã§' in text or 'Ã£' in text or 'Ã' in text or '┬║' in text or '├' in text or '├º├ú' in text:
            try:
                # Ocorre quando bytes utf-8 reais são lidos como codepage windows/latin1 e re-salvos como utf-8
                if '├' in text:
                    fixed_bytes = text.encode('cp437') # O VSCode as vezes leu utf-8 como cp437 no console do powershell
                else:
                    fixed_bytes = text.encode('latin-1') 
                    
                fixed_text = fixed_bytes.decode('utf-8')
                
                with open(file, 'w', encoding='utf-8') as f:
                    f.write(fixed_text)
                print(f"Corrigido: {file}")
            except Exception as e:
                print(f"Nao foi duplo encoding? {file}: {e}")
        else:
            print(f"Normal: {file}")
            
    except Exception as e:
        print(f"Erro ao processar {file}: {e}")
