from datetime import date, timedelta
from html import escape

import streamlit as st

from db import (
    get_slot_availability_counts,
    init_db,
    list_active_players,
    list_available_players_for_window,
    list_schedule_windows,
    list_submitted_player_ids,
    set_submission_open,
)


init_db()

st.title("Admin: View Responses")

windows = list_schedule_windows()
if not windows:
    st.info("Create a schedule window first.")
    st.stop()

window_options = {f"{w['title']} ({w['start_date']} to {w['end_date']})": w["id"] for w in windows}
selected_label = st.selectbox("Schedule window", list(window_options.keys()))
window_id = window_options[selected_label]
window = next(w for w in windows if w["id"] == window_id)


def format_date_label(date_value: str) -> str:
    parsed = date.fromisoformat(date_value)
    return f"{parsed.strftime('%a')} {parsed.strftime('%b')} {parsed.day}"


col1, col2, col3 = st.columns(3)
summary_style = """
<div style="border: 1px solid #e5e7eb; border-radius: 6px; padding: 0.6rem; min-height: 76px;">
  <div style="font-size: 0.72rem; color: #6b7280; text-transform: uppercase;">{label}</div>
  <div style="font-size: 0.95rem; font-weight: 600; line-height: 1.25;">{value}</div>
</div>
"""
col1.markdown(summary_style.format(label="Title", value=escape(window["title"])), unsafe_allow_html=True)
col2.markdown(
    summary_style.format(
        label="Date range",
        value=f"{format_date_label(window['start_date'])} to {format_date_label(window['end_date'])}",
    ),
    unsafe_allow_html=True,
)
col3.markdown(
    summary_style.format(label="Submissions", value="Open" if window["submission_open"] else "Closed"),
    unsafe_allow_html=True,
)

st.write("Public token")
st.code(window["public_token"])

button_col1, button_col2 = st.columns([1, 1])
if button_col1.button("Close Submissions", disabled=not window["submission_open"]):
    set_submission_open(window_id, False)
    st.rerun()
if button_col2.button("Reopen Submissions", disabled=bool(window["submission_open"])):
    set_submission_open(window_id, True)
    st.rerun()

players = list_active_players()
submitted_ids = list_submitted_player_ids(window_id)
submitted_players = [p["name"] for p in players if p["id"] in submitted_ids]
not_submitted_players = [p["name"] for p in players if p["id"] not in submitted_ids]

left, right = st.columns(2)
left.subheader("Submitted")
left.write(", ".join(submitted_players) if submitted_players else "No submissions yet.")
right.subheader("Not Submitted")
right.write(", ".join(not_submitted_players) if not_submitted_players else "Everyone has submitted.")

st.subheader("Slot Availability")
slot_counts = get_slot_availability_counts(window_id)
if not slot_counts:
    st.info("No slots have been added yet.")
    st.stop()

available_players_by_slot = {slot["id"]: [] for slot in slot_counts}
for player in list_available_players_for_window(window_id):
    available_players_by_slot.setdefault(player["practice_slot_id"], []).append(player)


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
    return f"{display_hour} {suffix}"


def format_slot_label(slot_date: date, hour: int, available_count: int) -> str:
    day_name = day_names[slot_date.weekday()]
    return f"{day_name} {slot_date.strftime('%b')} {slot_date.day} {format_hour(hour)} ({available_count})"


window_start = date.fromisoformat(window["start_date"])
window_end = date.fromisoformat(window["end_date"])
day_names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
hours = (6, 8, 15, 16, 18, 19, 20, 21)
missing_hour_gap_pixels = 12
slots_by_time = {
    (slot["date"], slot["start_time"]): slot
    for slot in slot_counts
}
selected_slot_state_key = f"responses_selected_slot_{window_id}"


def select_slot(slot_id: int) -> None:
    st.session_state[selected_slot_state_key] = slot_id


def render_slot_button(container, slot_date: date, hour: int, key_prefix: str, show_players: bool) -> None:
    start_time = f"{hour:02d}:00"
    slot = slots_by_time.get((slot_date.isoformat(), start_time))
    in_window = window_start <= slot_date <= window_end
    if slot:
        label = format_slot_label(slot_date, hour, slot["available_count"])
        selected = st.session_state.get(selected_slot_state_key) == slot["id"]
    else:
        label = f"{day_names[slot_date.weekday()]} {slot_date.strftime('%b')} {slot_date.day} {format_hour(hour)} (0)"
        selected = False

    button_kwargs = {
        "label": label,
        "key": f"{key_prefix}_{window_id}_{slot_date.isoformat()}_{hour}",
        "type": "primary" if selected else "secondary",
        "disabled": (not in_window) or (slot is None),
        "width": "stretch",
    }
    if slot:
        button_kwargs["on_click"] = select_slot
        button_kwargs["args"] = (slot["id"],)

    container.button(
        **button_kwargs,
    )
    if show_players and slot:
        names = ", ".join(player["name"] for player in available_players_by_slot.get(slot["id"], []))
        if names:
            container.caption(names)


@st.fragment
def render_response_grid() -> None:
    show_players = st.radio("Players", ["Hide players", "Show players"], horizontal=True) == "Show players"
    layout = st.radio("Layout", ["Calendar", "Day-by-day"], horizontal=True)

    if layout == "Calendar":
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
                    render_slot_button(row_cols[day_index + 1], slot_date, hour, "responses_grid", show_players)
                previous_hour = hour
    else:
        for week_start in week_starts_between(window_start, window_end):
            week_end = week_start + timedelta(days=5)
            st.markdown(f"**Week of {week_start.isoformat()} to {week_end.isoformat()}**")
            for day_index, day_name in enumerate(day_names):
                slot_date = week_start + timedelta(days=day_index)
                if not (window_start <= slot_date <= window_end):
                    continue
                st.markdown(f"**{day_name} {slot_date.strftime('%b')} {slot_date.day}**")
                for hour in hours:
                    render_slot_button(st, slot_date, hour, "responses_day", show_players)

    selected_slot_id = st.session_state.get(selected_slot_state_key)
    if selected_slot_id:
        selected_slot = next((slot for slot in slot_counts if slot["id"] == selected_slot_id), None)
        if selected_slot:
            st.subheader(f"Available players for {selected_slot['date']} {selected_slot['start_time']}")
            names = ", ".join(player["name"] for player in available_players_by_slot.get(selected_slot_id, []))
            if names:
                st.write(names)
    else:
        st.info("Select a slot to view available players.")


render_response_grid()
