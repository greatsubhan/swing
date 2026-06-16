"""Fix missing } to close Action Items card before Discord Import card."""
path = "bot-dashboard/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# The issue: actions array close is ], but missing } to close the card object
# Pattern: ...webhooks reachable"}],{name:"Discord Import Pipeline"
# Should be: ...webhooks reachable"}]},{name:"Discord Import Pipeline"
target = 'webhooks reachable"}],{name:'
replace = 'webhooks reachable"}]},{name:'

if target in content:
    content = content.replace(target, replace)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed: added missing } to close Action Items card")
else:
    print("Target pattern not found")
    idx = content.find('Discord Import Pipeline')
    if idx > 0:
        ctx = content[idx-100:idx+30]
        print(f"Current context: {ctx}")