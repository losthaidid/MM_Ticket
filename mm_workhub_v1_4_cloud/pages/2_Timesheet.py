from __future__ import annotations

from datetime import date, time, datetime

import pandas as pd
import streamlit as st

from db import connect, fetch_all, init_db
from ui import page_setup

page_setup("Timesheet", "🕒")
init_db()

if "timesheet_notice" in st.session_state:
    st.success(st.session_state.pop("timesheet_notice"))

CATEGORIES = ["Work", "Meeting", "Leave", "Training", "Admin"]


def _hours(work_date, start, end):
    start_dt = datetime.combine(work_date, start)
    end_dt = datetime.combine(work_date, end)
    return (end_dt - start_dt).total_seconds() / 3600


with st.expander("Log time", expanded=True):
    c1, c2, c3 = st.columns(3)
    work_date = c1.date_input("Date", value=date.today(), key="new_work_date")
    start = c2.time_input("Start", value=time(9, 0), key="new_start")
    end = c3.time_input("End", value=time(10, 0), key="new_end")
    activity = st.text_input("Activity", placeholder="[FM-1261] Unit testing in FMQ", key="new_activity")
    reference = st.text_input("Ticket / reference", placeholder="FM-1261 or charge code", key="new_reference")
    category = st.selectbox("Category", CATEGORIES, key="new_category")
    notes = st.text_area("Notes", height=80, key="new_notes")

    if st.button("Add timesheet entry", type="primary"):
        hours = _hours(work_date, start, end)
        if hours <= 0:
            st.error("End time must be after start time.")
        elif not activity.strip():
            st.error("Activity is required.")
        else:
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO timesheets(work_date,start_time,end_time,activity,reference,hours,category,notes)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        work_date.isoformat(),
                        start.strftime("%H:%M"),
                        end.strftime("%H:%M"),
                        activity.strip(),
                        reference.strip() or None,
                        hours,
                        category,
                        notes.strip() or None,
                    ),
                )
            st.session_state["timesheet_notice"] = "Timesheet entry added."
            st.rerun()

manage_rows = fetch_all("SELECT * FROM timesheets ORDER BY work_date DESC, start_time DESC, id DESC")
if manage_rows:
    with st.expander("Edit or delete an entry", expanded=False):
        labels = {
            f"#{r['id']} · {r['work_date']} {r['start_time']}–{r['end_time']} · {r['activity']}": r
            for r in manage_rows
        }
        selected_label = st.selectbox("Select entry", list(labels.keys()))
        selected = labels[selected_label]

        selected_date = date.fromisoformat(selected["work_date"])
        selected_start = datetime.strptime(selected["start_time"][:5], "%H:%M").time()
        selected_end = datetime.strptime(selected["end_time"][:5], "%H:%M").time()
        current_category = selected.get("category") or "Work"
        category_options = CATEGORIES if current_category in CATEGORIES else [current_category] + CATEGORIES

        with st.form(f"edit_timesheet_{selected['id']}"):
            c1, c2, c3 = st.columns(3)
            edit_date = c1.date_input("Date", value=selected_date)
            edit_start = c2.time_input("Start", value=selected_start)
            edit_end = c3.time_input("End", value=selected_end)
            edit_activity = st.text_input("Activity", value=selected.get("activity") or "")
            edit_reference = st.text_input("Ticket / reference", value=selected.get("reference") or "")
            edit_category = st.selectbox("Category", category_options, index=category_options.index(current_category))
            edit_notes = st.text_area("Notes", value=selected.get("notes") or "", height=80)

            csave, cdelete = st.columns(2)
            save = csave.form_submit_button("Save changes", type="primary", use_container_width=True)
            delete = cdelete.form_submit_button("Delete entry", use_container_width=True)

            if save:
                hours = _hours(edit_date, edit_start, edit_end)
                if hours <= 0:
                    st.error("End time must be after start time.")
                elif not edit_activity.strip():
                    st.error("Activity is required.")
                else:
                    with connect() as conn:
                        conn.execute(
                            """
                            UPDATE timesheets
                            SET work_date=?, start_time=?, end_time=?, activity=?, reference=?, hours=?, category=?, notes=?
                            WHERE id=?
                            """,
                            (
                                edit_date.isoformat(),
                                edit_start.strftime("%H:%M"),
                                edit_end.strftime("%H:%M"),
                                edit_activity.strip(),
                                edit_reference.strip() or None,
                                hours,
                                edit_category,
                                edit_notes.strip() or None,
                                selected["id"],
                            ),
                        )
                    st.session_state["timesheet_notice"] = "Timesheet entry updated."
                    st.rerun()

            if delete:
                with connect() as conn:
                    conn.execute("DELETE FROM timesheets WHERE id=?", (selected["id"],))
                st.session_state["timesheet_notice"] = "Timesheet entry deleted."
                st.rerun()

rows = fetch_all("SELECT * FROM timesheets ORDER BY work_date DESC, start_time DESC")
if rows:
    df = pd.DataFrame(rows)
    df["work_date"] = pd.to_datetime(df["work_date"])
    c1, c2 = st.columns(2)
    with c1:
        from_date = st.date_input("From", value=df["work_date"].min().date())
    with c2:
        to_date = st.date_input("To", value=df["work_date"].max().date())
    view = df[(df["work_date"].dt.date >= from_date) & (df["work_date"].dt.date <= to_date)].copy()
    k1, k2 = st.columns(2)
    k1.metric("Hours", f"{view['hours'].sum():.1f}")
    k2.metric("Entries", len(view))
    st.dataframe(
        view[["work_date", "start_time", "end_time", "activity", "reference", "hours", "category"]],
        use_container_width=True,
        hide_index=True,
    )
    daily = view.groupby(view["work_date"].dt.date)["hours"].sum()
    st.subheader("Hours by day")
    st.bar_chart(daily)
else:
    st.info("No timesheet data yet.")
