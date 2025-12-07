import streamlit as st


def get_main_mode():
    """Return the selected main mode for users; guests stay on Home."""
    if st.session_state.get("role") == "user":
        return st.radio(
            "Where would you like to go?",
            [
                "Home",
                "Dharma chat",
                "Meditation journey",
                "Mantra chanting journey",
                "My Journey",
                "Feedback",
            ],
            horizontal=True,
            key="main_nav_mode",
        )
    return "Home"
