import pathlib

file_path = pathlib.Path('web_panel/app/templates/simulation.html')
content = file_path.read_text(encoding='utf-8')

# Increase concurrency to 200 workers default and 120 secs default
old_conc = 'id="concurrency" class="form-control form-control-sm" value="50"'
new_conc = 'id="concurrency" class="form-control form-control-sm" value="200"'

old_dur = 'id="duration" class="form-control form-control-sm" value="60"'
new_dur = 'id="duration" class="form-control form-control-sm" value="120"'

if old_conc in content:
    content = content.replace(old_conc, new_conc)
    print("Replaced concurrency")

if old_dur in content:
    content = content.replace(old_dur, new_dur)
    print("Replaced duration")

content = content.replace('<option value="calm">Calmo</option>', '<!-- temp -->')
content = content.replace('<option value="aggressive">Agressivo</option>', '<option value="aggressive" selected>Agressivo</option>')
content = content.replace('<!-- temp -->', '<option value="calm">Calmo</option>')
print("Swapped default profile")

file_path.write_text(content, encoding='utf-8')

