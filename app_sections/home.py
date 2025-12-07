import streamlit as st

from helpers import (
    get_daily_reflection,
    get_daily_focus,
    get_micro_practice,
)


def render_home(daily_reflection_file: str):
    age_group = st.session_state.get("age_group")
    try:
        daily_line = get_daily_reflection(age_group, daily_reflection_file)
        daily_focus = get_daily_focus(age_group)
        micro_practice = get_micro_practice(age_group)
    except Exception:
        daily_line = None
        daily_focus = None
        micro_practice = None

    st.title("Welcome to Dharma Story Chat")

    if daily_line:
        st.markdown("### 🌅 Today's reflection")
        st.markdown(
            f"<div class='daily-reflection'>{daily_line}</div>",
            unsafe_allow_html=True,
        )
    if daily_focus:
        st.markdown("#### 🎯 Today's focus")
        st.write(daily_focus)
    if micro_practice:
        st.markdown("#### 🕯️ Tiny practice for today")
        st.write(micro_practice)

    st.markdown("---")
    st.info(
        "Head to **Dharma chat** to ask for stories, use quick mood buttons, and save favourites. "
        "Use the top menu to navigate."
    )
