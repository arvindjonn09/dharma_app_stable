import os  # safeguard for any downstream usage
import streamlit as st

from app_sections.admin_books import render_admin_books
from app_sections.admin_practices import render_admin_practices
from app_sections.admin_guidance import render_admin_guidance
from app_sections.admin_structured_view import render_admin_structured_view
from app_sections.admin_reflection import render_admin_reflection
from app_sections.admin_online import render_admin_online
from app_sections.admin_feedback import render_admin_feedback


def render_admin_panel(
    BOOKS_DIR,
    DAILY_REFLECTION_FILE,
    GUIDANCE_AUDIO_DIR,
    GUIDANCE_MEDIA_DIR,
    load_feedback_func,
    save_feedback_func,
    FEEDBACK_FILE,
):
    admin_view = st.radio(
        "Admin panel:",
        [
            "Books & indexing",
            "Approved practices",
            "Guidance",
            "Daily reflection",
            "Internet search",
            "Feedback collection",
        ],
        horizontal=True,
        key="admin_view_mode",
    )

    if admin_view == "Books & indexing":
        render_admin_books(BOOKS_DIR)
    elif admin_view == "Approved practices":
        render_admin_practices()
    elif admin_view == "Guidance":
        render_admin_guidance(GUIDANCE_AUDIO_DIR, GUIDANCE_MEDIA_DIR)
        render_admin_structured_view()
    elif admin_view == "Internet search":
        render_admin_online()
    elif admin_view == "Daily reflection":
        render_admin_reflection(DAILY_REFLECTION_FILE)
    elif admin_view == "Feedback collection":
        render_admin_feedback(load_feedback_func, FEEDBACK_FILE)
