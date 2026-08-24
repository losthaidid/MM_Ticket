from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from db import fetch_all, init_db
from ui import page_setup

page_setup("Reports", "📄")
init_db()

end = st.date_input("Report date", value=date.today())
period = st.selectbox("Period", ["Daily", "Weekly", "Monthly"])
if period == "Daily":
    start = end
elif period == "Weekly":
    start = end - timedelta(days=6)
else:
    start = end.replace(day=1)

hours = fetch_all("SELECT * FROM timesheets WHERE work_date BETWEEN ? AND ? ORDER BY work_date,start_time", (start.isoformat(), end.isoformat()))
updates = fetch_all("""
SELECT t.ams_ticket, t.description, u.update_date, u.update_text
FROM ticket_updates u JOIN tickets t ON t.id=u.ticket_id
WHERE u.update_date BETWEEN ? AND ?
ORDER BY u.update_date DESC, t.ams_ticket
""", (start.isoformat(), end.isoformat()))
active = fetch_all("""
SELECT t.ams_ticket,t.description,t.priority,t.object_status,t.action_status,COALESCE(AVG(s.completed),0) progress
FROM tickets t LEFT JOIN ticket_stages s ON s.ticket_id=t.id
WHERE lower(COALESCE(t.status,'')) <> 'closed'
GROUP BY t.id ORDER BY progress DESC
""")

total_hours = sum(r["hours"] for r in hours)
st.metric("Logged hours", f"{total_hours:.1f}")

lines = [f"# {period} Work Report", f"Period: {start.isoformat()} to {end.isoformat()}", ""]
lines.append(f"## Time logged — {total_hours:.1f} hours")
if hours:
    by_ref = {}
    for r in hours:
        key = r.get("reference") or r.get("category") or "Other"
        by_ref[key] = by_ref.get(key, 0) + r["hours"]
    for key, val in sorted(by_ref.items(), key=lambda x: -x[1]):
        lines.append(f"- {key}: {val:.1f}h")
else:
    lines.append("- No timesheet entries in this period.")

lines += ["", "## Ticket updates"]
if updates:
    for u in updates:
        lines.append(f"- **{u['ams_ticket']}** ({u['update_date']}): {u['update_text']}")
else:
    lines.append("- No dated ticket updates in this period.")

lines += ["", "## Active tickets"]
for t in active:
    waiting = " / ".join(x for x in [t.get("object_status"), t.get("action_status")] if x)
    lines.append(f"- **{t['ams_ticket']}** — {t['progress']*100:.0f}% — {waiting or 'No waiting status'}")

report = "\n".join(lines)
st.markdown(report)
st.download_button("Download report (.md)", report, file_name=f"mm-work-report-{end.isoformat()}.md", mime="text/markdown")
