import pathlib

file_path = pathlib.Path('web_panel/app/routers/stress.py')
content = file_path.read_text(encoding='utf-8')

old_limits = "limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)"
new_limits = "limits = httpx.Limits(max_connections=concurrency * 10, max_keepalive_connections=concurrency * 10)"

if old_limits in content:
    content = content.replace(old_limits, new_limits)
    file_path.write_text(content, encoding='utf-8')
    print("Successfully increased httpx pool connections limits")
else:
    print("Limits could not be increased")

