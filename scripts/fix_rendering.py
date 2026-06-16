"""Fix INTEGRATIONS rendering reference."""
from pathlib import Path

p = Path('bot-dashboard/index.html')
content = p.read_text(encoding='utf-8')
# The rendering code says MAP.integrations but we defined it as const INTEGRATIONS
content = content.replace('if(MAP.integrations)', 'if(INTEGRATIONS)')
p.write_text(content, encoding='utf-8')
print('Fixed INTEGRATIONS reference')
content2 = p.read_text(encoding='utf-8')
print(f'Has fix: {"if(INTEGRATIONS)" in content2}')