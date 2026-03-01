with open('web_panel/app/templates/base.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
text = re.sub(r'<li><a class=\"dropdown-item text-warning\" href=\"/stress\".*?</li>\n?', '', text)

with open('web_panel/app/templates/base.html', 'w', encoding='utf-8') as f:
    f.write(text)
