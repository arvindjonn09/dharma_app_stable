import os
import json
import datetime
import subprocess
import secrets
import streamlit as st

from ui import apply_global_css, render_answer_html, render_source_html, render_mantra_html
from rag import retrieve_passages, answer_question, generate_styled_image
from database import (
    load_sessions,
    save_sessions,
    list_book_names,
    load_unreadable,
    load_favourites,
    save_favourites,
    load_approved_practices,
    save_approved_practices,
    load_practice_candidates,
    save_practice_candidates,
    SESSION_TTL_MINUTES,
    GUIDANCE_AUDIO_DIR,
    GUIDANCE_MEDIA_DIR,
)
from auth import (
    hash_password,
    check_password,
    load_users,
    save_users,
    get_admin_credentials,
)
from admin_tools import (
    scan_practice_candidates_from_chroma,
    fetch_online_practices,
)
from helpers import (
    load_feedback,
    save_feedback,
    get_daily_reflection,
    get_daily_focus,
    get_micro_practice,
    get_current_username,
)
from session_state_utils import bootstrap_session_state
from navigation import get_main_mode
from app_sections.admin_panel import render_admin_panel
from app_sections.home import render_home
from app_sections.meditation import render_meditation_journey
from app_sections.mantra import render_mantra_journey
from app_sections.my_journey import render_my_journey
from app_sections.dharma_chat import render_dharma_chat

# Ensure guidance media directories exist
os.makedirs(GUIDANCE_AUDIO_DIR, exist_ok=True)
os.makedirs(GUIDANCE_MEDIA_DIR, exist_ok=True)

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Dharma Story Chat", page_icon="📚", layout="wide")
st.write("✅ App file loaded. Initializing...")  # So page is never blank

apply_global_css()

# ---------- CONSTANTS ----------
BOOKS_DIR = "books"
COLLECTION_NAME = "saint_books"
UNREADABLE_FILE = "unreadable_books.json"
CHROMA_PATH = "./chroma_db"
USER_DB_FILE = "users.json"
FAVOURITES_FILE = "favourites.json"
PRACTICE_CANDIDATES_FILE = "practice_candidates.json"
APPROVED_PRACTICES_FILE = "approved_practices.json"
DAILY_REFLECTION_FILE = "daily_reflection.json"
FEEDBACK_FILE = "feedback.json"  # NEW: user feedback storage

# Make sure the books directory exists (for uploads on Streamlit Cloud)
os.makedirs(BOOKS_DIR, exist_ok=True)


# ---------- AUTH / ROLE SESSION STATE ----------
bootstrap_session_state(
    st,
    load_sessions,
    save_sessions,
    load_users,
    SESSION_TTL_MINUTES,
)

# ---------- LOGIN GATE ----------
current_role = st.session_state.get("role", "guest")

if current_role == "guest":
    st.title("📚 Dharma Story Chat")
    st.subheader("Sign in to continue")
    st.markdown("---")

    login_mode = st.radio(
        "Login as:",
        ["User", "Admin"],
        horizontal=True,
        key="login_mode",
    )

    if login_mode == "Admin":
        admin_user, admin_pass = get_admin_credentials()
        if not admin_user or not admin_pass:
            st.info(
                "Admin credentials are not configured.\n\n"
                "Set them via Streamlit secrets under [admin] or environment\n"
                "variables ADMIN_USERNAME and ADMIN_PASSWORD."
            )

        username_input = st.text_input("Admin username", key="admin_username_input")
        password_input = st.text_input("Admin password", type="password", key="admin_password_input")

        if st.button("Sign in as Admin", key="admin_login_submit"):
            if admin_user and admin_pass and username_input == admin_user and password_input == admin_pass:
                st.session_state["role"] = "admin"
                st.session_state["user_name"] = username_input
                st.session_state["age_group"] = None
                st.session_state["user_profile"] = {}

                sessions = load_sessions()
                token = secrets.token_urlsafe(16)
                sessions[token] = {
                    "role": "admin",
                    "username": username_input,
                    "created_at": datetime.datetime.now().isoformat(),
                }
                save_sessions(sessions)
                st.session_state["session_token"] = token

                st.success("Logged in as admin.")
                st.rerun()
            else:
                st.error("Invalid admin credentials.")
    else:
        # User login / signup
        user_auth_mode = st.radio(
            "Mode:",
            ["Sign in", "Sign up"],
            horizontal=True,
            key="user_auth_mode",
        )

        if user_auth_mode == "Sign in":
            username_input = st.text_input("Username", key="user_login_username")
            password_input = st.text_input("Password", type="password", key="user_login_password")

            if st.button("Sign in as User", key="user_login_submit"):
                if len(password_input.strip()) < 8 or not any(
                    ch in "!@#$%^&*()-_=+[]{};:'\",.<>/?|" for ch in password_input
                ):
                    st.error("Password must be at least 8 characters and contain a special character.")
                else:
                    users = load_users()
                    profile = users.get(username_input)

                    if not profile:
                        st.error("No account found with that username. Please sign up first.")
                    else:
                        stored_password = profile.get("password", "")
                        if not check_password(password_input.strip(), stored_password):
                            st.error("Incorrect password.")
                        else:
                            year = profile.get("year_of_birth")
                            age_group = None
                            if isinstance(year, int):
                                current_year = datetime.datetime.now().year
                                age = current_year - year
                                age_group = "adult" if age >= 22 else "child"

                            st.session_state["role"] = "user"
                            st.session_state["user_name"] = profile.get("first_name") or username_input
                            st.session_state["age_group"] = age_group
                            st.session_state["user_profile"] = profile

                            sessions = load_sessions()
                            token = secrets.token_urlsafe(16)
                            sessions[token] = {
                                "role": "user",
                                "username": username_input,
                                "created_at": datetime.datetime.now().isoformat(),
                            }
                            save_sessions(sessions)
                            st.session_state["session_token"] = token

                            st.success(f"Logged in as user ({age_group or 'unknown age'} mode).")
                            st.rerun()
        else:
            # Sign up
            username = st.text_input("Choose a username (must be unique)", key="signup_username")
            first_name = st.text_input("First name", key="signup_first_name")
            last_name = st.text_input("Last name", key="signup_last_name")
            year_str = st.text_input("Year of birth (YYYY)", key="signup_yob")

            password_input = st.text_input(
                "Create Password (min 8 chars, include at least one special character)",
                type="password",
                key="signup_password",
            )

            language = st.selectbox(
                "Preferred language",
                [
                    "English",
                    "Hindi",
                    "Telugu",
                    "Tamil",
                    "Kannada",
                    "Malayalam",
                    "Gujarati",
                    "Marathi",
                    "Other",
                ],
                key="signup_lang",
            )

            location = st.text_input(
                "Location (City, Country)",
                key="signup_location",
            )

            if st.button("Sign up", key="user_signup_submit"):
                if not username.strip():
                    st.error("Please choose a username.")
                elif not first_name.strip():
                    st.error("Please enter your first name.")
                elif len(password_input.strip()) < 8 or not any(
                    ch in "!@#$%^&*()-_=+[]{};:'\",.<>/?|" for ch in password_input
                ):
                    st.error("Password must be at least 8 characters and contain a special character.")
                else:
                    try:
                        current_year = datetime.datetime.now().year
                        year = int(year_str)
                        if year < 1900 or year > current_year:
                            st.error("Please enter a valid birth year.")
                        else:
                            users = load_users()
                            if username in users:
                                st.error("That username is already taken. Please choose another.")
                            else:
                                age = current_year - year
                                age_group = "adult" if age >= 22 else "child"
                                hashed_pw = hash_password(password_input.strip())

                                profile = {
                                    "username": username.strip(),
                                    "first_name": first_name.strip(),
                                    "last_name": last_name.strip() or None,
                                    "year_of_birth": year,
                                    "language": language,
                                    "location": location.strip() or None,
                                    "password": hashed_pw,
                                }

                                users[username] = profile
                                save_users(users)

                                st.session_state["role"] = "user"
                                st.session_state["user_name"] = first_name.strip()
                                st.session_state["age_group"] = age_group
                                st.session_state["user_profile"] = profile

                                sessions = load_sessions()
                                token = secrets.token_urlsafe(16)
                                sessions[token] = {
                                    "role": "user",
                                    "username": username.strip(),
                                    "created_at": datetime.datetime.now().isoformat(),
                                }
                                save_sessions(sessions)
                                st.session_state["session_token"] = token

                                st.success(f"Signed up and logged in as user ({age_group} mode).")
                                st.rerun()
                    except ValueError:
                        st.error("Please enter birth year as numbers (YYYY).")

    st.stop()

# ---------- SESSION EXPIRY INFO ----------
token = st.session_state.get("session_token")
if token:
    try:
        sessions = load_sessions()
        sess = sessions.get(token)
        if sess and sess.get("created_at"):
            created_dt = datetime.datetime.fromisoformat(sess["created_at"])
            now_dt = datetime.datetime.now()
            minutes_used = (now_dt - created_dt).total_seconds() / 60.0
            if 30 <= minutes_used < SESSION_TTL_MINUTES:
                st.info(
                    "For your safety, this session will expire after 40 minutes. "
                    "If you are writing a long reflection, consider finishing and saving soon."
                )
    except Exception:
        pass

# ---------- TOP BAR ----------
col_title, col_login = st.columns([4, 1])

with col_title:
    st.title("📚 Dharma Story Chat — Story Mode (All Books)")
    st.write("Stories come from **all** your uploaded books. Each answer shows which books were used.")

with col_login:
    role = st.session_state.get("role", "guest")
    user_name = st.session_state.get("user_name")
    age_group = st.session_state.get("age_group")

    if role == "admin":
        st.markdown("👑 **Admin**")
        if st.button("Logout", key="logout_button_admin"):
            token = st.session_state.get("session_token")
            if token:
                sessions = load_sessions()
                sessions.pop(token, None)
                save_sessions(sessions)
                st.session_state["session_token"] = None

            st.session_state["role"] = "guest"
            st.session_state["user_name"] = None
            st.session_state["age_group"] = None
            st.session_state["user_profile"] = {}
            st.rerun()

    elif role == "user":
        label = "🙂 User"
        if age_group == "child":
            label += " (Child mode)"
        elif age_group == "adult":
            label += " (Adult)"
        if user_name:
            label += f": {user_name}"
        st.markdown(label)

        if st.button("📜 Saved stories", key="history_toggle_button"):
            st.session_state["show_history_panel"] = not st.session_state.get("show_history_panel", False)

        if st.button("Logout", key="logout_button_user"):
            token = st.session_state.get("session_token")
            if token:
                sessions = load_sessions()
                sessions.pop(token, None)
                save_sessions(sessions)
                st.session_state["session_token"] = None

            st.session_state["role"] = "guest"
            st.session_state["user_name"] = None
            st.session_state["age_group"] = None
            st.session_state["user_profile"] = {}
            st.session_state["show_history_panel"] = False
            st.rerun()

# ---------- ADMIN PANEL ----------
role = st.session_state.get("role", "guest")
if role == "admin":
    render_admin_panel(
        BOOKS_DIR=BOOKS_DIR,
        DAILY_REFLECTION_FILE=DAILY_REFLECTION_FILE,
        GUIDANCE_AUDIO_DIR=GUIDANCE_AUDIO_DIR,
        GUIDANCE_MEDIA_DIR=GUIDANCE_MEDIA_DIR,
        load_feedback_func=load_feedback,
        save_feedback_func=save_feedback,
        FEEDBACK_FILE=FEEDBACK_FILE,
    )
# ---------- MAIN USER NAVIGATION ----------
main_mode = get_main_mode()

# ---------- USER SAVED STORIES PANEL ----------
if (
    st.session_state.get("role") == "user"
    and st.session_state.get("show_history_panel", False)
    and main_mode == "Dharma chat"
):
    username = get_current_username()
    favs_all = load_favourites()
    user_favs = favs_all.get(username, []) if username else []

    with st.expander("⭐ Your saved stories", expanded=True):
        if not user_favs:
            st.write("You have not saved any stories yet. Tap '⭐ Save this story' under a story to add it here.")
        else:
            for i, item in enumerate(reversed(user_favs), start=1):
                ts = item.get("timestamp", "")
                books_used = item.get("books_used") or []
                title_line = f"Story {i}"
                if ts:
                    title_line += f" — saved at {ts}"
                st.markdown(f"**{title_line}**")
                if books_used:
                    st.markdown(f"_Books: {', '.join(sorted(books_used))}_")
                preview = item.get("content", "")
                if len(preview) > 1200:
                    preview = preview[:1200] + " ..."
                st.markdown(f"<div class='answer-text'>{preview}</div>", unsafe_allow_html=True)
                st.markdown("---")

st.markdown("---")

# ---------- MAIN CONTENT: HOME / JOURNEYS ----------
if "book_list" not in locals():
    book_list = list_book_names()


# ---------- HOME ----------
if main_mode == "Home":
    render_home(DAILY_REFLECTION_FILE)

# ---------- DHARMA CHAT ----------
elif main_mode == "Dharma chat":
    render_dharma_chat(book_list)

# ---------- MEDITATION JOURNEY ----------
elif main_mode == "Meditation journey":
    render_meditation_journey()

# ---------- MANTRA JOURNEY ----------
elif main_mode == "Mantra chanting journey":
    render_mantra_journey()

# ---------- MY JOURNEY ----------
elif main_mode == "My Journey":
    render_my_journey()

# ---------- FEEDBACK ----------
elif main_mode == "Feedback":
    st.header("📝 Feedback")

    if st.session_state.get("role") != "user":
        st.info("Feedback can be submitted only by logged-in users.")
    else:
        st.write(
            "If you notice any issue, incorrect information, or if you have ideas to improve the app, "
            "please share it here. Admin will see this in the **Feedback collection** panel."
        )

        feedback_category = st.selectbox(
            "Type of feedback",
            [
                "Bug / technical issue",
                "Content issue (stories / mantras / guidance)",
                "New feature or improvement idea",
                "Other",
            ],
            key="feedback_category",
        )

        feedback_text = st.text_area(
            "Describe your feedback in detail",
            key="feedback_text",
            height=180,
        )

        contact_info = st.text_input(
            "Optional contact (email or any detail, if you want admin to contact you)",
            key="feedback_contact",
        )

        submitted = st.button("Submit feedback", key="feedback_submit")

        if submitted:
            # ✅ Make description mandatory
            if not feedback_text.strip():
                st.error("Please describe your feedback before submitting.")
            else:
                items = load_feedback(FEEDBACK_FILE)
                items.append(
                    {
                        "username": get_current_username() or "unknown",
                        "category": feedback_category,
                        "text": feedback_text.strip(),
                        "contact": contact_info.strip(),
                        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                )
                save_feedback(FEEDBACK_FILE, items)

                # Mark that feedback was submitted (optional helper flag)
                st.session_state["feedback_submitted_once"] = True

                # ✅ Clear message, no rerun so the user can see it
                st.success(
                    "Thanks for your feedback — it really helps us to build this application better."
                )

        # Optional extra info below the button
        if st.session_state.get("feedback_submitted_once"):
            st.info("You can submit more feedback anytime if you notice anything else.")

# ---------- FOOTER ----------
st.markdown("---")
st.markdown(
    """
<small>
This app shares dharmic stories and guidance based on uploaded texts.  
It is meant to gently support your spiritual journey, not replace a living teacher,
doctor, or mental-health professional.  
If you feel very distressed or unsafe, please seek proper help and speak to someone you trust.
</small>
    """,
    unsafe_allow_html=True,
)
