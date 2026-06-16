"""Fix dashboard syntax errors: remove MAP.reviews injection, fix MAP.integrations, validate."""
import re
import subprocess
import sys

FILE = 'bot-dashboard/index.html'

def read():
    with open(FILE, 'r', encoding='utf-8') as f:
        return f.read()

def write(content):
    with open(FILE, 'w', encoding='utf-8') as f:
        f.write(content)

def extract_js(html):
    m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    return m.group(1) if m else ''

def validate_js(js):
    """Write JS to temp file and run node --check."""
    with open('_validate_temp.js', 'w', encoding='utf-8') as f:
        f.write(js)
    result = subprocess.run(['node', '--check', '_validate_temp.js'],
                          capture_output=True, text=True)
    return result.returncode == 0, result.stderr.strip()

html = read()
original_len = len(html)
changes = []

# 1. Remove the reviews injection from MAP object
# The reviews data is at the very end of MAP, right before the closing };
# Pattern: ,reviews:{source:"PROFESSIONAL_REVIEW.md",...,severity:{critical:3,high:2,medium:1}}
reviews_pattern = r',reviews:\{source:"PROFESSIONAL_REVIEW\.md",[^}]+\}'
if re.search(reviews_pattern, html):
    html = re.sub(reviews_pattern, '', html, count=1)
    changes.append('Removed reviews injection from MAP object')

# 2. Fix MAP.integrations -> INTEGRATIONS (the local const)
if 'MAP.integrations.map' in html:
    html = html.replace('MAP.integrations.map', 'INTEGRATIONS.map')
    changes.append('Fixed MAP.integrations.map -> INTEGRATIONS.map')
if 'if(MAP.integrations)' in html:
    html = html.replace('if(MAP.integrations)', 'if(INTEGRATIONS)')
    changes.append('Fixed if(MAP.integrations) -> if(INTEGRATIONS)')

# 3. Also fix the reviews panel in the JS render section
# Remove the JS-rendered reviews panel that was added (it duplicated the static HTML)
# Look for the block that starts with /* Render Reviews Panel */ and removes it
reviews_render_pattern = r'\n/\* Render Reviews Panel \*/.*?document\.querySelector\("\.app"\)\?document\.querySelector\("\.app"\)\.appendChild\(rg\):null;\}'
if re.search(reviews_render_pattern, html, re.DOTALL):
    html = re.sub(reviews_render_pattern, '', html, flags=re.DOTALL)
    changes.append('Removed duplicate JS-rendered reviews panel')

# 4. Validate the fix
js = extract_js(html)
is_valid, error = validate_js(js)

if is_valid:
    changes.append('JS syntax validation: PASSED')
else:
    changes.append(f'JS syntax validation: FAILED - {error[:200]}')

write(html)

print(f'File: {FILE} ({original_len} -> {len(html)} bytes)')
print(f'Changes: {len(changes)}')
for i, c in enumerate(changes, 1):
    print(f'  {i}. {c}')

if not is_valid:
    print('\n⚠️  JS still has syntax errors after fix')
    sys.exit(1)
else:
    print('\n✅ Dashboard syntax fixed successfully')