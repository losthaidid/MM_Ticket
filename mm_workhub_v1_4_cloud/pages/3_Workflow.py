from __future__ import annotations

import pandas as pd
import streamlit as st

from db import connect, fetch_all, init_db
from ui import page_setup

page_setup("Workflow Progress", "✅")
init_db()

if "workflow_notice" in st.session_state:
    st.success(st.session_state.pop("workflow_notice"))

rows = fetch_all(
    """
    SELECT t.id, t.ams_ticket, t.description, t.priority, t.status,
           COALESCE(AVG(s.completed),0) progress,
           COUNT(s.id) stage_count
    FROM tickets t LEFT JOIN ticket_stages s ON s.ticket_id=t.id
    GROUP BY t.id ORDER BY progress ASC, t.ams_ticket
    """
)
if not rows:
    st.info("Import your workbook to populate workflow data.")
    st.stop()

df = pd.DataFrame(rows)
df["Progress"] = (df["progress"] * 100).round().astype(int)
st.dataframe(
    df[["ams_ticket", "description", "priority", "status", "Progress", "stage_count"]].rename(
        columns={
            "ams_ticket": "Ticket",
            "description": "Description",
            "priority": "Priority",
            "status": "Status",
            "stage_count": "Stages",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

active = [r for r in rows if (r.get("status") or "").lower() != "closed"] or rows
labels = [f"{r['ams_ticket']} — {r['description'] or ''}" for r in active]
sel = st.selectbox("Manage workflow", labels)
ticket = active[labels.index(sel)]
stages = fetch_all("SELECT * FROM ticket_stages WHERE ticket_id=? ORDER BY stage_order, id", (ticket["id"],))

st.caption("Edit stage names or completion values directly. Add or remove rows in the table, then save.")

editor_df = pd.DataFrame(
    [
        {
            "Stage": s["stage_name"],
            "Completed": bool(s["completed"]),
        }
        for s in stages
    ],
    columns=["Stage", "Completed"],
)

edited = st.data_editor(
    editor_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Stage": st.column_config.TextColumn("Stage", required=True),
        "Completed": st.column_config.CheckboxColumn("Completed"),
    },
    key=f"workflow_editor_{ticket['id']}",
)

c1, c2 = st.columns(2)
if c1.button("Save workflow changes", type="primary", use_container_width=True):
    cleaned = []
    seen = set()
    error = None
    for _, row in edited.iterrows():
        name = str(row.get("Stage") or "").strip()
        if not name:
            error = "Stage names cannot be blank. Delete the blank row or enter a stage name."
            break
        key = name.casefold()
        if key in seen:
            error = f"Duplicate stage name: {name}"
            break
        seen.add(key)
        cleaned.append((name, 1 if bool(row.get("Completed")) else 0))

    if error:
        st.error(error)
    else:
        with connect() as conn:
            conn.execute("DELETE FROM ticket_stages WHERE ticket_id=?", (ticket["id"],))
            for order, (name, completed) in enumerate(cleaned, start=1):
                conn.execute(
                    "INSERT INTO ticket_stages(ticket_id,stage_name,stage_order,completed) VALUES (?,?,?,?)",
                    (ticket["id"], name, order, completed),
                )
        st.session_state["workflow_notice"] = f"Workflow updated for {ticket['ams_ticket']}."
        st.rerun()

if c2.button("Delete entire workflow", use_container_width=True):
    with connect() as conn:
        conn.execute("DELETE FROM ticket_stages WHERE ticket_id=?", (ticket["id"],))
    st.session_state["workflow_notice"] = f"Workflow deleted for {ticket['ams_ticket']}."
    st.rerun()

if len(edited):
    completed_count = int(edited["Completed"].fillna(False).astype(bool).sum())
    st.metric("Current progress", f"{completed_count / len(edited) * 100:.0f}%")
else:
    st.info("This ticket currently has no workflow stages. Add rows above and save to create a workflow.")
