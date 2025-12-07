import os
import streamlit as st

from database import load_approved_practices
from auth import save_users, load_users


def render_meditation_journey():
    st.header("🧘 Meditation journey")
    st.markdown(
        "Move step-by-step through simple guided meditations. "
        "Read the guidance, practice quietly, then mark the level as completed."
    )

    if st.session_state.get("role") != "user":
        st.info("Meditation levels are available for logged-in users only.")
        return

    approved = load_approved_practices()
    med_practices = approved.get("meditation", [])

    profile = st.session_state.get("user_profile") or {}
    med_level = profile.get("meditation_level", 1)

    if not med_practices:
        st.info(
            "No approved meditation practices are available yet. "
            "Ask the admin to approve some meditation passages from the books."
        )
        return

    max_level = min(20, len(med_practices))
    if med_level > max_level:
        st.success("You have completed all available meditation levels.")
        st.write(f"Current meditation level: {med_level}")
        return

    practice = med_practices[med_level - 1]
    src = practice.get("source") or "unknown"

    st.subheader(f"Meditation Level {med_level} of {max_level}")
    st.markdown(f"_Source: {os.path.basename(src)}_")
    st.progress((med_level - 1) / max_level)
    st.markdown(
        f"<div class='answer-text'>{practice.get('text', '')}</div>",
        unsafe_allow_html=True,
    )

    audio_path = practice.get("audio_path")
    if audio_path and os.path.exists(audio_path):
        st.markdown("**Listen to this guided meditation:**")
        st.audio(audio_path)

    image_path = practice.get("image_path")
    if image_path and os.path.exists(image_path):
        st.markdown("**Sacred image for this meditation:**")
        st.image(image_path, use_column_width=True)

    video_path = practice.get("video_path")
    if video_path and os.path.exists(video_path):
        st.markdown("**Video guidance for this meditation:**")
        st.video(video_path)

    reflection = st.text_area(
        "What did you feel or notice in this practice?",
        key=f"med_reflection_{med_level}",
    )

    if st.button("Mark this level as completed", key=f"med_complete_{med_level}"):
        med_reflections = profile.get("meditation_reflections") or {}
        if reflection.strip():
            med_reflections[str(med_level)] = reflection.strip()
        profile["meditation_reflections"] = med_reflections

        profile["meditation_level"] = med_level + 1
        st.session_state["user_profile"] = profile

        username = profile.get("username")
        if username:
            users = load_users()
            users[username] = profile
            save_users(users)

        st.success("Meditation level completed. Next time you'll see the next level.")
        st.rerun()
