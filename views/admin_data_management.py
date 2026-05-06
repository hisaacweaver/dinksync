import streamlit as st

from db import (
    GENDERS,
    TEAMS,
    add_location,
    add_player,
    init_db,
    list_active_players,
    list_locations,
    update_player_details,
)


init_db()

st.title("Admin: Data Management")

player_col, location_col = st.columns(2)

with player_col:
    st.subheader("Players")
    with st.form("add_player"):
        player_name = st.text_input("Player name")
        player_team = st.selectbox("Team", TEAMS, index=TEAMS.index("Challenger"))
        player_gender = st.selectbox("Gender", GENDERS)
        submitted = st.form_submit_button("Add Player")

    if submitted:
        if add_player(player_name, player_team, player_gender):
            st.success("Player added.")
            st.rerun()
        else:
            st.warning("Enter a new player name.")

    players = list_active_players()
    if players:
        with st.form("update_player_details"):
            selected_player_label = st.selectbox(
                "Player to update",
                [f"{player['name']} ({player['team']}, {player['gender']})" for player in players],
            )
            selected_player = players[
                [f"{player['name']} ({player['team']}, {player['gender']})" for player in players].index(
                    selected_player_label
                )
            ]
            selected_name = st.text_input("Name", value=selected_player["name"])
            selected_team = st.selectbox(
                "Team assignment",
                TEAMS,
                index=TEAMS.index(selected_player["team"]),
            )
            selected_gender = st.selectbox(
                "Gender",
                GENDERS,
                index=GENDERS.index(selected_player["gender"]),
            )
            update_submitted = st.form_submit_button("Update Player")

        if update_submitted:
            if update_player_details(selected_player["id"], selected_name, selected_team, selected_gender):
                st.success("Player updated.")
                st.rerun()
            else:
                st.warning("Enter a unique player name.")

        st.dataframe(
            [{"Name": player["name"], "Team": player["team"], "Gender": player["gender"]} for player in players],
            hide_index=True,
            width='stretch',
        )
    else:
        st.info("No active players.")

with location_col:
    st.subheader("Locations")
    with st.form("add_location"):
        location_name = st.text_input("Location name")
        submitted = st.form_submit_button("Add Location")

    if submitted:
        if add_location(location_name):
            st.success("Location added.")
            st.rerun()
        else:
            st.warning("Enter a new location name.")

    locations = list_locations()
    if locations:
        st.dataframe(
            [{"Name": location["name"]} for location in locations],
            hide_index=True,
            width='stretch',
        )
    else:
        st.info("No saved locations.")
