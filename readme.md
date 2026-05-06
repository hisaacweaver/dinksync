# DinkSync

DinkSync is a local Streamlit app for coordinating pickleball practice schedules. An admin creates a schedule window, adds possible practice start times, shares a token with players, reviews availability responses, assigns players and locations to slots, marks one practice lead, and views the final schedule.

Players use the shared token to submit or update the practice slots they are available for while submissions are open. The player page uses the same Monday-through-Saturday calendar grid as the admin availability setup page.

Players can be assigned to Premier, Challenger, or Reserves teams. Schedule creation defaults to Premier and Challenger players, with Reserves available as an optional filter.

## Project Structure

```text

app.py
db.py
models.py
supabase_schema.sql
views/
    admin_create_availability.py
    player_submit_availability.py
    admin_view_responses.py
    admin_create_schedule.py
    view_schedule.py
    admin_data_management.py
data/
    scheduler.db
.streamlit/
    secrets.toml
```

## Scheduling Flow

Availability setup uses a WhenIsGood-style grid. Each schedule window displays weeks in separate sections, Monday through Saturday only. Sundays are not shown.

The admin and player availability pages include both a Calendar layout for laptop screens and a Day-by-day layout for narrow mobile screens.

Default practice start times are:

- 6 AM
- 8 AM
- 3 PM
- 4 PM
- 6 PM
- 7 PM
- 8 PM
- 9 PM

Practice slots store a start time. The app automatically stores an end time two hours later for internal use, but the UI displays only the start time.

Locations are not selected during availability setup. The admin chooses a saved location or enters a custom location when creating the final schedule.

## Install

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run Locally

```bash
streamlit run app.py
```

Use the Streamlit sidebar to move through the admin and player pages.

Admin pages require the sidebar login. For local development, `.streamlit/secrets.toml` contains:

```toml
ADMIN_PASSWORD = "byupickleball"
```

The player availability page remains accessible by token at:

```text
https://byupbscheduling.streamlit.app/Player_Submit_Availability?token=<public_token>
```

## Local Database

DinkSync uses SQLite for local development. On startup the app creates `data/scheduler.db`, creates missing tables, and seeds sample players if the players table is empty:

- Isaac
- Eli
- Benjamin
- Tyler

The database file is local development data and can be deleted to start over.

## Supabase / Production Database

Local development uses SQLite by default:

```toml
DB_BACKEND = "sqlite"
```

For production, create the tables in Supabase by opening the Supabase SQL Editor and running `supabase_schema.sql`.

Then set these secrets in `.streamlit/secrets.toml` or your production Streamlit secrets:

```toml
DB_BACKEND = "supabase"
SUPABASE_DB_URL = "postgresql://postgres.<project-ref>:<password>@aws-0-us-west-1.pooler.supabase.com:5432/postgres"
```

Use the direct Postgres connection string from Supabase. Keep the SQLite setting for local dev.

## Future Hosted Database

The database layer is isolated in `db.py` and supports SQLite for local development plus Supabase/Postgres for production.
