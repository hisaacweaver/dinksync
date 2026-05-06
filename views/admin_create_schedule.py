from datetime import date, timedelta
from html import escape

import streamlit as st

from db import (
    TEAMS,
    add_location,
    delete_slot_schedule,
    get_slot_availability_counts,
    init_db,
    list_assignments_for_slot,
    list_available_players_for_slot,
    list_locations,
    list_schedule_windows,
    save_slot_schedule,
)


init_db()

st.title("Admin: Create Schedule")

windows = list_schedule_windows()
if not windows:
    st.info("Create a schedule window first.")
    st.stop()

window_options = {f"{w['title']} ({w['start_date']} to {w['end_date']})": w["id"] for w in windows}
selected_label = st.selectbox("Schedule window", list(window_options.keys()))
window_id = window_options[selected_label]
window = next(w for w in windows if w["id"] == window_id)

slots = get_slot_availability_counts(window_id)
if not slots:
    st.info("No slots have been added yet.")
    st.stop()

locations = list_locations()
location_names = [location["name"] for location in locations]
location_options = location_names + ["Custom location"]

window_start = date.fromisoformat(window["start_date"])
window_end = date.fromisoformat(window["end_date"])
day_names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
hours = (6, 8, 15, 16, 18, 19, 20, 21)
missing_hour_gap_pixels = 12

slots_by_time = {
    (slot["date"], slot["start_time"]): slot
    for slot in slots
}

slots_by_id = {slot["id"]: slot for slot in slots}

assignments_by_slot = {
    slot["id"]: list_assignments_for_slot(slot["id"])
    for slot in slots
}

assignment_ids_by_slot = {
    slot_id: [assignment["player_id"] for assignment in assignments]
    for slot_id, assignments in assignments_by_slot.items()
}

scheduled_slot_ids = {
    slot["id"]
    for slot in slots
    if slot["location"].strip() or assignment_ids_by_slot[slot["id"]]
}

players_display = st.radio(
    "Players",
    ["Hide players", "Show players", "Show players only"],
    index=2,
    horizontal=True,
)

selected_teams = st.multiselect(
    "Teams",
    TEAMS,
    default=["Premier", "Challenger"],
)

available_players_by_slot = {}
for slot in slots:
    slot_id = slot["id"]
    filtered_players = list_available_players_for_slot(slot_id, selected_teams)
    players_by_id = {player["id"]: player for player in filtered_players}
    for assignment in assignments_by_slot[slot_id]:
        if assignment["player_id"] not in players_by_id:
            players_by_id[assignment["player_id"]] = {
                "id": assignment["player_id"],
                "name": assignment["player_name"],
                "team": assignment["player_team"],
                "gender": assignment["player_gender"],
            }
    available_players_by_slot[slot_id] = list(players_by_id.values())


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


def format_time_value(time_value: str) -> str:
    return format_hour(int(time_value.split(":")[0]))


def format_slot_label(slot_date: date, hour: int, available_count: int) -> str:
    day_name = day_names[slot_date.weekday()]
    return f"{day_name} {slot_date.strftime('%b')} {slot_date.day} {format_hour(hour)} ({available_count})"


def button_time_slug(slot_date: str, start_time: str) -> str:
    return f"{slot_date}_{start_time.replace(':', '')}"


def slot_button_key(slot) -> str:
    return f"schedule_slot_{button_time_slug(slot['date'], slot['start_time'])}_{slot['id']}"


def slot_button_style(slot, color: str) -> str:
    return f"""
    <style>
    .st-key-{slot_button_key(slot)} button {{
        background-color: {color};
        border-color: {color};
        color: white;
        white-space: pre-line;
    }}
    .st-key-{slot_button_key(slot)} button:hover {{
        background-color: {color};
        border-color: {color};
        color: white;
        filter: brightness(0.95);
    }}
    </style>
    """


def sort_players_for_slot(players: list[dict], assigned_player_ids: set[int]) -> list[dict]:
    return sorted(
        players,
        key=lambda player: (
            player["id"] not in assigned_player_ids,
            player["name"].lower(),
        ),
    )


st.markdown(
    """
    <style>
    [class*="st-key-schedule_slot_"] button {
        white-space: pre-line;
    }

    .player-only-cell {
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 0.35rem;
        margin-bottom: 0.25rem;
        background: #ffffff;
        color: #111827;
    }

    .player-only-row {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        min-height: 1.4rem;
        font-size: 0.9rem;
        line-height: 1.2;
        padding: 0.15rem 0.25rem;
        border-radius: 4px;
    }

    .player-only-row-assigned {
        background: #dbeafe;
        font-weight: 700;
    }

    .gender-bar {
        width: 4px;
        min-height: 1.1rem;
        border-radius: 999px;
        flex: 0 0 4px;
    }

    .gender-male {
        background: #2563eb;
    }

    .gender-female {
        background: #ec4899;
    }

    .gender-unspecified {
        background: #9ca3af;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.dialog("Schedule Practice")
def schedule_slot_dialog(slot_id: int) -> None:
    slot = slots_by_id[slot_id]
    is_scheduled = slot_id in scheduled_slot_ids
    slot_date = date.fromisoformat(slot["date"])
    start_hour = int(slot["start_time"].split(":")[0])
    filtered_available_players = available_players_by_slot[slot_id]

    st.subheader(format_slot_label(slot_date, start_hour, len(filtered_available_players)))

    available_options = {player["name"]: player["id"] for player in filtered_available_players}
    existing_assignments = list_assignments_for_slot(slot_id)
    existing_ids = [assignment["player_id"] for assignment in existing_assignments]

    existing_names = [
        name
        for name, player_id in available_options.items()
        if player_id in existing_ids
    ]

    existing_lead_id = next(
        (
            assignment["player_id"]
            for assignment in existing_assignments
            if assignment["is_practice_lead"]
        ),
        None,
    )

    existing_location = slot["location"] or ""

    if location_options:
        if existing_location in location_options:
            location_index = location_options.index(existing_location)
            custom_default = ""
        elif existing_location:
            location_index = location_options.index("Custom location")
            custom_default = existing_location
        else:
            location_index = 0
            custom_default = ""

        selected_location = st.selectbox(
            "Location",
            location_options,
            index=location_index,
            key=f"modal_location_{slot_id}",
        )
    else:
        selected_location = "Custom location"
        custom_default = existing_location

    custom_location = ""
    if selected_location == "Custom location":
        custom_location = st.text_input(
            "Custom location",
            value=custom_default,
            key=f"modal_custom_location_{slot_id}",
        )

    if not available_options:
        st.write("No available players for this slot.")

    assigned_names = st.multiselect(
        "Players",
        list(available_options.keys()),
        default=existing_names,
        key=f"modal_players_{slot_id}",
    )

    assigned_ids = [available_options[name] for name in assigned_names]

    lead_options = ["No lead"] + assigned_names

    existing_lead_name = next(
        (
            name
            for name, player_id in available_options.items()
            if player_id == existing_lead_id
        ),
        "No lead",
    )

    lead_index = lead_options.index(existing_lead_name) if existing_lead_name in lead_options else 0
    lead_state_key = f"modal_lead_{slot_id}"

    if st.session_state.get(lead_state_key) not in (None, *lead_options):
        st.session_state[lead_state_key] = "No lead"

    lead_name = st.selectbox(
        "Lead",
        lead_options,
        index=lead_index,
        key=lead_state_key,
    )

    if st.button("Save Schedule", type="primary"):
        location = custom_location.strip() if selected_location == "Custom location" else selected_location

        if not location:
            st.error("Choose a location or enter a custom location.")
            return

        if selected_location == "Custom location":
            add_location(location)

        lead_id = available_options[lead_name] if lead_name != "No lead" else None

        save_slot_schedule(slot_id, assigned_ids, lead_id, location)

        st.success("Schedule saved.")
        st.rerun()

    if is_scheduled:
        st.divider()

        if st.button("Delete Scheduled Practice", type="secondary"):
            delete_slot_schedule(slot_id)
            st.success("Scheduled practice deleted.")
            st.rerun()


def render_slot_button(container, slot_date: date, hour: int) -> None:
    start_time = f"{hour:02d}:00"
    slot = slots_by_time.get((slot_date.isoformat(), start_time))
    in_window = window_start <= slot_date <= window_end

    if not slot:
        if players_display == "Show players only":
            label = ""
        else:
            label = f"{day_names[slot_date.weekday()]} {slot_date.strftime('%b')} {slot_date.day} {format_hour(hour)} (0)"

        container.button(
            label,
            key=f"schedule_slot_empty_{button_time_slug(slot_date.isoformat(), start_time)}",
            disabled=True,
            width='stretch',
        )
        return

    slot_id = slot["id"]
    assigned_player_ids = set(assignment_ids_by_slot[slot_id])

    available_players = available_players_by_slot[slot_id]
    sorted_available_players = sort_players_for_slot(available_players, assigned_player_ids)

    available_player_names = [player["name"] for player in sorted_available_players]
    available_count = len(available_player_names)

    is_scheduled = slot_id in scheduled_slot_ids
    has_many_available = available_count >= 4

    if is_scheduled:
        st.markdown(slot_button_style(slot, "#2563eb"), unsafe_allow_html=True)
    elif has_many_available:
        st.markdown(slot_button_style(slot, "#16a34a"), unsafe_allow_html=True)

    if players_display == "Show players only":
        if sorted_available_players:
            rows = []

            for player in sorted_available_players:
                gender_class = {
                    "Male": "gender-male",
                    "Female": "gender-female",
                }.get(player["gender"], "gender-unspecified")

                assigned_class = (
                    "player-only-row-assigned"
                    if player["id"] in assigned_player_ids
                    else ""
                )

                rows.append(
                    f'<div class="player-only-row {assigned_class}">'
                    f'<span class="gender-bar {gender_class}"></span>'
                    f'<span>{escape(player["name"])}</span>'
                    f'</div>'
                )

            container.markdown(
                f"<div class='player-only-cell'>{''.join(rows)}</div>",
                unsafe_allow_html=True,
            )

        label = "Schedule" if available_players else ""
    else:
        label = format_slot_label(slot_date, hour, available_count)

    clicked = container.button(
        label,
        key=slot_button_key(slot),
        type="secondary",
        disabled=(not in_window) or (players_display == "Show players only" and not available_player_names),
        width='stretch',
    )

    if clicked:
        schedule_slot_dialog(slot_id)

    if players_display == "Show players":
        names = ", ".join(available_player_names)
        container.caption(names if names else "No available players")


st.caption("Green slots have 4 or more available players. Blue slots have already been scheduled.")

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
            render_slot_button(row_cols[day_index + 1], slot_date, hour)

        previous_hour = hour


st.subheader("Scheduled Practices")

scheduled_rows = []

for slot in slots:
    assignments = list_assignments_for_slot(slot["id"])

    if not assignments and not slot["location"].strip():
        continue

    assigned_players = ", ".join(assignment["player_name"] for assignment in assignments) or "No players assigned"
    lead = next(
        (assignment["player_name"] for assignment in assignments if assignment["is_practice_lead"]),
        "No lead",
    )

    slot_date = date.fromisoformat(slot["date"])

    scheduled_rows.append(
        {
            "Time": f"{day_names[slot_date.weekday()]} {slot_date.strftime('%b')} {slot_date.day} {format_time_value(slot['start_time'])}",
            "Location": slot["location"] or "Location not set",
            "Players": assigned_players,
            "Lead": lead,
        }
    )

if scheduled_rows:
    st.dataframe(scheduled_rows, hide_index=True, width='stretch')
else:
    st.info("No practices have been scheduled yet.")
