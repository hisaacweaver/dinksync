import streamlit as st

from db import init_db


st.set_page_config(page_title="BYU PB Scheduling", layout="wide", initial_sidebar_state="collapsed")
init_db()


ADMIN_PAGES = [
    st.Page(
        "views/admin_create_availability.py",
        title="Create Availability",
        icon="🗓️",
        url_path="admin-create-availability",
    ),
    st.Page(
        "views/admin_view_responses.py",
        title="View Responses",
        icon="📋",
        url_path="admin-view-responses",
    ),
    st.Page(
        "views/admin_create_schedule.py",
        title="Create Schedule",
        icon="✅",
        url_path="admin-create-schedule",
    ),
    st.Page(
        "views/view_schedule.py",
        title="View Schedule",
        icon="📆",
        url_path="view-schedule",
    ),
    st.Page(
        "views/admin_data_management.py",
        title="Data Management",
        icon="⚙️",
        url_path="admin-data-management",
    ),
]

PLAYER_PAGE = st.Page(
    "views/player_submit_availability.py",
    title="Submit Availability",
    icon="🏓",
    url_path="player-submit-availability",
)

PLAYER_LEGACY_PAGE = st.Page(
    "views/player_submit_availability.py",
    title="Submit Availability",
    icon="🏓",
    url_path="Player_Submit_Availability",
)


def is_admin() -> bool:
    return bool(st.session_state.get("is_admin"))


def render_login() -> None:
    with st.sidebar:
        st.subheader("Admin login")

        password = st.text_input(
            "Password",
            type="password",
            key="admin_password_input",
        )

        if st.button("Log in"):
            if password == st.secrets["ADMIN_PASSWORD"]:
                st.session_state["is_admin"] = True
                st.rerun()
            else:
                st.error("Invalid password.")


def render_logout() -> None:
    with st.sidebar:
        if st.button("Log out"):
            st.session_state["is_admin"] = False
            st.rerun()


if is_admin():
    render_logout()

    nav = st.navigation(
        {
            "Admin": ADMIN_PAGES,
            "Player": [PLAYER_PAGE],
        },
        position="sidebar",
    )
else:
    render_login()

    # Non-admin users only get the player availability page.
    # No sidebar page navigation is shown.
    nav = st.navigation(
        [PLAYER_PAGE, PLAYER_LEGACY_PAGE],
        position="hidden",
    )

nav.run()
