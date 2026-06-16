"""Fix double comma before Discord Import Pipeline card."""
path = "bot-dashboard/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the specific double comma pattern
target = '},,{name:"Discord Import Pipeline"'
replacement = '},{name:"Discord Import Pipeline"'
if target in content:
    content = content.replace(target, replacement)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed: double comma before Discord Import Pipeline")
else:
    # Check alternate: ],, before the card
    target2 = '],,{name:"Discord Import Pipeline"'
    if target2 in content:
        content = content.replace(target2, '],{name:"Discord Import Pipeline"')
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Fixed: ],, pattern")
    else:
        print("No double comma issue found")
        # Verify the structure is valid
        idx = content.find('Discord Import Pipeline')
        if idx > 0:
            print(f"Context around insertion: ...{content[idx-80:idx+30]}...")