from __future__ import annotations

import pandas as pd
import streamlit as st

from db import backend_name, fetch_all, init_db
from importer import import_workbook
from ui import page_setup

page_setup("Dashboard", "🧭")
init_db()

with st.sidebar:
    st.header("MM WorkHub")
    st.caption("SAP MM work, tickets and timesheets")
    if backend_name() == "postgres":
        st.success("Database: Cloud PostgreSQL")
    else:
        st.warning("Database: Local SQLite. Configure Supabase secrets before using this app in the cloud.")
    st.divider()
    uploaded = st.file_uploader("Import MM Tickets.xlsm", type=["xlsm", "xlsx"])
    if uploaded is not None:
        st.caption(f"Selected: {uploaded.name} · {uploaded.size / 1024:.0f} KB")
        st.warning("Importing replaces the current ticket, workflow, and timesheet data. Export or back up anything you need first.")
        confirm_replace = st.checkbox("I understand this will replace current data")
        if st.button(
            "Replace data from workbook",
            type="primary",
            use_container_width=True,
            disabled=not confirm_replace,
        ):
            try:
                with st.spinner("Importing workbook..."):
                    stats = import_workbook(uploaded, reset=True)
                st.session_state["last_import"] = stats
                st.session_state["last_import_file"] = uploaded.name
            except Exception as exc:
                st.session_state["import_error"] = str(exc)

    if "import_error" in st.session_state:
        st.error(f"Import failed: {st.session_state.pop('import_error')}")

    if "last_import" in st.session_state:
        stats = st.session_state["last_import"]
        st.success(
            f"Import complete: {stats['tickets']} tickets, {stats['updates']} updates, "
            f"{stats['stages']} workflow stages, and {stats['timesheets']} timesheet entries."
        )
        st.caption(f"Last imported file: {st.session_state.get('last_import_file', 'workbook')}")

summary = fetch_all(
    """
    SELECT
      COUNT(*) AS total,
      SUM(CASE WHEN lower(coalesce(status,''))='pending' THEN 1 ELSE 0 END) AS pending,
      SUM(CASE WHEN lower(coalesce(status,''))='closed' THEN 1 ELSE 0 END) AS closed,
      SUM(CASE WHEN lower(coalesce(status,'')) NOT IN ('closed','pending') OR status IS NULL THEN 1 ELSE 0 END) AS other
    FROM tickets
    """
)
summary = summary[0] if summary else {"total": 0, "pending": 0, "closed": 0, "other": 0}

hours = fetch_all("SELECT COALESCE(SUM(hours),0) AS h FROM timesheets")
total_hours = hours[0]["h"] if hours else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Tickets", summary["total"] or 0)
c2.metric("Pending", summary["pending"] or 0)
c3.metric("Closed", summary["closed"] or 0)
c4.metric("Logged Hours", f"{total_hours:.1f}")

st.subheader("Needs attention")
rows = fetch_all(
    """
    SELECT t.id, t.ams_ticket, t.description, t.priority, t.object_status, t.action_status,
           t.last_update_date,
           COALESCE(AVG(s.completed),0) AS progress
    FROM tickets t
    LEFT JOIN ticket_stages s ON s.ticket_id=t.id
    WHERE lower(COALESCE(t.status,'')) <> 'closed'
    GROUP BY t.id
    ORDER BY CASE t.priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END,
             COALESCE(t.last_update_date,'1900-01-01') ASC
    """
)

if rows:
    df = pd.DataFrame(rows)
    df["Progress"] = (df["progress"] * 100).round().astype(int).astype(str) + "%"
    df["Waiting On"] = df[["object_status", "action_status"]].fillna("").agg(" / ".join, axis=1).str.strip(" /")
    st.dataframe(
        df[["ams_ticket", "description", "priority", "Waiting On", "Progress", "last_update_date"]].rename(
            columns={
                "ams_ticket": "Ticket",
                "description": "Description",
                "priority": "Priority",
                "last_update_date": "Last Update",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No ticket data yet. Import your workbook from the sidebar.")

st.subheader("Ticket progress")
progress = fetch_all(
    """
    SELECT t.ams_ticket, t.description, COALESCE(AVG(s.completed),0) AS progress
    FROM tickets t LEFT JOIN ticket_stages s ON s.ticket_id=t.id
    WHERE lower(COALESCE(t.status,'')) <> 'closed'
    GROUP BY t.id ORDER BY progress ASC
    """
)
if progress:
    chart = pd.DataFrame(progress)
    chart["progress"] = (chart["progress"] * 100).round(1)
    st.bar_chart(chart.set_index("ams_ticket")["progress"], horizontal=True)

st.caption("Use the pages in the left navigation for Tickets, Timesheet, Workflow and Reports.")
