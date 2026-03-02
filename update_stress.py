import pathlib

file_path = pathlib.Path('web_panel/app/routers/stress.py')
content = file_path.read_text(encoding='utf-8')

# 1KB empty string dummy data
old_payload = 'payload = {"data": "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=1024))} # 1KB dummy load'
new_payload = 'payload = {"data": "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=20480))} # 20KB dummy load'

if old_payload in content:
    content = content.replace(old_payload, new_payload)
    file_path.write_text(content, encoding='utf-8')
    print("Successfully changed payload size")
else:
    print("Could not find payload line")

