from datetime import date, timedelta
from html import escape

import streamlit as st

from db import get_printable_schedule, init_db, list_assignments_for_window, list_schedule_windows


init_db()

st.title("View Schedule")

windows = list_schedule_windows()
if not windows:
    st.info("Create a schedule window first.")
    st.stop()

window_options = {f"{w['title']} ({w['start_date']} to {w['end_date']})": w["id"] for w in windows}
selected_label = st.selectbox("Schedule window", list(window_options.keys()))
window_id = window_options[selected_label]
window = next(w for w in windows if w["id"] == window_id)

rows = get_printable_schedule(window_id)
if not rows:
    st.info("No practices have been scheduled yet.")
    st.stop()

window_start = date.fromisoformat(window["start_date"])
window_end = date.fromisoformat(window["end_date"])
day_names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
hours = (6, 8, 10, 12, 14, 16, 18, 20)
missing_hour_gap_pixels = 8
rows_by_time = {
    (row["date"], row["start_time"]): row
    for row in rows
}
assignments_by_slot = {row["practice_slot_id"]: [] for row in rows}
for assignment in list_assignments_for_window(window_id):
    if assignment["practice_slot_id"] in assignments_by_slot:
        assignments_by_slot[assignment["practice_slot_id"]].append(assignment)


def week_starts_between(start: date, end: date) -> list[date]:
    first_monday = start - timedelta(days=start.weekday())
    week_start = first_monday
    weeks = []
    while week_start <= end:
        weeks.append(week_start)
        week_start += timedelta(days=7)
    return weeks


def format_hour(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    return f"{display_hour}{suffix}"


def render_schedule_cell(container, row) -> None:
    if not row:
        container.write("")
        return

    assignments = assignments_by_slot.get(row["practice_slot_id"], [])
    player_lines = []
    for assignment in assignments:
        player_name = escape(assignment["player_name"])
        if assignment["is_practice_lead"]:
            player_lines.append(f"<div class='lead-player'>{player_name}</div>")
        else:
            player_lines.append(f"<div>{player_name}</div>")

    if not player_lines:
        player_lines.append("<div>Unassigned</div>")

    location = escape(row["location"] or "Location not set")
    container.markdown(
        f"""
        <div class="schedule-cell">
            {''.join(player_lines)}
            <div class="schedule-location">{location}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.header(window["title"])
st.caption(f"{window['start_date']} to {window['end_date']}")

st.markdown(
    """
    <style>
    .schedule-cell {
        min-height: 72px;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 0.5rem;
        background: #ffffff;
        color: #111827;
        line-height: 1.35;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
    }
    .lead-player {
        display: block;
        font-weight: 700;
        background: #dbeafe;
        color: #1d4ed8;
        border-radius: 4px;
        padding: 0.05rem 0.25rem;
        margin-bottom: 0.1rem;
    }
    .schedule-location {
        margin-top: 0.35rem;
        color: #374151;
        font-size: 0.85rem;
        border-top: 1px solid #e5e7eb;
        padding-top: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.fragment
def render_schedule_calendar() -> None:
    for week_start in week_starts_between(window_start, window_end):
        week_end = week_start + timedelta(days=5)
        st.markdown(f"**Week of {week_start.isoformat()} to {week_end.isoformat()}**")
        header_cols = st.columns([1.1, 1, 1, 1, 1, 1, 1])
        header_cols[0].write("")
        for index, day_name in enumerate(day_names):
            day_date = week_start + timedelta(days=index)
            header_cols[index + 1].markdown(f"**{day_name}**  \n{day_date.strftime('%b')} {day_date.day}")

        previous_hour = None
        for hour in hours:
            if previous_hour is not None:
                missing_hours = hour - previous_hour - 1
                if missing_hours > 0:
                    gap = missing_hour_gap_pixels if missing_hours == 1 else missing_hour_gap_pixels * 2
                    st.markdown(f"<div style='height: {gap}px;'></div>", unsafe_allow_html=True)
            row_cols = st.columns([1.1, 1, 1, 1, 1, 1, 1])
            row_cols[0].markdown(f"**{format_hour(hour)}**")
            for day_index in range(6):
                slot_date = week_start + timedelta(days=day_index)
                start_time = f"{hour:02d}:00"
                row = rows_by_time.get((slot_date.isoformat(), start_time))
                render_schedule_cell(row_cols[day_index + 1], row)
            previous_hour = hour


render_schedule_calendar()
