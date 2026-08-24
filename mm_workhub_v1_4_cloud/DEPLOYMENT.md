# MM WorkHub Cloud Deployment Checklist

- [ ] Create a Supabase project in a suitable region.
- [ ] Copy the Supabase **Session pooler** host, user, port and database name.
- [ ] Keep the database password private.
- [ ] Create a **private** GitHub repository.
- [ ] Upload the MM WorkHub V1.4 Cloud source files.
- [ ] Connect Streamlit Community Cloud to GitHub.
- [ ] Create an app using `main` and `app.py`.
- [ ] Add the `[database]` block in Streamlit **Secrets**.
- [ ] Deploy/reboot.
- [ ] Confirm the sidebar says `Database: Cloud PostgreSQL`.
- [ ] Set app visibility to **Only specific people can view this app**.
- [ ] Import `MM Tickets.xlsm` once from the Dashboard.
- [ ] Test create/edit/delete for one ticket, one workflow stage and one timesheet entry.
