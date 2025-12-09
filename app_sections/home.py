import os
import streamlit as st

from helpers import get_daily_reflection


def render_home(daily_reflection_file: str):
    age_group = st.session_state.get("age_group")
    try:
        daily_line, image_url = get_daily_reflection(age_group, daily_reflection_file)
    except Exception:
        daily_line, image_url = None, None

    st.title("Welcome to Dharma Story Chat")

    if daily_line or image_url:
        st.markdown("### 🌅 Today's reflection")
        if image_url:
            # Allow local file paths as well as URLs
            if image_url.startswith("http://") or image_url.startswith("https://"):
                st.image(image_url, use_column_width=True, caption=None)
            else:
                img_path = image_url
                if not os.path.isabs(img_path):
                    img_path = os.path.abspath(img_path)
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        st.image(f.read(), use_column_width=True, caption=None)
                else:
                    st.info("Reflection image is not available on this server.")
        if daily_line:
            st.markdown(
                f"<div class='daily-reflection'>{daily_line}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.info(
        "Head to **Dharma chat** to ask for stories, use quick mood buttons, and save favourites. "
        "Use the top menu to navigate."
    )
