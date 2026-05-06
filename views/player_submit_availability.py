from datetime import date, timedelta

import streamlit as st

from db import (
    get_player_available_slot_ids,
    get_schedule_window_by_token,
    init_db,
    list_active_players,
    list_practice_slots,
    upsert_availability,
)


init_db()

st.title("Player: Submit Availability")

query_token = st.query_params.get("token", "")
token = query_token or st.text_input("Token")

if not token:
    st.info("Enter the code from the captains, or open the link from the text.")
    st.stop()

window = get_schedule_window_by_token(token)
if window is None:
    st.error("Invalid token.")
    st.stop()

st.subheader(window["title"])
st.caption(f"{window['start_date']} to {window['end_date']}")

slots = list_practice_slots(window["id"])
if not slots:
    st.info("No practice slots are available yet.")
    st.stop()

players = list_active_players()
if not players:
    st.error("No active players found.")
    st.stop()

player_names = [""] + [player["name"] for player in players]
player_name = st.selectbox("Your name", player_names, format_func=lambda name: "Select your name" if not name else name)
if not player_name:
    st.info("Select your name to submit availability.")
    st.stop()

player = next(p for p in players if p["name"] == player_name)

previous_available_ids = get_player_available_slot_ids(player["id"], window["id"])

if not window["submission_open"]:
    st.warning("Submissions are closed for this schedule window.")

st.write("Select every practice start time you are available for.")


def week_starts_between(start: date, end: date) -> list[date]:
    first_monday = start - timedelta(days=start.weekday())
    week_start = first_monday
    weeks = []
    while week_start <= end:
        weeks.append(week_start)
        week_start += timedelta(days=7)
    return weeks


def slot_key(slot_date: date, hour: int) -> str:
    return f"{window['id']}|{player['id']}|{slot_date.isoformat()}|{hour:02d}:00"


def format_hour(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    return f"{display_hour} {suffix}"


def format_slot_label(slot_date: date, hour: int) -> str:
    return f"{day_names[slot_date.weekday()]} {slot_date.strftime('%b')} {slot_date.day} {format_hour(hour)}"


selected_state_key = f"player_available_slots_{window['id']}_{player['id']}"
loaded_state_key = f"{selected_state_key}_loaded"
if not st.session_state.get(loaded_state_key):
    st.session_state[selected_state_key] = set(previous_available_ids)
    st.session_state[loaded_state_key] = True

window_start = date.fromisoformat(window["start_date"])
window_end = date.fromisoformat(window["end_date"])
day_names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
hours = (6, 8, 15, 16, 18, 19, 20, 21)
missing_hour_gap_pixels = 12
slots_by_time = {
    (slot["date"], slot["start_time"]): slot
    for slot in slots
}


def render_slot_button(container, slot_date: date, hour: int, key_prefix: str) -> None:
    start_time = f"{hour:02d}:00"
    slot = slots_by_time.get((slot_date.isoformat(), start_time))
    key = slot_key(slot_date, hour)
    in_window = window_start <= slot_date <= window_end
    is_available = bool(slot and slot["id"] in st.session_state[selected_state_key])
    disabled = (not in_window) or (slot is None) or (not window["submission_open"])
    button_kwargs = {
        "label": format_slot_label(slot_date, hour),
        "key": f"{key_prefix}_{key}",
        "type": "primary" if is_available else "secondary",
        "disabled": disabled,
        "width": "stretch",
    }
    if slot is not None and window["submission_open"]:
        button_kwargs["on_click"] = toggle_slot_selection
        button_kwargs["args"] = (slot["id"],)
    container.button(
        **button_kwargs,
    )


def toggle_slot_selection(slot_id: int) -> None:
    if slot_id in st.session_state[selected_state_key]:
        st.session_state[selected_state_key].remove(slot_id)
    else:
        st.session_state[selected_state_key].add(slot_id)


def clear_selected_slots() -> None:
    st.session_state[selected_state_key].clear()


@st.fragment
def render_player_availability_grid() -> None:
    layout = st.radio("Layout", ["Calendar", "Day-by-day"], index=1, horizontal=True)

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
                    render_slot_button(row_cols[day_index + 1], slot_date, hour, "player_grid")
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
                    render_slot_button(st, slot_date, hour, "player_day")

    selected_slot_ids = sorted(st.session_state[selected_state_key])
    st.write(f"{len(selected_slot_ids)} slot(s) selected.")

    st.button(
        "Clear Selected Slots",
        disabled=(not selected_slot_ids) or (not window["submission_open"]),
        on_click=clear_selected_slots,
    )

    if st.button("Submit Availability", type="primary", disabled=not window["submission_open"]):
        upsert_availability(player["id"], window["id"], selected_slot_ids)
        st.success("Availability saved.")


render_player_availability_grid()
