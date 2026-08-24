# MM WorkHub V1.4 Cloud

Python/Streamlit replacement for `MM Tickets.xlsm`, now prepared for both local and cloud use.

## What changed in V1.4

- Keeps all V1.3 ticket, workflow and timesheet CRUD features.
- Uses **SQLite automatically for local development**.
- Uses **PostgreSQL automatically when cloud database secrets are configured**.
- Designed for **Supabase PostgreSQL + Streamlit Community Cloud**.
- No real workbook, database or credentials are included in this package.
- The app creates its PostgreSQL tables automatically on first launch.

## Local run

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Without cloud secrets the app stores data in `data/workhub.db`.

## Cloud architecture

```text
Private GitHub repository
        |
        v
Streamlit Community Cloud
        |
        v
Supabase PostgreSQL
```

The Streamlit app contains no database password in Git. The PostgreSQL credentials are stored in Streamlit's Secrets settings.

## 1. Create the Supabase database

1. Create a Supabase project.
2. Choose a region close to you; Southeast Asia / Singapore is appropriate for Malaysia when available.
3. In Supabase, open **Connect** and select the **Session pooler** connection details.
4. Record these values:
   - host
   - port (normally `5432` for Session pooler)
   - database name (`postgres`)
   - user (normally `postgres.<project-ref>`)
   - database password
5. You do **not** need to create tables manually. MM WorkHub calls `init_db()` and creates them on first launch.

## 2. Create a private GitHub repository

Create a private repository such as `mm-workhub` and upload the contents of this folder.

If Git is installed locally:

```bash
git init
git add .
git commit -m "MM WorkHub V1.4 Cloud"
git branch -M main
git remote add origin YOUR_PRIVATE_GITHUB_REPOSITORY_URL
git push -u origin main
```

The included `.gitignore` prevents normal accidental commits of `.xlsm`, `.xlsx`, CSV files, local SQLite databases and `.streamlit/secrets.toml`.

## 3. Deploy to Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud and connect your GitHub account.
2. Create an app from the private `mm-workhub` repository.
3. Branch: `main`.
4. Entrypoint: `app.py`.
5. Open **Advanced settings -> Secrets**.
6. Paste the following, replacing the placeholders with the Session pooler values from Supabase:

```toml
[database]
host = "YOUR_POOLER_HOST"
port = 5432
dbname = "postgres"
user = "postgres.YOUR_PROJECT_REF"
password = "YOUR_DATABASE_PASSWORD"
sslmode = "require"
```

7. Save the secrets and deploy/reboot the app.
8. The sidebar should show **Database: Cloud PostgreSQL**. If it says Local SQLite, the secrets were not configured correctly.

## 4. Keep the app private

This app contains work-ticket and timesheet information. In Streamlit's app sharing settings, use **Only specific people can view this app**. Do not make it public unless the dataset is sanitized.

## 5. Load your existing workbook

After the cloud app opens:

1. Upload `MM Tickets.xlsm` from the Dashboard sidebar.
2. Confirm replacement.
3. Click **Replace data from workbook**.
4. Verify the imported counts.

After that, create/edit/delete records directly in the website. They will be stored in Supabase rather than on one laptop.

## Data mapping

| Workbook | MM WorkHub |
|---|---|
| `Main` | `tickets` + `ticket_updates` |
| `Ticket tracker` | `ticket_stages` |
| `Date` | `timesheets` |

`FS TWMS` remains intentionally ignored.

## Security rules

Never commit any of the following to GitHub:

- your real `MM Tickets.xlsm`
- `data/workhub.db`
- `.streamlit/secrets.toml`
- Supabase database passwords

Use a **private GitHub repository** and a **private Streamlit app** for real work data.
