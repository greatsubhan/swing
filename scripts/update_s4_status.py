"""Update strategy_four bot card status from error to idle after OANDA fix verification."""
with open("bot-dashboard/index.html", encoding="utf-8") as f:
    dash = f.read()

# The strategy_four bot card has status:"error" — change to "idle" since OANDA fix is verified
# We need to be precise: only change the strategy_four bot card's status, not the node entries
# Strategy four bot card is: {id:"strategy_four",... status:"error",...
dash = dash.replace(
    'id:"strategy_four",displayName:"CWT",strategy:"Cambist With Trend",strategyClass:"CwtStrategy",enabled:true,dispatch:"discord_and_oanda",granularity:"M5",interval:"5 min",watchlist:"core-mixed",status:"error"',
    'id:"strategy_four",displayName:"CWT",strategy:"Cambist With Trend",strategyClass:"CwtStrategy",enabled:true,dispatch:"discord_and_oanda",granularity:"M5",interval:"5 min",watchlist:"core-mixed",status:"idle"'
)

with open("bot-dashboard/index.html", "w", encoding="utf-8") as f:
    f.write(dash)

# Verify
with open("bot-dashboard/index.html", encoding="utf-8") as f:
    check = f.read()

# Count bot status values
import re
idle_count = len(re.findall(r'id:"[^"]+",.*?status:"idle"', check))
error_count = len(re.findall(r'id:"[^"]+",.*?status:"error"', check))

has_idle_s4 = 'id:"strategy_four"' in check and check.split('id:"strategy_four"')[1][:200].count('status:"idle"') > 0

print(f"[{'PASS' if has_idle_s4 else 'FAIL'}] strategy_four status changed to idle")
print(f"  Bot cards: {idle_count} idle, {error_count} error")
print(f"  Expected: 4 idle (nas100, strategy_two, strategy_four, command_bot), 2 error (little_rzy, strategy_five still has OANDA 401 on market data)")

# Wait - strategy_five should also be updated since its dispatch is now fixed
# strategy_five status is "idle" in the dashboard which is correct (dispatch fixed, but no journal yet)
# Let's verify strategy_five is idle
has_idle_s5 = 'id:"strategy_five"' in check and check.split('id:"strategy_five"')[1][:200].count('status:"idle"') > 0
print(f"[{'PASS' if has_idle_s5 else 'FAIL'}] strategy_five status is idle (dispatch fixed)")