import pathlib

file_path = pathlib.Path('web_panel/app/routers/simulation.py')
content = file_path.read_text(encoding='utf-8')

# Decrease delay from 0.5s to 0.05s to make aggressive profile hit database MUCH faster
old_delay = 'delay = 5.0 if config.profile == "calm" else 0.5'
new_delay = 'delay = 5.0 if config.profile == "calm" else 0.05'

if old_delay in content:
    content = content.replace(old_delay, new_delay)
    file_path.write_text(content, encoding='utf-8')
    print("Successfully updated db delay simulation")
