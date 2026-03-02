import pathlib
import sys

file_path = pathlib.Path('web_panel/app/routers/stress.py')
content = file_path.read_text(encoding='utf-8')

# 1. Update StressConfig
content = content.replace(
'''class StressConfig(BaseModel):
    target_url: str
    duration_seconds: int
    concurrency: int''',
'''class StressConfig(BaseModel):
    target_url: str
    duration_seconds: int
    concurrency: int
    network_intensity: str = "low"'''
)

# 2. Update perform_stress_test signature
content = content.replace(
'''async def perform_stress_test(url: str, duration: int, concurrency: int, method: str = "GET"):''',
'''async def perform_stress_test(url: str, duration: int, concurrency: int, method: str = "GET", network_intensity: str = "low"):'''
)

# 3. Pre-generate payload logic
dummy_payload_logic = '''
    if network_intensity == "high":
        payload_size = 5242880 # 5MB
    elif network_intensity == "medium":
        payload_size = 512000 # 500KB
    else:
        payload_size = 1024 # 1KB
        
    import string
    import random
    base_chars = string.ascii_letters + string.digits
    pre_generated_payload_str = "".join(random.choices(base_chars, k=payload_size))
    
    timeout = httpx.Timeout(10.0)'''

content = content.replace(
'''timeout = httpx.Timeout(10.0)''',
dummy_payload_logic
)

# 4. Use pre-generated string
content = content.replace(
'''                    else:
                        payload = {"data": "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=20480))} # 20KB dummy load
                        await client.post(url, headers=headers, json=payload)''',
'''                    else:
                        payload = {"data": pre_generated_payload_str} 
                        await client.post(url, headers=headers, json=payload)'''
)

# 5. Fix background_tasks calls
content = content.replace(
'''background_tasks.add_task(perform_stress_test, config.target_url, config.duration_seconds, config.concurrency, "GET")''',
'''background_tasks.add_task(perform_stress_test, config.target_url, config.duration_seconds, config.concurrency, "GET", config.network_intensity)'''
)
content = content.replace(
'''background_tasks.add_task(perform_stress_test, url, config.duration_seconds, config.concurrency, "GET")''',
'''background_tasks.add_task(perform_stress_test, url, config.duration_seconds, config.concurrency, "GET", config.network_intensity)'''
)
content = content.replace(
'''background_tasks.add_task(perform_stress_test, url, config.duration_seconds, config.concurrency, "POST")''',
'''background_tasks.add_task(perform_stress_test, url, config.duration_seconds, config.concurrency, "POST", config.network_intensity)'''
)

file_path.write_text(content, encoding='utf-8')
print("Backend modifications applied.")
