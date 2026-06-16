"""Check dashboard CSS and JS state."""
with open('bot-dashboard/index.html', 'r', encoding='utf-8') as f:
    content = f.read()
print(f"File length: {len(content)}")
print(f"Has CSS (integ-section): {'integ-section' in content}")
print(f"Has INTEGRATIONS const: {'const INTEGRATIONS' in content}")
print(f"Has integGrid div: {'integGrid' in content}")
print(f"Has INTEGRATIONS rendering: {'integGrid' in content}")