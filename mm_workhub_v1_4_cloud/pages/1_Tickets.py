from __future__ import annotations

from datetime import date

import streamlit as st

from db import connect, fetch_all, init_db
from importer import STAGES
from ui import page_setup

page_setup("Tickets", "🎫")
init_db()

if "ticket_notice" in st.session_state:
    st.success(st.session_state.pop("ticket_notice"))

COMMON_PRIORITIES = ["High", "Medium", "Low"]
COMMON_STATUSES = ["Pending", "In Progress", "On Hold", "Closed"]
COMMON_TYPES = ["New", "Change", "Incident", "Request"]


def _options(current, defaults):
    values = []
    if current and current not in defaults:
        values.append(current)
    values.extend(defaults)
    return values


def _clean(value):
    value = str(value or "").strip()
    return value or None


create_tab, manage_tab = st.tabs(["Create ticket", "View / edit tickets"])

with create_tab:
    st.subheader("Create ticket")
    st.caption("Create the ticket once here. Workflow stages and updates will reference this ticket record.")

    with st.form("create_ticket", clear_on_submit=False):
        c1, c2 = st.columns(2)
        new_ams = c1.text_input("AMS ticket *", placeholder="FM-1300")
        new_jira = c2.text_input("JIRA / charge code", placeholder="8280000000")

        new_description = st.text_area("Description *", height=90)

        c1, c2, c3 = st.columns(3)
        new_created = c1.date_input("Created date", value=date.today())
        new_priority = c2.selectbox("Priority", COMMON_PRIORITIES, index=1)
        new_status = c3.selectbox("Status", COMMON_STATUSES, index=0)

        c1, c2 = st.columns(2)
        new_pic = c1.text_input("PIC")
        new_type = c2.selectbox("Ticket type", COMMON_TYPES)

        c1, c2, c3 = st.columns(3)
        new_object = c1.text_input("Object status")
        new_action = c2.text_input("Action / waiting on")
        new_transport = c3.text_input("Environment / latest transport")

        new_mandays = st.number_input("Mandays chargeable", min_value=0.0, value=0.0, step=0.5)
        create_workflow = st.checkbox("Create standard 12-stage workflow", value=True)

        submitted = st.form_submit_button("Create ticket", type="primary", use_container_width=True)
        if submitted:
            ams = new_ams.strip()
            if not ams:
                st.error("AMS ticket is required.")
            elif not new_description.strip():
                st.error("Description is required.")
            else:
                with connect() as conn:
                    exists = conn.execute(
                        "SELECT id FROM tickets WHERE lower(ams_ticket)=lower(?)",
                        (ams,),
                    ).fetchone()
                    if exists:
                        st.error(f"Ticket {ams} already exists.")
                    else:
                        cur = conn.execute(
                            """
                            INSERT INTO tickets (
                                ams_ticket,jira_ticket,description,date_created,priority,pic,status,
                                object_status,action_status,latest_transport,ticket_type,mandays_chargeable
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                            RETURNING id
                            """,
                            (
                                ams,
                                _clean(new_jira),
                                new_description.strip(),
                                new_created.isoformat(),
                                new_priority,
                                _clean(new_pic),
                                new_status,
                                _clean(new_object),
                                _clean(new_action),
                                _clean(new_transport),
                                new_type,
                                float(new_mandays),
                            ),
                        )
                        ticket_id = cur.fetchone()[0]
                        if create_workflow:
                            for order, stage_name in enumerate(STAGES, start=1):
                                conn.execute(
                                    "INSERT INTO ticket_stages(ticket_id,stage_name,stage_order,completed) VALUES (?,?,?,0)",
                                    (ticket_id, stage_name, order),
                                )
                st.session_state["ticket_notice"] = f"Ticket {ams} created."
                st.rerun()

with manage_tab:
    left, right = st.columns([2, 1])
    with left:
        search = st.text_input("Search", placeholder="FM-1062, JIRA number, description, PIC...")
    with right:
        status_filter = st.selectbox("Status filter", ["All"] + COMMON_STATUSES)

    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if search:
        query += " AND (ams_ticket LIKE ? OR jira_ticket LIKE ? OR description LIKE ? OR pic LIKE ?)"
        q = f"%{search}%"
        params += [q, q, q, q]
    if status_filter != "All":
        query += " AND lower(COALESCE(status,''))=lower(?)"
        params.append(status_filter)
    query += " ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END, ams_ticket"
    rows = fetch_all(query, tuple(params))

    if not rows:
        st.info("No tickets match the current filter. Use the Create ticket tab to add one.")
    else:
        labels = [f"{r['ams_ticket']} — {r['description'] or ''}" for r in rows]
        selected_label = st.selectbox("Open ticket", labels)
        row = rows[labels.index(selected_label)]
        ticket_id = row["id"]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Status", row.get("status") or "—")
        m2.metric("Priority", row.get("priority") or "—")
        m3.metric("PIC", row.get("pic") or "—")
        m4.metric("Environment", row.get("latest_transport") or "—")

        st.subheader(row["ams_ticket"])
        st.write(row.get("description") or "")
        st.caption(
            f"JIRA / Charge Code: {row.get('jira_ticket') or '—'} · "
            f"Type: {row.get('ticket_type') or '—'} · Created: {row.get('date_created') or '—'}"
        )

        with st.expander("Edit ticket details", expanded=False):
            current_priority = row.get("priority") or "Medium"
            priority_options = _options(current_priority, COMMON_PRIORITIES)
            current_status = row.get("status") or "Pending"
            status_options = _options(current_status, COMMON_STATUSES)
            current_type = row.get("ticket_type") or "New"
            type_options = _options(current_type, COMMON_TYPES)

            try:
                created_value = date.fromisoformat(row.get("date_created") or "")
            except ValueError:
                created_value = date.today()

            with st.form(f"edit_ticket_{ticket_id}"):
                c1, c2 = st.columns(2)
                edit_ams = c1.text_input("AMS ticket *", value=row.get("ams_ticket") or "")
                edit_jira = c2.text_input("JIRA / charge code", value=row.get("jira_ticket") or "")
                edit_description = st.text_area("Description *", value=row.get("description") or "", height=90)

                c1, c2, c3 = st.columns(3)
                edit_created = c1.date_input("Created date", value=created_value)
                edit_priority = c2.selectbox(
                    "Priority", priority_options, index=priority_options.index(current_priority)
                )
                edit_status = c3.selectbox(
                    "Status", status_options, index=status_options.index(current_status)
                )

                c1, c2 = st.columns(2)
                edit_pic = c1.text_input("PIC", value=row.get("pic") or "")
                edit_type = c2.selectbox("Ticket type", type_options, index=type_options.index(current_type))

                c1, c2, c3 = st.columns(3)
                edit_object = c1.text_input("Object status", value=row.get("object_status") or "")
                edit_action = c2.text_input("Action / waiting on", value=row.get("action_status") or "")
                edit_transport = c3.text_input(
                    "Environment / latest transport", value=row.get("latest_transport") or ""
                )

                edit_mandays = st.number_input(
                    "Mandays chargeable",
                    min_value=0.0,
                    value=float(row.get("mandays_chargeable") or 0.0),
                    step=0.5,
                )

                save_ticket = st.form_submit_button("Save ticket changes", type="primary", use_container_width=True)
                if save_ticket:
                    ams = edit_ams.strip()
                    if not ams:
                        st.error("AMS ticket is required.")
                    elif not edit_description.strip():
                        st.error("Description is required.")
                    else:
                        with connect() as conn:
                            duplicate = conn.execute(
                                "SELECT id FROM tickets WHERE lower(ams_ticket)=lower(?) AND id<>?",
                                (ams, ticket_id),
                            ).fetchone()
                            if duplicate:
                                st.error(f"Another ticket already uses {ams}.")
                            else:
                                old_ams = row["ams_ticket"]
                                conn.execute(
                                    """
                                    UPDATE tickets SET
                                        ams_ticket=?, jira_ticket=?, description=?, date_created=?, priority=?,
                                        pic=?, status=?, object_status=?, action_status=?, latest_transport=?,
                                        ticket_type=?, mandays_chargeable=?, updated_at=CURRENT_TIMESTAMP
                                    WHERE id=?
                                    """,
                                    (
                                        ams,
                                        _clean(edit_jira),
                                        edit_description.strip(),
                                        edit_created.isoformat(),
                                        edit_priority,
                                        _clean(edit_pic),
                                        edit_status,
                                        _clean(edit_object),
                                        _clean(edit_action),
                                        _clean(edit_transport),
                                        edit_type,
                                        float(edit_mandays),
                                        ticket_id,
                                    ),
                                )
                                # Keep exact ticket references in timesheets aligned if the AMS number changes.
                                if old_ams != ams:
                                    conn.execute(
                                        "UPDATE timesheets SET reference=? WHERE lower(reference)=lower(?)",
                                        (ams, old_ams),
                                    )
                        st.session_state["ticket_notice"] = f"Ticket {ams} updated."
                        st.rerun()

        st.subheader("Workflow")
        stages = fetch_all("SELECT * FROM ticket_stages WHERE ticket_id=? ORDER BY stage_order", (ticket_id,))
        if stages:
            progress = sum(s["completed"] for s in stages) / len(stages)
            st.progress(progress, text=f"{progress * 100:.0f}% complete")
            cols = st.columns(3)
            for i, stage in enumerate(stages):
                cols[i % 3].write(("✅ " if stage["completed"] else "⬜ ") + stage["stage_name"])
        else:
            st.caption("No stage data available for this ticket.")

        st.subheader("Activity history")
        updates = fetch_all(
            """
            SELECT * FROM ticket_updates WHERE ticket_id=?
            ORDER BY CASE WHEN update_date IS NULL THEN 1 ELSE 0 END, update_date DESC, source_order DESC
            """,
            (ticket_id,),
        )
        if updates:
            for update in updates:
                st.markdown(f"**{update['update_date'] or 'Date not captured'}**  \\n{update['update_text']}")
        else:
            st.caption("No updates recorded yet.")

        with st.expander("Add update", expanded=False):
            update_date = st.date_input("Date", value=date.today(), key=f"update_date_{ticket_id}")
            update_text = st.text_area("Update", key=f"update_text_{ticket_id}")
            if st.button("Save update", type="primary", key=f"save_update_{ticket_id}"):
                if update_text.strip():
                    with connect() as conn:
                        max_order = conn.execute(
                            "SELECT COALESCE(MAX(source_order),0) FROM ticket_updates WHERE ticket_id=?",
                            (ticket_id,),
                        ).fetchone()[0]
                        conn.execute(
                            "INSERT INTO ticket_updates(ticket_id,update_date,update_text,source_order) VALUES (?,?,?,?)",
                            (ticket_id, update_date.isoformat(), update_text.strip(), max_order + 1),
                        )
                        conn.execute(
                            "UPDATE tickets SET last_update_date=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (update_date.isoformat(), ticket_id),
                        )
                    st.session_state["ticket_notice"] = "Update saved."
                    st.rerun()
                else:
                    st.warning("Enter an update first.")

        with st.expander("Delete ticket", expanded=False):
            update_count = fetch_all(
                "SELECT COUNT(*) AS n FROM ticket_updates WHERE ticket_id=?", (ticket_id,)
            )[0]["n"]
            stage_count = fetch_all(
                "SELECT COUNT(*) AS n FROM ticket_stages WHERE ticket_id=?", (ticket_id,)
            )[0]["n"]
            timesheet_count = fetch_all(
                "SELECT COUNT(*) AS n FROM timesheets WHERE lower(reference)=lower(?)",
                (row["ams_ticket"],),
            )[0]["n"]

            st.warning(
                f"Deleting {row['ams_ticket']} permanently removes the ticket plus "
                f"{update_count} history update(s) and {stage_count} workflow stage(s)."
            )
            if timesheet_count:
                st.info(
                    f"There are {timesheet_count} timesheet entr{'y' if timesheet_count == 1 else 'ies'} "
                    f"referencing {row['ams_ticket']}. They are kept by default so logged work is not erased."
                )
                delete_timesheets = st.checkbox(
                    f"Also delete those {timesheet_count} linked timesheet entr{'y' if timesheet_count == 1 else 'ies'}",
                    key=f"delete_timesheets_{ticket_id}",
                )
            else:
                delete_timesheets = False

            confirm_delete = st.checkbox(
                f"I understand that deleting {row['ams_ticket']} cannot be undone",
                key=f"confirm_delete_ticket_{ticket_id}",
            )
            if st.button(
                "Delete ticket permanently",
                disabled=not confirm_delete,
                use_container_width=True,
                key=f"delete_ticket_{ticket_id}",
            ):
                with connect() as conn:
                    if delete_timesheets:
                        conn.execute(
                            "DELETE FROM timesheets WHERE lower(reference)=lower(?)",
                            (row["ams_ticket"],),
                        )
                    # ticket_updates and ticket_stages are removed automatically by ON DELETE CASCADE.
                    conn.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
                st.session_state["ticket_notice"] = f"Ticket {row['ams_ticket']} deleted."
                st.rerun()
