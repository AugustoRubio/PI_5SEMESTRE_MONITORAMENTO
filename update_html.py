import pathlib

file_path = pathlib.Path('web_panel/app/templates/simulation.html')
lines = file_path.read_text(encoding='utf-8').splitlines()

# find index of <div class="col-md-7">
idx_col7 = -1
for i, line in enumerate(lines):
    if '<div class="col-md-7">' in line:
        idx_col7 = i
        break

html_insert = '''                            <div class="mb-2 row">
                                <div class="col-sm-12">
                                    <label class="form-label fw-bold mb-0"><small>Intensidade de Rede (Payload)</small></label>
                                    <select class="form-select form-select-sm" id="networkIntensity">
                                        <option value="low">Baixa (~1KB por req)</option>
                                        <option value="medium">Media (~500KB por req)</option>
                                        <option value="high" selected>Extrema (~5MB por req)</option>
                                    </select>
                                </div>
                            </div>'''

if idx_col7 != -1:
    lines.insert(idx_col7, html_insert)

# find index of const concurrency =
idx_conc = -1
for i, line in enumerate(lines):
    if 'const concurrency =' in line:
        idx_conc = i
        break

js_insert = "        const network_intensity = document.getElementById('networkIntensity').value;"

if idx_conc != -1:
    lines.insert(idx_conc + 1, js_insert)

# find index of ody: JSON.stringify
for i, line in enumerate(lines):
    if 'body: JSON.stringify({' in line:
        lines[i] = line.replace('concurrency })', 'concurrency, network_intensity })')
        break

file_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('Modifications applied.')

