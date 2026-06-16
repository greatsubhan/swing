"""Fix double comma in dashboard INTEGRATIONS array."""
path = "bot-dashboard/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()
old = ',{name:"Discord Import Pipeline"'
if ',,' + old in content:
    content = content.replace(',,' + old, old)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed double comma")
elif old in content and ',,' not in content.split(old)[0][-5:]:
    print("No double comma found - dashboard OK")
else:
    # Just find and fix any double commas around the insertion
    content = content.replace('},,{name:', '},{name:')
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed via generic double comma repair")