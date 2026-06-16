"""
Add Reviews panel to bot-dashboard/index.html.

Injects three things:
1. reviews data into MAP object
2. Reviews section HTML into the innerHTML template
3. Reviews rendering JS after Integration Panel

Run: python scripts/add_review_panel.py
"""

import re

DASHBOARD_PATH = "bot-dashboard/index.html"

def main():
    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # === 1. Inject reviews data into MAP object ===
    # The MAP object ends with: depTypes:["runtime","journal"]}]};
    reviews_data = """,reviews:{source:"PROFESSIONAL_REVIEW.md",verified:"2026-06-13",doc:"docs/claim_verification_professional_review.md",total:20,contradicted:8,partialContradicted:3,partialConfirmed:3,confirmed:3,notVerifiable:3,severity:{critical:3,high:2,medium:1}}"""

    map_end = 'depTypes:["runtime","journal"]}]};'
    if map_end in html:
        html = html.replace(map_end, map_end[:-1] + reviews_data + "};", 1)
        print("✓ Injected reviews data into MAP object")
    else:
        print("✗ Could not find MAP object end anchor. Trying alternate...")
        # Fallback: find the last }; that closes MAP
        alt_anchor = 'depTypes:["runtime","journal"]'
        if alt_anchor in html:
            idx = html.index(alt_anchor)
            end_idx = html.index("};", idx) + 2
            html = html[:end_idx-2] + reviews_data + "};"
            print("✓ Injected reviews data (alternate method)")
        else:
            print("✗ Could not inject reviews data")

    # === 2. Inject Reviews section HTML ===
    # Insert before <div class="legend-section"><div class="legend-title">Visual Legend</div>
    legend_anchor = '<div class="legend-section"><div class="legend-title">Visual Legend</div>'
    reviews_html = """<div class="review-section" style="margin-top:20px;animation:fadeInUp 0.6s ease-out 0.62s both;"><div class="section-header"><span class="icon">🔍</span><h2>External Review Audit</h2><span class="ref">docs/claim_verification_professional_review.md</span></div><p class="section-desc">Cross-check of PROFESSIONAL_REVIEW.md against codebase (2026-06-13). <strong style="color:var(--negative)">Audit layer, not primary truth source.</strong></p><div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:4px;"><div class="bt-card"><div class="bt-label">Total Claims</div><div class="bt-value">20</div></div><div class="bt-card" style="border-color:#E08070;"><div class="bt-label">Contradicted</div><div class="bt-value" style="color:#E08070;">8</div></div><div class="bt-card" style="border-color:rgba(224,200,112,0.5);"><div class="bt-label">Partial</div><div class="bt-value" style="color:#E0C870;">3+3</div></div><div class="bt-card" style="border-color:#70D89A;"><div class="bt-label">Confirmed</div><div class="bt-value" style="color:#70D89A;">3</div></div><div class="bt-card" style="border-color:#7A7068;"><div class="bt-label">Not Verifiable</div><div class="bt-value" style="color:#7A7068;">3</div></div></div><div style="font-size:0.5rem;color:var(--text-muted);padding:4px 4px 0;font-style:italic;">Renders static summary. Full table at docs/claim_verification_professional_review.md.</div></div><div class="legend-section""" 
    
    if legend_anchor in html:
        html = html.replace('<div class="legend-section', reviews_html, 1)
        print("✓ Injected Reviews section HTML")
    else:
        print("✗ Could not find legend section anchor")
        # Try alternate - just before backtest section
        bt_anchor = '{srcBadge("backtest")}</p><div class="backtest-grid" id="btGrid"></div></div>'
        if bt_anchor in html:
            idx = html.index(bt_anchor) + len(bt_anchor)
            html = html[:idx] + reviews_html.replace('<div class="legend-section', '') + html[idx:]
            print("✓ Injected Reviews section HTML (after backtest)")
        else:
            print("✗ Could not inject Reviews HTML")

    # === 3. Inject Reviews rendering JS ===
    # After /* Render Integration Panel */ block, before /* Validation */
    validation_anchor = '/* Validation */'
    review_js = """\n/* Render Reviews Panel */
if(MAP.reviews){const rv=MAP.reviews;const rg=document.createElement("div");rg.className="review-section";rg.style.cssText="margin-top:16px;animation:fadeInUp 0.6s ease-out 0.62s both;";rg.innerHTML='<div class="section-header"><span class="icon">🔍</span><h2>External Review Audit</h2><span class="ref">'+rv.doc+'</span></div><p class="section-desc">Cross-check of PROFESSIONAL_REVIEW.md against codebase ('+rv.verified+'). <strong style="color:var(--negative)">Audit layer, not primary truth source.</strong></p><div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:4px;"><div class="bt-card"><div class="bt-label">Total</div><div class="bt-value">'+rv.total+'</div></div><div class="bt-card" style="border-color:#E08070;"><div class="bt-label">Contradicted</div><div class="bt-value" style="color:#E08070;">'+rv.contradicted+'</div></div><div class="bt-card" style="border-color:rgba(224,200,112,0.5);"><div class="bt-label">Partial</div><div class="bt-value" style="color:#E0C870;">'+(rv.partialContradicted+rv.partialConfirmed)+'</div></div><div class="bt-card" style="border-color:#70D89A;"><div class="bt-label">Confirmed</div><div class="bt-value" style="color:#70D89A;">'+rv.confirmed+'</div></div><div class="bt-card" style="border-color:#7A7068;"><div class="bt-label">Not Verif.</div><div class="bt-value" style="color:#7A7068;">'+rv.notVerifiable+'</div></div></div><div style="font-size:0.5rem;color:var(--text-muted);padding:4px 4px 0;font-style:italic;">Severity distribution: '+(rv.severity?Object.entries(rv.severity).map(([k,v])=>k+': '+v).join(' &middot; '):'See full doc')+'.</div></div>';document.querySelector(".app")?document.querySelector(".app").appendChild(rg):null;}
"""

    if validation_anchor in html:
        html = html.replace(validation_anchor, review_js + validation_anchor, 1)
        print("✓ Injected Reviews rendering JS")
    else:
        print("✗ Could not find Validation anchor")

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ bot-dashboard/index.html updated")

if __name__ == "__main__":
    main()