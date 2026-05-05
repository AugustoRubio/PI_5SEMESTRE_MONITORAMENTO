import pathlib

file_path = pathlib.Path('web_panel/app/templates/simulation.html')
content = file_path.read_text(encoding='utf-8')

# We need to replace the corrupted lines 122-124
#
# 121: </div>
# 122: 
# 123:                 </div>
# 124:             </div>
#
# with the proper HTML opening tags.

proper_html = '''</div>

<!-- Logs e Status Unificado -->
<div class="row">
    <div class="col-12 mb-4">
        <div class="card bg-dark text-light border-secondary">
            <div class="card-header border-secondary d-flex flex-column flex-md-row justify-content-between align-items-center gap-2">
                <span><i class="bi bi-terminal"></i> Console de Monitoramento Unificado</span>
                <div class="d-flex gap-3">
                    <span id="stressBadge" class="badge bg-secondary fs-6">Stress: Parado <small id="stressTime" class="fw-normal"></small></span>
                    <span id="simBadge" class="badge bg-secondary fs-6">Simulação: Parada <small id="simTime" class="fw-normal"></small></span>
                </div>
            </div>'''

# Let's perform a simple replace.
bad_chunk = '''</div>

                </div>
            </div>'''

if bad_chunk in content:
    content = content.replace(bad_chunk, proper_html)
    file_path.write_text(content, encoding='utf-8')
    print("Fixed corrupted HTML tags")
else:
    print("Could not find the exact bad chunk to replace!")
