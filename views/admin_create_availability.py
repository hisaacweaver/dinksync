from datetime import date, timedelta

import streamlit as st

from db import (
    add_practice_slots_batch,
    create_schedule_window,
    init_db,
    list_practice_slots,
    list_schedule_windows,
)


init_db()

st.title("Admin: Create Availability")

with st.form("create_window"):
    st.subheader("Create Schedule Window")
    title = st.text_input("Title", placeholder="May practice week")
    start_date = st.date_input("Start date", value=date.today())
    end_date = st.date_input("End date", value=date.today())
    submitted = st.form_submit_button("Create Schedule Window")

if submitted:
    if not title.strip():
        st.error("Enter a title.")
    elif end_date < start_date:
        st.error("End date must be on or after start date.")
    else:
        window = create_schedule_window(title.strip(), start_date.isoformat(), end_date.isoformat())
        st.session_state["selected_window_id"] = window["id"]
        st.success("Schedule window created.")

windows = list_schedule_windows()
if not windows:
    st.info("Create a schedule window before adding slots.")
    st.stop()

window_options = {f"{w['title']} ({w['start_date']} to {w['end_date']})": w["id"] for w in windows}
default_id = st.session_state.get("selected_window_id", windows[0]["id"])
default_index = list(window_options.values()).index(default_id) if default_id in window_options.values() else 0
selected_label = st.selectbox("Selected schedule window", list(window_options.keys()), index=default_index)
window_id = window_options[selected_label]
window = next(w for w in windows if w["id"] == window_id)
st.session_state["selected_window_id"] = window_id

base_url = "https://byupbscheduling.streamlit.app/Player_Submit_Availability"
player_link = f"{base_url}?token={window['public_token']}"
st.write("Share this token or link with players:")
st.code(window["public_token"])
st.code(player_link)

st.subheader("Batch Add Practice Slots")
st.caption("Select practice start times. Weeks run Monday through Saturday; Sundays are never shown.")


def week_starts_between(start: date, end: date) -> list[date]:
    first_monday = start - timedelta(days=start.weekday())
    week_start = first_monday
    weeks = []
    while week_start <= end:
        weeks.append(week_start)
        week_start += timedelta(days=7)
    return weeks


def slot_key(slot_date: date, hour: int) -> str:
    return f"{window_id}|{slot_date.isoformat()}|{hour:02d}:00"


def format_hour(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    return f"{display_hour} {suffix}"


def format_slot_label(slot_date: date, hour: int) -> str:
    return f"{day_names[slot_date.weekday()]} {slot_date.strftime('%b')} {slot_date.day} {format_hour(hour)}"


selected_state_key = f"selected_slots_{window_id}"
if selected_state_key not in st.session_state:
    st.session_state[selected_state_key] = set()

window_start = date.fromisoformat(window["start_date"])
window_end = date.fromisoformat(window["end_date"])
day_names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
hours = (6, 8, 15, 16, 18, 19, 20, 21)
missing_hour_gap_pixels = 12
existing_slots = {
    (slot["date"], slot["start_time"])
    for slot in list_practice_slots(window_id)
}


def selectable_slot_keys() -> set[str]:
    keys = set()
    for week_start in week_starts_between(window_start, window_end):
        for day_index in range(6):
            slot_date = week_start + timedelta(days=day_index)
            if not (window_start <= slot_date <= window_end):
                continue
            for hour in hours:
                start_time = f"{hour:02d}:00"
                if (slot_date.isoformat(), start_time) not in existing_slots:
                    keys.add(slot_key(slot_date, hour))
    return keys


def render_slot_button(container, slot_date: date, hour: int, key_prefix: str) -> None:
    key = slot_key(slot_date, hour)
    start_time = f"{hour:02d}:00"
    in_window = window_start <= slot_date <= window_end
    already_added = (slot_date.isoformat(), start_time) in existing_slots
    is_selected = key in st.session_state[selected_state_key]
    clicked = container.button(
        format_slot_label(slot_date, hour),
        key=f"{key_prefix}_{key}",
        type="primary" if is_selected or already_added else "secondary",
        disabled=(not in_window) or already_added,
        width='stretch',
    )
    if clicked:
        if is_selected:
            st.session_state[selected_state_key].remove(key)
        else:
            st.session_state[selected_state_key].add(key)
        st.rerun()


layout = st.radio("Layout", ["Calendar", "Day-by-day"], horizontal=True)

action_col1, action_col2 = st.columns(2)
if action_col1.button("Select All Available Slots"):
    st.session_state[selected_state_key].update(selectable_slot_keys())
    st.rerun()
if action_col2.button("Clear Selected Slots", disabled=not st.session_state[selected_state_key]):
    st.session_state[selected_state_key].clear()
    st.rerun()

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
                render_slot_button(row_cols[day_index + 1], slot_date, hour, "grid")
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
                render_slot_button(st, slot_date, hour, "day")

selected_slots = sorted(st.session_state[selected_state_key])
st.write(f"{len(selected_slots)} new slot(s) selected.")

if st.button("Add Selected Time Slots", type="primary", disabled=not selected_slots):
    batch = []
    for selected_key in selected_slots:
        _, selected_date, selected_start = selected_key.split("|")
        batch.append((selected_date, selected_start))
    added_count = add_practice_slots_batch(window_id, batch)
    st.session_state[selected_state_key].clear()
    st.success(f"Added {added_count} slot(s).")
    st.rerun()

st.subheader("Slots")
slots = list_practice_slots(window_id)
if not slots:
    st.info("No slots have been added yet.")
else:
    st.dataframe(
        [
            {
                "Date": slot["date"],
                "Start time": slot["start_time"],
            }
            for slot in slots
        ],
        hide_index=True,
        width='stretch',
    )
