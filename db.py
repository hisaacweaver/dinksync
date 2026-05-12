from __future__ import annotations

import os
import secrets
import sqlite3
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "scheduler.db"
SECRETS_PATH = APP_DIR / ".streamlit" / "secrets.toml"

SAMPLE_PLAYERS = ("Isaac", "Eli", "Benjamin", "Tyler")
TEAMS = ("Premier", "Challenger", "Reserves")
DEFAULT_TEAM = "Challenger"
GENDERS = ("Unspecified", "Female", "Male")
DEFAULT_GENDER = "Unspecified"


def get_secret(name: str, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ[name]
    if SECRETS_PATH.exists():
        with SECRETS_PATH.open("rb") as file:
            return str(tomllib.load(file).get(name, default))
    return default


def database_backend() -> str:
    return get_secret("DB_BACKEND", "sqlite").lower()


def is_postgres() -> bool:
    return database_backend() in {"postgres", "postgresql", "supabase"}


def postgres_url() -> str:
    return get_secret("SUPABASE_DB_URL") or get_secret("DATABASE_URL")


def translate_sql(sql: str) -> str:
    return sql.replace("?", "%s")


class PostgresConnection:
    def __init__(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "Postgres backend requires psycopg. Run `pip install -r requirements.txt`."
            ) from exc

        url = postgres_url()
        if not url:
            raise RuntimeError("Set SUPABASE_DB_URL in .streamlit/secrets.toml for Postgres.")
        # Supabase pooler connections can reject psycopg prepared statements.
        self.conn = psycopg.connect(url, row_factory=dict_row, prepare_threshold=None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()

    def execute(self, sql: str, params: Iterable | None = None):
        return self.conn.execute(translate_sql(sql), tuple(params or ()))

    def executemany(self, sql: str, params_seq: Iterable[Iterable]):
        with self.conn.cursor() as cursor:
            cursor.executemany(translate_sql(sql), [tuple(params) for params in params_seq])
            return cursor

    def executescript(self, sql: str) -> None:
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        self.conn.close()


def get_connection():
    if is_postgres():
        return PostgresConnection()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    if is_postgres():
        init_postgres_db()
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                team TEXT NOT NULL DEFAULT 'Challenger',
                gender TEXT NOT NULL DEFAULT 'Unspecified',
                phone_number TEXT,
                practice_group TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS schedule_windows (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                submission_open INTEGER NOT NULL DEFAULT 1,
                public_token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS practice_slots (
                id INTEGER PRIMARY KEY,
                schedule_window_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(schedule_window_id) REFERENCES schedule_windows(id)
            );

            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS availability (
                id INTEGER PRIMARY KEY,
                player_id INTEGER NOT NULL,
                practice_slot_id INTEGER NOT NULL,
                available INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                UNIQUE(player_id, practice_slot_id),
                FOREIGN KEY(player_id) REFERENCES players(id),
                FOREIGN KEY(practice_slot_id) REFERENCES practice_slots(id)
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY,
                practice_slot_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                is_practice_lead INTEGER NOT NULL DEFAULT 0,
                UNIQUE(practice_slot_id, player_id),
                FOREIGN KEY(practice_slot_id) REFERENCES practice_slots(id),
                FOREIGN KEY(player_id) REFERENCES players(id)
            );

            CREATE INDEX IF NOT EXISTS idx_practice_slots_window_time
                ON practice_slots(schedule_window_id, date, start_time);
            CREATE INDEX IF NOT EXISTS idx_availability_slot_available
                ON availability(practice_slot_id, available);
            CREATE INDEX IF NOT EXISTS idx_availability_player_slot
                ON availability(player_id, practice_slot_id);
            CREATE INDEX IF NOT EXISTS idx_assignments_slot
                ON assignments(practice_slot_id);
            """
        )

        ensure_player_columns(conn)

        player_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        if player_count == 0:
            conn.executemany(
                "INSERT INTO players (name, active, team, gender) VALUES (?, 1, ?, ?)",
                [(name, DEFAULT_TEAM, DEFAULT_GENDER) for name in SAMPLE_PLAYERS],
            )

        conn.execute(
            """
            INSERT OR IGNORE INTO locations (name, active)
            SELECT DISTINCT location, 1
            FROM practice_slots
            WHERE TRIM(location) != ''
            """
        )


def init_postgres_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                team TEXT NOT NULL DEFAULT 'Challenger',
                gender TEXT NOT NULL DEFAULT 'Unspecified',
                phone_number TEXT,
                practice_group TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS schedule_windows (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                title TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                submission_open INTEGER NOT NULL DEFAULT 1,
                public_token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS practice_slots (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                schedule_window_id INTEGER NOT NULL REFERENCES schedule_windows(id),
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS availability (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                player_id INTEGER NOT NULL REFERENCES players(id),
                practice_slot_id INTEGER NOT NULL REFERENCES practice_slots(id),
                available INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                UNIQUE(player_id, practice_slot_id)
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                practice_slot_id INTEGER NOT NULL REFERENCES practice_slots(id),
                player_id INTEGER NOT NULL REFERENCES players(id),
                is_practice_lead INTEGER NOT NULL DEFAULT 0,
                UNIQUE(practice_slot_id, player_id)
            );

            CREATE INDEX IF NOT EXISTS idx_practice_slots_window_time
                ON practice_slots(schedule_window_id, date, start_time);
            CREATE INDEX IF NOT EXISTS idx_availability_slot_available
                ON availability(practice_slot_id, available);
            CREATE INDEX IF NOT EXISTS idx_availability_player_slot
                ON availability(player_id, practice_slot_id);
            CREATE INDEX IF NOT EXISTS idx_assignments_slot
                ON assignments(practice_slot_id);
            """
        )

        ensure_postgres_player_columns(conn)

        player_count = conn.execute("SELECT COUNT(*) AS count FROM players").fetchone()["count"]
        if player_count == 0:
            conn.executemany(
                "INSERT INTO players (name, active, team, gender) VALUES (?, 1, ?, ?)",
                [(name, DEFAULT_TEAM, DEFAULT_GENDER) for name in SAMPLE_PLAYERS],
            )

        conn.execute(
            """
            INSERT INTO locations (name, active)
            SELECT DISTINCT location, 1
            FROM practice_slots
            WHERE TRIM(location) != ''
            ON CONFLICT(name) DO NOTHING
            """
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_player_columns(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(players)").fetchall()
    }
    if "team" not in columns:
        conn.execute(
            "ALTER TABLE players ADD COLUMN team TEXT NOT NULL DEFAULT 'Challenger'"
        )
    if "gender" not in columns:
        conn.execute(
            "ALTER TABLE players ADD COLUMN gender TEXT NOT NULL DEFAULT 'Unspecified'"
        )
    if "phone_number" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN phone_number TEXT")
    if "practice_group" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN practice_group TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "UPDATE players SET team = ? WHERE team IS NULL OR TRIM(team) = ''",
        (DEFAULT_TEAM,),
    )
    conn.execute(
        "UPDATE players SET gender = ? WHERE gender IS NULL OR TRIM(gender) = ''",
        (DEFAULT_GENDER,),
    )
    conn.execute(
        "UPDATE players SET practice_group = '' WHERE practice_group IS NULL",
    )


def ensure_postgres_player_columns(conn: PostgresConnection) -> None:
    conn.executescript(
        """
        ALTER TABLE players ADD COLUMN IF NOT EXISTS team TEXT NOT NULL DEFAULT 'Challenger';
        ALTER TABLE players ADD COLUMN IF NOT EXISTS gender TEXT NOT NULL DEFAULT 'Unspecified';
        ALTER TABLE players ADD COLUMN IF NOT EXISTS phone_number TEXT;
        ALTER TABLE players ADD COLUMN IF NOT EXISTS practice_group TEXT NOT NULL DEFAULT '';
        UPDATE players SET team = 'Challenger' WHERE team IS NULL OR TRIM(team) = '';
        UPDATE players SET gender = 'Unspecified' WHERE gender IS NULL OR TRIM(gender) = '';
        UPDATE players SET practice_group = '' WHERE practice_group IS NULL;
        """
    )


def normalize_team(team: str) -> str:
    return team if team in TEAMS else DEFAULT_TEAM


def normalize_gender(gender: str) -> str:
    return gender if gender in GENDERS else DEFAULT_GENDER


def create_schedule_window(title: str, start_date: str, end_date: str) -> sqlite3.Row:
    token = secrets.token_urlsafe(16)
    with get_connection() as conn:
        if is_postgres():
            row = conn.execute(
                """
                INSERT INTO schedule_windows
                    (title, start_date, end_date, submission_open, public_token, created_at)
                VALUES (?, ?, ?, 1, ?, ?)
                RETURNING id
                """,
                (title, start_date, end_date, token, now_iso()),
            ).fetchone()
            return get_schedule_window(row["id"], conn=conn)
        else:
            cursor = conn.execute(
                """
                INSERT INTO schedule_windows
                    (title, start_date, end_date, submission_open, public_token, created_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (title, start_date, end_date, token, now_iso()),
            )
            return get_schedule_window(cursor.lastrowid, conn=conn)


def get_schedule_window(window_id: int, conn: sqlite3.Connection | None = None) -> sqlite3.Row | None:
    close_conn = conn is None
    conn = conn or get_connection()
    try:
        return conn.execute(
            "SELECT * FROM schedule_windows WHERE id = ?",
            (window_id,),
        ).fetchone()
    finally:
        if close_conn:
            conn.close()


def get_schedule_window_by_token(token: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM schedule_windows WHERE public_token = ?",
            (token.strip(),),
        ).fetchone()


def list_schedule_windows() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM schedule_windows
            ORDER BY start_date DESC, id DESC
            """
        ).fetchall()


def set_submission_open(window_id: int, is_open: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE schedule_windows SET submission_open = ? WHERE id = ?",
            (1 if is_open else 0, window_id),
        )


def add_practice_slot(
    schedule_window_id: int,
    date: str,
    start_time: str,
    end_time: str,
    location: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO practice_slots
                (schedule_window_id, date, start_time, end_time, location)
            VALUES (?, ?, ?, ?, ?)
            """,
            (schedule_window_id, date, start_time, end_time, location),
        )


def add_practice_slots_batch(
    schedule_window_id: int,
    slots: Iterable[tuple[str, str]],
) -> int:
    """Insert non-duplicate slots and return the number added."""
    slots_to_add = list(slots)
    if not slots_to_add:
        return 0

    with get_connection() as conn:
        existing_rows = conn.execute(
            """
            SELECT date, start_time
            FROM practice_slots
            WHERE schedule_window_id = ?
            """,
            (schedule_window_id,),
        ).fetchall()
        existing = {
            (row["date"], row["start_time"])
            for row in existing_rows
        }
        new_slots = []
        seen = set(existing)
        for slot in slots_to_add:
            if slot in seen:
                continue
            new_slots.append(slot)
            seen.add(slot)
        conn.executemany(
            """
            INSERT INTO practice_slots
                (schedule_window_id, date, start_time, end_time, location)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (schedule_window_id, slot_date, start_time, end_time, "")
                for slot_date, start_time in new_slots
                for end_time in [_two_hours_after(start_time)]
            ],
        )
        return len(new_slots)


def _two_hours_after(start_time: str) -> str:
    start_hour, start_minute = [int(part) for part in start_time.split(":")]
    end_hour = start_hour + 2
    return f"{end_hour:02d}:{start_minute:02d}"


def list_practice_slots(schedule_window_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM practice_slots
            WHERE schedule_window_id = ?
            ORDER BY date, start_time, id
            """,
            (schedule_window_id,),
        ).fetchall()


def list_active_players() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM players
            WHERE active = 1
            ORDER BY name
            """
        ).fetchall()


def add_player(name: str, team: str = DEFAULT_TEAM, gender: str = DEFAULT_GENDER) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False

    with get_connection() as conn:
        if is_postgres():
            cursor = conn.execute(
                """
                INSERT INTO players (name, active, team, gender)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(name) DO NOTHING
                """,
                (clean_name, normalize_team(team), normalize_gender(gender)),
            )
        else:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO players (name, active, team, gender)
                VALUES (?, 1, ?, ?)
                """,
                (clean_name, normalize_team(team), normalize_gender(gender)),
            )
        return cursor.rowcount > 0


def update_player_details(player_id: int, name: str, team: str, gender: str) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "UPDATE players SET name = ?, team = ?, gender = ? WHERE id = ?",
                (clean_name, normalize_team(team), normalize_gender(gender), player_id),
            )
        except Exception:
            conn.rollback()
            return False
        return cursor.rowcount > 0


def get_player(player_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()


def list_locations() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM locations
            WHERE active = 1
            ORDER BY name
            """
        ).fetchall()


def add_location(name: str) -> bool:
    clean_name = name.strip()
    if not clean_name:
        return False

    with get_connection() as conn:
        if is_postgres():
            cursor = conn.execute(
                """
                INSERT INTO locations (name, active)
                VALUES (?, 1)
                ON CONFLICT(name) DO NOTHING
                """,
                (clean_name,),
            )
        else:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO locations (name, active)
                VALUES (?, 1)
                """,
                (clean_name,),
            )
        return cursor.rowcount > 0


def update_practice_slot_location(practice_slot_id: int, location: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE practice_slots SET location = ? WHERE id = ?",
            (location.strip(), practice_slot_id),
        )


def get_player_available_slot_ids(player_id: int, schedule_window_id: int) -> set[int]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT a.practice_slot_id
            FROM availability a
            JOIN practice_slots ps ON ps.id = a.practice_slot_id
            WHERE a.player_id = ?
              AND ps.schedule_window_id = ?
              AND a.available = 1
            """,
            (player_id, schedule_window_id),
        ).fetchall()
    return {row["practice_slot_id"] for row in rows}


def upsert_availability(player_id: int, schedule_window_id: int, available_slot_ids: Iterable[int]) -> None:
    selected_ids = set(available_slot_ids)
    slots = list_practice_slots(schedule_window_id)
    updated_at = now_iso()
    with get_connection() as conn:
        for slot in slots:
            conn.execute(
                """
                INSERT INTO availability
                    (player_id, practice_slot_id, available, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(player_id, practice_slot_id) DO UPDATE SET
                    available = excluded.available,
                    updated_at = excluded.updated_at
                """,
                (player_id, slot["id"], 1 if slot["id"] in selected_ids else 0, updated_at),
            )


def list_submitted_player_ids(schedule_window_id: int) -> set[int]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT a.player_id
            FROM availability a
            JOIN practice_slots ps ON ps.id = a.practice_slot_id
            WHERE ps.schedule_window_id = ?
            """,
            (schedule_window_id,),
        ).fetchall()
    return {row["player_id"] for row in rows}


def get_slot_availability_counts(schedule_window_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                ps.id,
                ps.date,
                ps.start_time,
                ps.end_time,
                ps.location,
                COUNT(CASE WHEN a.available = 1 THEN 1 END) AS available_count
            FROM practice_slots ps
            LEFT JOIN availability a ON a.practice_slot_id = ps.id
            WHERE ps.schedule_window_id = ?
            GROUP BY ps.id
            ORDER BY ps.date, ps.start_time, ps.id
            """,
            (schedule_window_id,),
        ).fetchall()


def list_available_players_for_slot(
    practice_slot_id: int,
    teams: Iterable[str] | None = None,
) -> list[sqlite3.Row]:
    selected_teams = [normalize_team(team) for team in teams] if teams is not None else None
    if selected_teams == []:
        return []
    with get_connection() as conn:
        params: list[object] = [practice_slot_id]
        team_clause = ""
        if selected_teams is not None:
            placeholders = ", ".join("?" for _ in selected_teams)
            team_clause = f" AND p.team IN ({placeholders})"
            params.extend(selected_teams)
        return conn.execute(
            f"""
            SELECT p.*
            FROM availability a
            JOIN players p ON p.id = a.player_id
            WHERE a.practice_slot_id = ?
              AND a.available = 1
              AND p.active = 1
              {team_clause}
            ORDER BY p.name
            """,
            params,
        ).fetchall()


def list_available_players_for_window(
    schedule_window_id: int,
    teams: Iterable[str] | None = None,
) -> list[sqlite3.Row]:
    selected_teams = [normalize_team(team) for team in teams] if teams is not None else None
    if selected_teams == []:
        return []
    with get_connection() as conn:
        params: list[object] = [schedule_window_id]
        team_clause = ""
        if selected_teams is not None:
            placeholders = ", ".join("?" for _ in selected_teams)
            team_clause = f" AND p.team IN ({placeholders})"
            params.extend(selected_teams)
        return conn.execute(
            f"""
            SELECT
                a.practice_slot_id,
                p.id,
                p.name,
                p.active,
                p.team,
                p.gender,
                p.practice_group
            FROM availability a
            JOIN practice_slots ps ON ps.id = a.practice_slot_id
            JOIN players p ON p.id = a.player_id
            WHERE ps.schedule_window_id = ?
              AND a.available = 1
              AND p.active = 1
              {team_clause}
            ORDER BY a.practice_slot_id, p.name
            """,
            params,
        ).fetchall()


def list_assignments_for_slot(practice_slot_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                a.*,
                p.name AS player_name,
                p.team AS player_team,
                p.gender AS player_gender,
                p.practice_group AS player_practice_group
            FROM assignments a
            JOIN players p ON p.id = a.player_id
            WHERE a.practice_slot_id = ?
            ORDER BY p.name
            """,
            (practice_slot_id,),
        ).fetchall()


def list_assignments_for_window(schedule_window_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                a.*,
                p.name AS player_name,
                p.team AS player_team,
                p.gender AS player_gender,
                p.practice_group AS player_practice_group
            FROM assignments a
            JOIN practice_slots ps ON ps.id = a.practice_slot_id
            JOIN players p ON p.id = a.player_id
            WHERE ps.schedule_window_id = ?
            ORDER BY a.practice_slot_id, p.name
            """,
            (schedule_window_id,),
        ).fetchall()


def save_assignments_for_slot(
    practice_slot_id: int,
    player_ids: Iterable[int],
    practice_lead_player_id: int | None,
) -> None:
    assigned_ids = list(dict.fromkeys(player_ids))
    if practice_lead_player_id not in assigned_ids:
        practice_lead_player_id = None

    with get_connection() as conn:
        conn.execute("DELETE FROM assignments WHERE practice_slot_id = ?", (practice_slot_id,))
        conn.executemany(
            """
            INSERT INTO assignments
                (practice_slot_id, player_id, is_practice_lead)
            VALUES (?, ?, ?)
            """,
            [
                (practice_slot_id, player_id, 1 if player_id == practice_lead_player_id else 0)
                for player_id in assigned_ids
            ],
        )


def save_slot_schedule(
    practice_slot_id: int,
    player_ids: Iterable[int],
    practice_lead_player_id: int | None,
    location: str,
) -> None:
    assigned_ids = list(dict.fromkeys(player_ids))
    if practice_lead_player_id not in assigned_ids:
        practice_lead_player_id = None

    with get_connection() as conn:
        conn.execute(
            "UPDATE practice_slots SET location = ? WHERE id = ?",
            (location.strip(), practice_slot_id),
        )
        conn.execute("DELETE FROM assignments WHERE practice_slot_id = ?", (practice_slot_id,))
        conn.executemany(
            """
            INSERT INTO assignments
                (practice_slot_id, player_id, is_practice_lead)
            VALUES (?, ?, ?)
            """,
            [
                (practice_slot_id, player_id, 1 if player_id == practice_lead_player_id else 0)
                for player_id in assigned_ids
            ],
        )


def delete_slot_schedule(practice_slot_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE practice_slots SET location = '' WHERE id = ?", (practice_slot_id,))
        conn.execute("DELETE FROM assignments WHERE practice_slot_id = ?", (practice_slot_id,))


def delete_all_scheduled_practices() -> None:
    with get_connection() as conn:
        conn.execute("UPDATE practice_slots SET location = ''")
        conn.execute("DELETE FROM assignments")


def get_printable_schedule(schedule_window_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if is_postgres():
            assigned_players_expr = "STRING_AGG(p.name, ', ' ORDER BY p.name)"
            practice_lead_expr = "STRING_AGG(CASE WHEN a.is_practice_lead = 1 THEN p.name END, ', ' ORDER BY p.name)"
        else:
            assigned_players_expr = "GROUP_CONCAT(p.name, ', ')"
            practice_lead_expr = "GROUP_CONCAT(CASE WHEN a.is_practice_lead = 1 THEN p.name END)"
        return conn.execute(
            f"""
            SELECT
                ps.id AS practice_slot_id,
                ps.date,
                ps.start_time,
                ps.end_time,
                ps.location,
                {assigned_players_expr} AS assigned_players,
                {practice_lead_expr} AS practice_lead
            FROM practice_slots ps
            LEFT JOIN assignments a ON a.practice_slot_id = ps.id
            LEFT JOIN players p ON p.id = a.player_id
            WHERE ps.schedule_window_id = ?
              AND (
                  TRIM(ps.location) != ''
                  OR EXISTS (
                      SELECT 1
                      FROM assignments ax
                      WHERE ax.practice_slot_id = ps.id
                  )
              )
            GROUP BY ps.id
            ORDER BY ps.date, ps.start_time, ps.id
            """,
            (schedule_window_id,),
        ).fetchall()
