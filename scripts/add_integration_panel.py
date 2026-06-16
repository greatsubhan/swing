"""Add integration panel data and rendering to the dashboard."""
from pathlib import Path

path = Path('bot-dashboard/index.html')
content = path.read_text(encoding='utf-8')

# 1. Add INTEGRATIONS const before /* Render Architecture Map */
integrations_data = """const INTEGRATIONS=[{name:"OANDA",icon:"🏦",status:"broken",label:"BROKEN",rows:[{l:"Status",v:"HTTP 401"},{l:"Root Cause",v:"Token expired/revoked"},{l:"Account",v:"101-011-30754943-003"},{l:"Environment",v:"practice"},{l:"Impact",v:"Blocks all scanners → 0 signals → 0 dispatch"},{l:"Diagnosis",v:"Generate new token at oanda.com/account/token"}],actions:["Generate new OANDA practice API token","Update OANDA_API_TOKEN in .env"]},{name:"Discord Webhooks",icon:"💬",status:"ok",label:"CONFIGURED",rows:[{l:"little_rzy",v:"✅ set"},{l:"strategy_two",v:"✅ set"},{l:"CWT (four)",v:"✅ set"},{l:"SIP (five)",v:"✅ set"},{l:"little_rzy_1h",v:"⚠ not set (disabled)"},{l:"Base",v:"⚠ not set"}]},{name:"Journal Files",icon:"📓",status:"ok",label:"PARTIAL",rows:[{l:"strategy_four",v:"✅ 1,029 entries"},{l:"little_rzy",v:"✅ 2 entries"},{l:"strategy_two",v:"⚠ 0 entries (no setups)"},{l:"strategy_five",v:"❌ no file (D1 low freq)"},{l:"little_rzy_1h",v:"⚠ missing (disabled)"}]},{name:"Action Items",icon:"📋",status:"broken",label:"2 BLOCKERS",rows:[{l:"🔴 P0",v:"New OANDA API token"},{l:"🟡 P1",v:"Confirm webhooks reachable"}],actions:["OANDA 401 blocks scanners, dispatch, and ML training"]}];
"""
anchor1 = '/* Render Architecture Map */'
if 'const INTEGRATIONS' not in content and anchor1 in content:
    content = content.replace(anchor1, integrations_data + anchor1, 1)
    print("Added INTEGRATIONS const")
else:
    print("INTEGRATIONS already exists or anchor not found")

# 2. Add HTML placeholder in the template string (before backtest section)
integ_placeholder = '<div class="integ-section"><div class="section-header"><span class="icon">🔌</span><h2>Integration Status</h2><span class="ref">PROJECT_MAP.md §20</span></div><p class="section-desc">OANDA connection, Discord webhooks, journal files, and action items.</p><div class="integ-grid" id="integGrid"></div></div>'
anchor2 = '<div class="backtest-section">'
if 'integGrid' not in content and anchor2 in content:
    content = content.replace(anchor2, integ_placeholder + '\n<div class="backtest-section">', 1)
    print("Added integration HTML placeholder")
else:
    print("Placeholder already exists or anchor not found")

# 3. Add rendering code before /* Validation */
render_code = """/* Render Integration Panel */
if(MAP.integrations){const ig=document.getElementById("integGrid");if(ig){ig.innerHTML=MAP.integrations.map(card=>{const bs=card.status==="broken"?"broken":card.status==="ok"?"healthy":"unknown";const rowsHtml=(card.rows||[]).map(r=>`<div class="integ-row"><span class="integ-lbl">${r.l}</span><span class="integ-val${r.cls===' err'?' err':''}">${r.v}</span></div>`).join("");const diagHtml=card.diagnosis?`<div class="integ-diag">⚠ ${card.diagnosis}</div>`:"";const actsHtml=card.actions?`<div class="integ-actions"><div class="integ-actions-title">Actions</div>${card.actions.map(a=>`<div class="integ-act">• ${a}</div>`).join("")}</div>`:"";return `<div class="integ-card"><div class="integ-hdr"><span style="font-size:1rem">${card.icon}</span><span class="integ-name">${card.name}</span><span class="integ-badge ${bs}">${card.label}</span></div>${rowsHtml}${diagHtml}${actsHtml}</div>`;}).join("");}}
"""
anchor3 = '/* Validation */'
if 'Render Integration Panel' not in content and anchor3 in content:
    content = content.replace(anchor3, render_code + '\n/* Validation */', 1)
    print("Added integration rendering code")
else:
    print("Rendering already exists or anchor not found")

path.write_text(content, encoding='utf-8')
print(f"File written: {len(content)} bytes")

# Verify
for check in ['const INTEGRATIONS', 'integGrid', 'Render Integration Panel']:
    print(f"  {check}: {'✅' if check in content else '❌'}")