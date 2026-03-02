import pathlib

file_path = pathlib.Path('web_panel/app/templates/simulation.html')
content = file_path.read_text(encoding='utf-8')

param_block = '''                             <div class="mb-2 row">
                                 <div class="col-sm-12">
                                     <label class="form-label fw-bold mb-0"><small>Intensidade de Rede (Payload)</small> <i class="bi bi-question-circle ms-1 cursor-pointer text-primary" data-bs-toggle="tooltip" title="Tamanho do Payload/Upload disparado a cada request para entupir link."></i></label>
                                     <select class="form-select form-select-sm" id="networkIntensity">
                                         <option value="low">Baixa (1 KB/req)</option>
                                         <option value="medium" selected>Média (500 KB/req)</option>
                                         <option value="high">Extrema (5 MB/req)</option>
                                     </select>
                                 </div>
                             </div>
'''

old = '<div class="mb-2 row">\n                                 <div class="col-sm-6">\n                                     <label class="form-label fw-bold mb-0"><small>Concorrencia Carga</small></label>'

if old in content:
    content = content.replace(old, param_block + old)
    file_path.write_text(content, encoding='utf-8')
    print('Updated simulation HTML params')
else:
    print('Pattern not found')

