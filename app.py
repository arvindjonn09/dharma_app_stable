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
# ---------- SIMPLE FILE HELPERS (FEEDBACK) ----------
def load_feedback():
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except FileNotFoundError:
        return []
    except Exception:
        return []


def save_feedback(items):
    try:
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------- DAILY REFLECTION ----------
def get_daily_reflection(age_group):
    """
    Return a short, gentle reflection line for the day.

    We keep this simple and static for now, rotating through a small set
    based on the current date, and adjust tone slightly for child/adult.
    """
    # First, try to use an admin-chosen override stored on disk.
    overrides = {}
    try:
        with open(DAILY_REFLECTION_FILE, "r", encoding="utf-8") as f:
            overrides = json.load(f)
    except Exception:
        overrides = {}

    if isinstance(overrides, dict):
        # Prefer age-specific override if present
        if age_group == "child" and overrides.get("child"):
            return overrides["child"]
        if age_group == "adult" and overrides.get("adult"):
            return overrides["adult"]
        # Fallback generic reflection for all ages
        if overrides.get("both"):
            return overrides["both"]

    # Adult reflections
    adult_reflections = [
        "Pause once today and remember: every small act of kindness can be placed at the Lord's feet like a flower.",
        "When the mind becomes restless, gently return to the breath and recall one quality of your chosen deity.",
        "Before sleep, think of one moment today where you could have been softer. Offer that moment into inner light.",
        "Wherever you are today, imagine you are standing in a sacred space. Speak and act as if the Divine is listening.",
        "If worry arises, quietly say: 'I am not alone in this. May I act with dharma and trust.'",
    ]

    # Child reflections
    child_reflections = [
        "Can you share something today and imagine you are sharing it with God?",
        "If you feel angry today, take three slow breaths and think of your favourite form of the Divine smiling at you.",
        "Try to tell the truth today even in small things. Saints smile when you are honest.",
        "Before you sleep, thank the Divine for one happy moment from your day.",
        "When you see someone sad today, can you say one kind word for them in your heart?",
    ]

    today = datetime.date.today()
    idx = today.toordinal()

    if age_group == "child":
        items = child_reflections
    else:
        items = adult_reflections

    return items[idx % len(items)]


def get_current_username():
    profile = st.session_state.get("user_profile") or {}
    return profile.get("username") or st.session_state.get("user_name")


# ---------- AUTH / ROLE SESSION STATE ----------
if "role" not in st.session_state:
    st.session_state["role"] = "guest"  # "guest", "admin", "user"
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "age_group" not in st.session_state:
    st.session_state["age_group"] = None  # "child", "adult", or None
if "user_profile" not in st.session_state:
    st.session_state["user_profile"] = {}

if "show_history_panel" not in st.session_state:
    st.session_state["show_history_panel"] = False
if "session_token" not in st.session_state:
    st.session_state["session_token"] = None

# Attempt auto-restore of login if we are currently a guest
current_role = st.session_state.get("role", "guest")
if current_role == "guest":
    token_list = st.query_params.get("session", [])
    if isinstance(token_list, str):
        token_list = [token_list]
    if token_list:
        token = token_list[0]
        sessions = load_sessions()
        sess = sessions.get(token)
        if sess:
            created_str = sess.get("created_at")
            expired = False
            if created_str:
                try:
                    created_dt = datetime.datetime.fromisoformat(created_str)
                    now_dt = datetime.datetime.now()
                    if now_dt - created_dt > datetime.timedelta(minutes=SESSION_TTL_MINUTES):
                        expired = True
                except Exception:
                    expired = True
            if expired:
                sessions.pop(token, None)
                save_sessions(sessions)
            else:
                role_from_sess = sess.get("role")
                username_from_sess = sess.get("username")
                if role_from_sess == "admin":
                    st.session_state["role"] = "admin"
                    st.session_state["user_name"] = username_from_sess or "admin"
                    st.session_state["age_group"] = None
                    st.session_state["user_profile"] = {}
                    st.session_state["session_token"] = token
                elif role_from_sess == "user" and username_from_sess:
                    users = load_users()
                    profile = users.get(username_from_sess)
                    if profile:
                        year = profile.get("year_of_birth")
                        age_group = None
                        if isinstance(year, int):
                            current_year = datetime.datetime.now().year
                            age = current_year - year
                            age_group = "adult" if age >= 22 else "child"
                        st.session_state["role"] = "user"
                        st.session_state["user_name"] = profile.get("first_name") or username_from_sess
                        st.session_state["age_group"] = age_group
                        st.session_state["user_profile"] = profile
                        st.session_state["session_token"] = token

# ---------- SESSION STATE FOR CHAT / SEARCH ----------
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "generate_image" not in st.session_state:
    st.session_state["generate_image"] = False
if "online_search_results" not in st.session_state:
    st.session_state["online_search_results"] = []
if "reflection_suggestions" not in st.session_state:
    st.session_state["reflection_suggestions"] = []

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

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("Options")
    st.checkbox(
        "Generate cartoon illustration for each story",
        key="generate_image",
        help="Automatically creates ACK or Clay style images.",
    )

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
    admin_view = st.radio(
        "Admin panel:",
        [
            "Books & indexing",
            "Approved practices",
            "Guidance",
            "Daily reflection",
            "Internet search",
            "Feedback collection",  # NEW
        ],
        horizontal=True,
        key="admin_view_mode",
    )

    if admin_view == "Books & indexing":
        st.subheader("📚 Books & indexing")

        st.write(
            "Upload new PDF/EPUB books here. They will be stored only on the server "
            "(not in GitHub) and used after you reindex."
        )

        # 1) Upload new books into the books/ folder
        uploaded_books = st.file_uploader(
            "Upload one or more books (PDF / EPUB)",
            type=["pdf", "epub"],
            accept_multiple_files=True,
            key="admin_books_uploader",
        )

        if uploaded_books:
            if st.button("📥 Save uploaded books", key="save_uploaded_books"):
                saved_files = []
                for f in uploaded_books:
                    # Clean filename
                    original_name = os.path.basename(f.name)
                    if not original_name:
                        continue

                    base, ext = os.path.splitext(original_name)
                    if not ext:
                        ext = ".pdf"  # default if no extension

                    # Avoid overwriting existing files: add suffix if needed
                    dest_path = os.path.join(BOOKS_DIR, original_name)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(BOOKS_DIR, f"{base}_{counter}{ext}")
                        counter += 1

                    with open(dest_path, "wb") as out:
                        out.write(f.getbuffer())

                    saved_files.append(os.path.basename(dest_path))

                if saved_files:
                    st.success(f"Saved {len(saved_files)} book(s): " + ", ".join(saved_files))
                    st.info("Now click **'🔄 Reindex books now'** below so the app can read them.")
                else:
                    st.warning("No valid files were saved. Please try again.")

        st.markdown("---")

        # 2) Reindex button (unchanged logic)
        if st.button("🔄 Reindex books now", key="admin_reindex"):
            with st.spinner("Reindexing books from the 'books' folder..."):
                try:
                    result = subprocess.run(
                        ["python3", "prepare_data.py"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    st.success("Reindexing finished successfully.")

                    if result.stdout:
                        st.text_area("Reindex log (stdout)", result.stdout, height=200)
                    if result.stderr:
                        st.text_area("Reindex log (stderr)", result.stderr, height=200)

                    # Clear any cached Chroma / book list
                    st.cache_data.clear()
                    st.cache_resource.clear()
                except subprocess.CalledProcessError as e:
                    st.error("Reindexing failed. See log below.")
                    err_text = e.stderr or str(e)
                    st.text_area("Error log", err_text, height=200)

        st.markdown("---")

        # 3) Unreadable books info (as before)
        unreadable = load_unreadable()
        if unreadable:
            st.warning("Some books could not be read completely (scanned or problematic):")
            for path, reason in unreadable.items():
                st.write(f"- `{os.path.basename(path)}` — {reason}")

        # 4) Show list of books currently in the library
        book_list = list_book_names()
        if book_list:
            with st.expander("Books currently available"):
                for b in book_list:
                    st.write("•", b)
        else:
            st.info("No books found yet in 'books/' folder.")
    elif admin_view == "Approved practices":
        st.subheader("✅ Approved practices overview")
        st.write(
            "Here you can see all meditation and mantra practices that have already been approved "
            "for users, and you can filter, edit, or remove them."
        )

        approved = load_approved_practices()
        med_practices = approved.get("meditation", []) or []
        mantra_practices = approved.get("mantra", []) or []

        if not med_practices and not mantra_practices:
            st.info("No practices have been approved yet. Use the Practice approval section below to approve some.")
        else:
            col_m, col_j = st.columns(2)

            # LEFT: Meditation
            with col_m:
                st.markdown("### 🧘 Meditation practices")

                if not med_practices:
                    st.write("No meditation practices approved yet.")
                else:
                    level_filter = st.selectbox(
                        "Filter by level (index-based)",
                        ["All levels", "Beginner", "Intermediate", "Deeper"],
                        key="meditation_level_filter",
                    )

                    def _med_band_for_index(idx: int) -> str:
                        if idx <= 3:
                            return "Beginner"
                        elif idx <= 7:
                            return "Intermediate"
                        else:
                            return "Deeper"

                    for idx, p in enumerate(med_practices, start=1):
                        band = _med_band_for_index(idx)
                        if level_filter != "All levels" and band != level_filter:
                            continue

                        src = p.get("source") or "manual-guidance"
                        text_full = p.get("text", "") or ""
                        text_preview = text_full
                        if len(text_preview) > 260:
                            text_preview = text_preview[:260] + " ..."

                        header = f"Meditation {idx} ({band}) — Source: {os.path.basename(src)}"
                        with st.expander(header, expanded=False):
                            st.markdown(
                                f"<div class='source-text'>{text_preview}</div>",
                                unsafe_allow_html=True,
                            )

                            audio_path = p.get("audio_path")
                            if audio_path and os.path.exists(audio_path):
                                st.markdown("**Audio preview:**")
                                st.audio(audio_path)

                            image_path = p.get("image_path")
                            if image_path and os.path.exists(image_path):
                                st.markdown("**Image preview:**")
                                st.image(image_path, use_column_width=True)

                            video_path = p.get("video_path")
                            if video_path and os.path.exists(video_path):
                                st.markdown("**Video preview:**")
                                st.video(video_path)

                            st.markdown("---")

                            new_text = st.text_area(
                                "Edit meditation text",
                                value=text_full,
                                key=f"med_edit_text_{idx}",
                                height=180,
                            )

                            col_save, col_del = st.columns(2)
                            with col_save:
                                if st.button("Save changes", key=f"med_save_{idx}"):
                                    updated = load_approved_practices()
                                    med_list = updated.get("meditation", []) or []
                                    if 0 <= idx - 1 < len(med_list):
                                        med_list[idx - 1]["text"] = new_text.strip()
                                        updated["meditation"] = med_list
                                        save_approved_practices(updated)
                                        st.success("Meditation updated.")
                                        st.rerun()
                            with col_del:
                                if st.button("Delete this meditation", key=f"med_delete_{idx}"):
                                    updated = load_approved_practices()
                                    med_list = updated.get("meditation", []) or []
                                    if 0 <= idx - 1 < len(med_list):
                                        med_list.pop(idx - 1)
                                        updated["meditation"] = med_list
                                        save_approved_practices(updated)
                                        st.warning("Meditation deleted.")
                                        st.rerun()

            # RIGHT: Mantra
            with col_j:
                st.markdown("### 📿 Mantra practices")

                if not mantra_practices:
                    st.write("No mantra practices approved yet.")
                else:
                    deity_names = set()
                    for p in mantra_practices:
                        d = (p.get("deity") or "General").strip()
                        if not d:
                            d = "General"
                        deity_names.add(d)
                    deity_list = sorted(deity_names, key=str.lower)

                    deity_filter = st.selectbox(
                        "Filter by deity",
                        ["All deities"] + deity_list,
                        key="mantra_deity_filter",
                    )

                    level_filter = st.selectbox(
                        "Filter by level band",
                        ["All levels", "Beginner", "Intermediate", "Deeper"],
                        key="mantra_level_filter",
                    )

                    def _mantra_band_for_level(lvl: int) -> str:
                        if lvl <= 3:
                            return "Beginner"
                        elif lvl <= 7:
                            return "Intermediate"
                        else:
                            return "Deeper"

                    for idx, p in enumerate(mantra_practices, start=1):
                        deity = (p.get("deity") or "General").strip()
                        if not deity:
                            deity = "General"

                        try:
                            lvl_val = int(p.get("level", 1))
                        except Exception:
                            lvl_val = 1
                        band = _mantra_band_for_level(lvl_val)

                        if deity_filter != "All deities" and deity != deity_filter:
                            continue
                        if level_filter != "All levels" and band != level_filter:
                            continue

                        age_meta = p.get("age_group") or "both"
                        if age_meta == "child":
                            age_label = "Children"
                        elif age_meta == "adult":
                            age_label = "Adults"
                        else:
                            age_label = "All ages"

                        src = p.get("source") or "manual-guidance"
                        raw_mantra = p.get("mantra_text") or p.get("text") or ""
                        preview = raw_mantra
                        if len(preview) > 260:
                            preview = preview[:260] + " ..."

                        safe_preview = (
                            preview.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )

                        heading = f"{deity} — Level {lvl_val} ({band}) — Visible to: {age_label}"
                        with st.expander(heading, expanded=False):
                            st.markdown(
                                f"<div class='mantra-box'>{safe_preview}</div>",
                                unsafe_allow_html=True,
                            )

                            audio_path = p.get("audio_path")
                            if audio_path and os.path.exists(audio_path):
                                st.markdown("**Audio preview:**")
                                st.audio(audio_path)

                            image_path = p.get("image_path")
                            if image_path and os.path.exists(image_path):
                                st.markdown("**Image preview:**")
                                st.image(image_path, use_column_width=True)

                            video_path = p.get("video_path")
                            if video_path and os.path.exists(video_path):
                                st.markdown("**Video preview:**")
                                st.video(video_path)

                            st.markdown("---")

                            edit_deity = st.text_input(
                                "Deity / God name",
                                value=deity,
                                key=f"mantra_deity_{idx}",
                            )

                            edit_level = st.number_input(
                                "Level (1 = beginner, higher = deeper)",
                                min_value=1,
                                max_value=20,
                                value=lvl_val,
                                step=1,
                                key=f"mantra_level_{idx}",
                            )

                            if age_meta == "child":
                                age_index = 1
                            elif age_meta == "adult":
                                age_index = 2
                            else:
                                age_index = 0
                            edit_age_choice = st.selectbox(
                                "Who is this mantra suitable for?",
                                ["All ages", "Children", "Adults"],
                                index=age_index,
                                key=f"mantra_age_{idx}",
                            )
                            if edit_age_choice == "Children":
                                edit_age_code = "child"
                            elif edit_age_choice == "Adults":
                                edit_age_code = "adult"
                            else:
                                edit_age_code = "both"

                            edit_mantra_text = st.text_area(
                                "Mantra text (exactly as shown to users)",
                                value=p.get("mantra_text") or "",
                                key=f"mantra_text_edit_{idx}",
                                height=120,
                            )
                            edit_desc = st.text_area(
                                "Description / meaning / guidance",
                                value=p.get("text") or "",
                                key=f"mantra_desc_edit_{idx}",
                                height=160,
                            )

                            col_save, col_del = st.columns(2)
                            with col_save:
                                if st.button("Save changes", key=f"mantra_save_{idx}"):
                                    updated = load_approved_practices()
                                    man_list = updated.get("mantra", []) or []
                                    if 0 <= idx - 1 < len(man_list):
                                        entry = man_list[idx - 1]
                                        entry["deity"] = edit_deity.strip()
                                        entry["level"] = int(edit_level)
                                        entry["age_group"] = edit_age_code
                                        entry["mantra_text"] = edit_mantra_text.rstrip()
                                        entry["text"] = edit_desc.strip()
                                        man_list[idx - 1] = entry
                                        updated["mantra"] = man_list
                                        save_approved_practices(updated)
                                        st.success("Mantra updated.")
                                        st.rerun()
                            with col_del:
                                if st.button("Delete this mantra", key=f"mantra_delete_{idx}"):
                                    updated = load_approved_practices()
                                    man_list = updated.get("mantra", []) or []
                                    if 0 <= idx - 1 < len(man_list):
                                        man_list.pop(idx - 1)
                                        updated["mantra"] = man_list
                                        save_approved_practices(updated)
                                        st.warning("Mantra deleted.")
                                        st.rerun()

        # ---- PRACTICE APPROVAL (candidates) ----
        st.subheader("Practice approval (mantra / meditation)")
        st.write(
            "From the uploaded dharmic texts, the app can suggest passages that feel "
            "suitable for gentle meditation or mantra remembrance. As admin, you can "
            "review and bless which of these become guided practices for seekers."
        )

        practice_scope = st.radio(
            "What would you like to review now?",
            ["Meditation", "Mantras", "Both"],
            horizontal=True,
            key="practice_scope_mode",
        )

        if practice_scope == "Meditation":
            kind_filter = "meditation"
        elif practice_scope == "Mantras":
            kind_filter = "mantra"
        else:
            kind_filter = None  # Both

        available_books = list_book_names()
        selected_books = st.multiselect(
            "Limit scan to specific books (optional):",
            options=available_books,
            default=[],
            help="If you leave this empty, all indexed books will be scanned.",
            key="practice_book_filter",
        )

        extra_keywords_str = st.text_input(
            "Extra keywords for scanning (optional, comma-separated)",
            key="practice_extra_keywords",
            help="Example: 'mudra, pranayama, japa, dharana'",
        )

        extra_keywords = []
        if extra_keywords_str.strip():
            extra_keywords = [w.strip() for w in extra_keywords_str.split(",") if w.strip()]

        if st.button("🔍 Scan books for new practice candidates", key="scan_practices"):
            with st.spinner("Scanning books for related passages..."):
                candidates = scan_practice_candidates_from_chroma(
                    kind_filter=kind_filter,
                    book_filter=selected_books if selected_books else None,
                    extra_keywords=extra_keywords,
                )
            st.success(f"Scan complete. Total candidates stored: {len(candidates)}")
        else:
            candidates = load_practice_candidates()

        if selected_books:
            selected_set = set(selected_books)
            filtered_candidates = []
            for c in candidates:
                src = c.get("source") or ""
                fname = os.path.basename(src) if src else ""
                if fname in selected_set:
                    filtered_candidates.append(c)
            candidates = filtered_candidates

        approved = load_approved_practices()

        if not candidates:
            st.info(
                "No possible practice passages have been collected yet. "
                "Use 'Scan books' to let the app suggest places where the texts "
                "speak about meditation or mantra remembrance."
            )
        else:
            st.markdown("### Pending candidates")
            any_pending = False
            approve_states = []

            for idx, cand in enumerate(candidates):
                if cand.get("approved"):
                    continue

                kind = cand.get("kind", "unknown")
                if kind_filter == "mantra" and kind != "mantra":
                    continue
                if kind_filter == "meditation" and kind != "meditation":
                    continue

                any_pending = True
                src = cand.get("source") or "unknown"
                text = cand.get("text") or ""

                label_kind = "MEDITATION" if kind == "meditation" else "MANTRA" if kind == "mantra" else kind.upper()
                with st.expander(f"[{label_kind}] from {os.path.basename(src)}", expanded=False):
                    st.markdown(f"<div class='source-text'>{text}</div>", unsafe_allow_html=True)
                    ck = st.checkbox(
                        "Approve this practice",
                        key=f"approve_cand_{idx}",
                    )
                    approve_states.append((idx, ck))

            if not any_pending:
                st.info("No unapproved candidates at the moment.")

            if approve_states and st.button("💾 Save approvals", key="save_practice_approvals"):
                candidates = load_practice_candidates()
                approved = load_approved_practices()

                for idx, is_checked in approve_states:
                    if not is_checked:
                        continue
                    if idx < 0 or idx >= len(candidates):
                        continue
                    cand = candidates[idx]
                    if cand.get("approved"):
                        continue

                    kind = cand.get("kind", "unknown")
                    if kind not in ("mantra", "meditation"):
                        continue

                    cand["approved"] = True
                    practices_list = approved.get(kind) or []
                    practices_list.append(
                        {
                            "text": cand.get("text", ""),
                            "source": cand.get("source", ""),
                        }
                    )
                    approved[kind] = practices_list

                save_practice_candidates(candidates)
                save_approved_practices(approved)
                st.success("Selected practices have been approved and saved.")
                st.rerun()

    elif admin_view == "Guidance":
        st.subheader("Guided practices (manual)")
        st.write(
            "Here you can gently add your own meditation or mantra guidance. "
            "You may write a short passage and optionally attach an audio, image, or video file. "
            "Seekers will first see the text, then can listen or watch the guidance."
        )

        guidance_kind = st.radio(
            "What type of guidance would you like to add?",
            ["Meditation", "Mantra"],
            horizontal=True,
            key="guidance_kind_mode",
        )

        deity_name = ""
        age_group_code = "both"
        level_number = 1
        guidance_text = ""
        mantra_lines = ""
        mantra_desc = ""

        if guidance_kind == "Meditation":
            kind_key = "meditation"
            st.markdown("**Meditation guidance text:**")
            guidance_text = st.text_area(
                "Meditation guidance (this will appear before any audio/image/video):",
                key="guidance_text_input",
                height=160,
            )
        else:
            kind_key = "mantra"
            st.markdown("**Mantra targeting (for users):**")

            existing_deities = []
            try:
                approved_existing = load_approved_practices()
                mantra_existing = approved_existing.get("mantra", [])
                deity_set = set()
                for item in mantra_existing:
                    dname = (item.get("deity") or "").strip()
                    if dname:
                        deity_set.add(dname)
                existing_deities = sorted(deity_set, key=str.lower)
            except Exception:
                existing_deities = []

            deity_choice_mode = "Type new name"
            selected_existing_deity = None

            if existing_deities:
                deity_choice_mode = st.radio(
                    "How would you like to choose deity?",
                    ["Use existing deity", "Type new name"],
                    horizontal=True,
                    key="deity_choice_mode",
                )
                if deity_choice_mode == "Use existing deity":
                    selected_existing_deity = st.selectbox(
                        "Existing deities:",
                        existing_deities,
                        key="existing_deity_select",
                    )

            if deity_choice_mode == "Use existing deity" and selected_existing_deity:
                deity_name = selected_existing_deity
                st.info(f"Adding mantra for deity: {deity_name}")
            else:
                deity_name = st.text_input(
                    "Deity / God name for this mantra (e.g. Shiva, Krishna, Devi)",
                    key="guidance_deity_input",
                )

            age_choice = st.radio(
                "Who is this mantra best suited for?",
                ["All ages", "Children", "Adults"],
                horizontal=True,
                key="guidance_age_group_choice",
            )
            if age_choice == "Children":
                age_group_code = "child"
            elif age_choice == "Adults":
                age_group_code = "adult"
            else:
                age_group_code = "both"

            level_number = st.number_input(
                "Suggested mantra level (1 = beginner, 2 = deeper, etc.)",
                min_value=1,
                max_value=20,
                value=1,
                step=1,
                key="guidance_level_number",
            )

            st.markdown("**Mantra text (exactly as chanted):**")
            mantra_lines = st.text_area(
                "Mantra lines (line breaks will be preserved exactly for users):",
                key="mantra_text_input",
                height=120,
            )

            mantra_desc = st.text_area(
                "Description / meaning / practice guidance (optional but recommended):",
                key="mantra_desc_input",
                height=160,
            )

        uploaded_audio = st.file_uploader(
            "Optional: upload an audio file for this guidance",
            type=["mp3", "wav", "m4a", "ogg"],
            key="guidance_audio_uploader",
        )

        uploaded_image = st.file_uploader(
            "Optional: upload an image for this guidance",
            type=["png", "jpg", "jpeg", "webp"],
            key="guidance_image_uploader",
        )

        uploaded_video = st.file_uploader(
            "Optional: upload a video for this guidance",
            type=["mp4", "mov", "m4v", "webm", "mpeg4"],
            key="guidance_video_uploader",
        )

        if st.button("Save guidance", key="guidance_save_button"):
            if kind_key == "meditation":
                if not guidance_text.strip():
                    st.error("Please write a short guidance passage before saving (especially if you include media).")
                    st.stop()
            else:
                if not mantra_lines.strip():
                    st.error("Please enter the mantra text (even if the description is short).")
                    st.stop()
                if not deity_name.strip():
                    st.error("Please enter a deity / god name for this mantra.")
                    st.stop()

            saved_audio_path = None
            original_name = None
            if uploaded_audio is not None:
                try:
                    original_name = uploaded_audio.name
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = original_name.replace(" ", "_")
                    filename = f"{kind_key}_{ts}_{safe_name}"
                    saved_audio_path = os.path.join(GUIDANCE_AUDIO_DIR, filename)
                    with open(saved_audio_path, "wb") as f:
                        f.write(uploaded_audio.getbuffer())
                except Exception as e:
                    st.error(f"Could not save audio file: {e}")
                    saved_audio_path = None

            saved_image_path = None
            image_original_name = None
            if uploaded_image is not None:
                try:
                    image_original_name = uploaded_image.name
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name_img = image_original_name.replace(" ", "_")
                    img_filename = f"{kind_key}_img_{ts}_{safe_name_img}"
                    saved_image_path = os.path.join(GUIDANCE_MEDIA_DIR, img_filename)
                    with open(saved_image_path, "wb") as f:
                        f.write(uploaded_image.getbuffer())
                except Exception as e:
                    st.error(f"Could not save image file: {e}")
                    saved_image_path = None

            saved_video_path = None
            video_original_name = None
            if uploaded_video is not None:
                try:
                    video_original_name = uploaded_video.name
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name_vid = video_original_name.replace(" ", "_")
                    vid_filename = f"{kind_key}_vid_{ts}_{safe_name_vid}"
                    saved_video_path = os.path.join(GUIDANCE_MEDIA_DIR, vid_filename)
                    with open(saved_video_path, "wb") as f:
                        f.write(uploaded_video.getbuffer())
                except Exception as e:
                    st.error(f"Could not save video file: {e}")
                    saved_video_path = None

            approved = load_approved_practices()
            practices_list = approved.get(kind_key) or []

            entry = {"source": "manual-guidance"}

            if kind_key == "meditation":
                entry["text"] = guidance_text.strip()
            else:
                entry["mantra_text"] = mantra_lines.rstrip()
                entry["text"] = mantra_desc.strip()
                entry["deity"] = deity_name.strip()
                entry["age_group"] = age_group_code
                entry["level"] = int(level_number)

            if saved_audio_path:
                entry["audio_path"] = saved_audio_path
                if original_name:
                    entry["audio_original_name"] = original_name

            if saved_image_path:
                entry["image_path"] = saved_image_path
                if image_original_name:
                    entry["image_original_name"] = image_original_name

            if saved_video_path:
                entry["video_path"] = saved_video_path
                if video_original_name:
                    entry["video_original_name"] = video_original_name

            practices_list.append(entry)
            approved[kind_key] = practices_list
            save_approved_practices(approved)

            st.success("Your guidance has been saved and will appear in the journey levels.")
            st.rerun()

        st.markdown("---")
        st.subheader("Existing mantra deities")

        approved_all = load_approved_practices()
        mantra_existing_all = approved_all.get("mantra", []) or []

        deity_map = {}
        for idx, item in enumerate(mantra_existing_all):
            dname = (item.get("deity") or "General").strip()
            if not dname:
                dname = "General"
            deity_map.setdefault(dname, []).append((idx, item))

        if not deity_map:
            st.write("No mantra deities configured yet.")
        else:
            for dname, items in sorted(deity_map.items(), key=lambda x: x[0].lower()):
                with st.expander(f"Deity: {dname} ({len(items)} mantra entries)", expanded=False):
                    for idx, item in items:
                        level = item.get("level")
                        label = f"Level {level}" if level is not None else f"Entry {idx+1}"
                        st.markdown(f"**{label}**")
                        preview = item.get("mantra_text") or item.get("text") or ""
                        if len(preview) > 200:
                            preview = preview[:200] + " ..."
                        st.markdown(
                            f"<div class='source-text'>{preview}</div>",
                            unsafe_allow_html=True,
                        )

    elif admin_view == "Internet search":
        st.subheader("🌐 Mantra & meditation suggestions (admin review)")
        st.write(
            "Use this space to ask the model for **mantras and meditation ideas** for any deity and level. "
            "You remain the final approval before anything reaches the users."
        )

        deity_name = st.text_input(
            "Deity / God name (e.g. Shiva, Krishna, Devi)",
            key="online_deity_name",
        )

        scope_choice = st.radio(
            "What would you like to search for?",
            ["Mantras", "Meditations", "Both"],
            horizontal=True,
            key="online_scope_choice",
        )

        level_choice = st.selectbox(
            "Which level are you focusing on?",
            ["Beginner", "Intermediate", "Deeper"],
            index=0,
            key="online_level_choice",
        )

        if st.button("🌐 Search online suggestions", key="online_search_button"):
            if not deity_name.strip():
                st.error("Please enter a deity / god name first.")
            else:
                with st.spinner("Asking the model for traditional-style suggestions..."):
                    results = fetch_online_practices(
                        deity_name=deity_name,
                        scope=scope_choice,
                        level_label=level_choice,
                    )
                st.session_state["online_search_results"] = results
                if results:
                    st.success(f"Received {len(results)} suggestions. Review them below.")
                else:
                    st.warning("No suggestions were returned. Try adjusting scope or deity name.")

        results = st.session_state.get("online_search_results") or []
        if results:
            st.markdown("### Suggestions")
            add_flags = []

            for idx, p in enumerate(results):
                kind = (p.get("kind") or "").lower()
                kind_label = "MANTRA" if kind == "mantra" else "MEDITATION"
                title = p.get("title") or "Untitled practice"
                deity_p = p.get("deity") or deity_name or ""
                level_p = p.get("level") or level_choice
                mantra_text = p.get("mantra_text") or ""
                instructions = p.get("instructions") or ""
                source_hint = p.get("source_hint") or ""

                header = f"[{kind_label}] {title} — {deity_p} ({level_p})"
                with st.expander(header, expanded=False):
                    if mantra_text:
                        safe_mantra = (
                            mantra_text.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )
                        st.markdown(
                            f"<div class='mantra-box'>{safe_mantra}</div>",
                            unsafe_allow_html=True,
                        )
                    if instructions:
                        safe_instr = (
                            instructions.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )
                        st.markdown("**Guidance / instructions:**")
                        st.markdown(
                            f"<div class='answer-text'>{safe_instr}</div>",
                            unsafe_allow_html=True,
                        )
                    if source_hint:
                        st.markdown(f"_Source hint: {source_hint}_")

                    ck = st.checkbox(
                        "Add this suggestion to practice candidates",
                        key=f"online_add_{idx}",
                    )
                    add_flags.append((idx, ck))

            if add_flags and st.button("💾 Save selected suggestions", key="online_save_suggestions"):
                candidates = load_practice_candidates()
                for idx, is_checked in add_flags:
                    if not is_checked:
                        continue
                    if idx < 0 or idx >= len(results):
                        continue
                    p = results[idx]
                    kind = (p.get("kind") or "mantra").lower()
                    title = p.get("title") or ""
                    deity_p = (p.get("deity") or deity_name or "").strip()
                    level_p = (p.get("level") or level_choice).strip()
                    mantra_text = p.get("mantra_text") or ""
                    instructions = p.get("instructions") or ""
                    source_hint = p.get("source_hint") or "online suggestion"

                    lines = []
                    if title:
                        lines.append(f"{title} ({level_p})")
                    if mantra_text:
                        lines.append(mantra_text)
                    if instructions:
                        lines.append(instructions)
                    if source_hint:
                        lines.append(f"[Source hint: {source_hint}]")
                    combined_text = "\n\n".join(lines)

                    cand = {
                        "kind": kind,
                        "source": f"online:{deity_p or 'unknown'}",
                        "text": combined_text,
                        "approved": False,
                        "deity": deity_p,
                        "level": level_p.lower(),
                    }
                    candidates.append(cand)

                save_practice_candidates(candidates)
                st.success(
                    "Selected suggestions have been stored as practice candidates. "
                    "You can now review and give final approval under 'Approved practices'."
                )
        else:
            st.info("No online suggestions yet. Enter a deity name above and click search.")

    elif admin_view == "Daily reflection":
        st.subheader("🌅 Daily reflection (admin)")
        st.write(
            "Use this page to ask the model for short dharmic reflections connected to a deity, "
            "and choose which line should appear on the home page."
        )

        try:
            with open(DAILY_REFLECTION_FILE, "r", encoding="utf-8") as f:
                overrides = json.load(f)
                if not isinstance(overrides, dict):
                    overrides = {}
        except Exception:
            overrides = {}

        if overrides:
            st.markdown("#### Currently active reflections")
            for key, label in [
                ("both", "All ages"),
                ("adult", "Adults"),
                ("child", "Children"),
            ]:
                txt = overrides.get(key)
                if txt:
                    st.markdown(f"**{label}:**")
                    st.markdown(
                        f"<div class='source-text'>{txt}</div>",
                        unsafe_allow_html=True,
                    )
            st.markdown("---")

        deity_name = st.text_input(
            "Optional deity / god focus for suggestions",
            key="ref_deity_name",
        )

        age_choice = st.radio(
            "Which seekers do you want this reflection for?",
            ["All ages", "Children", "Adults"],
            horizontal=True,
            key="ref_age_choice",
        )
        if age_choice == "Children":
            age_key = "child"
        elif age_choice == "Adults":
            age_key = "adult"
        else:
            age_key = "both"

        if st.button("🔄 Refresh reflection suggestions", key="refresh_reflections_button"):
            hint_deity = deity_name.strip() if deity_name.strip() else ""
            with st.spinner("Gathering fresh reflection suggestions..."):
                results = fetch_online_practices(
                    deity_name=hint_deity,
                    scope="Meditations",
                    level_label="Beginner",
                )
            st.session_state["reflection_suggestions"] = results or []
            if results:
                st.success(f"Received {len(results)} suggestions. Review them below.")
            else:
                st.warning("No suggestions were returned. Try another deity name or try again later.")

        suggestions = st.session_state.get("reflection_suggestions") or []
        if suggestions:
            st.markdown("#### Suggestions")
            for idx, p in enumerate(suggestions):
                text_candidates = [
                    p.get("instructions"),
                    p.get("title"),
                    p.get("mantra_text"),
                ]
                reflection_text = next((t for t in text_candidates if t), "")
                if not reflection_text:
                    continue

                preview = reflection_text
                if len(preview) > 500:
                    preview = preview[:500] + " ..."

                with st.expander(f"Suggestion {idx+1}", expanded=False):
                    st.markdown(
                        f"<div class='answer-text'>{preview}</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button("Use this as today's reflection", key=f"use_reflection_{idx}"):
                        overrides = overrides or {}
                        overrides[age_key] = reflection_text.strip()
                        try:
                            with open(DAILY_REFLECTION_FILE, "w", encoding="utf-8") as f:
                                json.dump(overrides, f, ensure_ascii=False, indent=2)
                            st.success(
                                f"Saved reflection for {age_choice}. It will now appear on the home page "
                                "for that age group (if available)."
                            )
                        except Exception as e:
                            st.error(f"Could not save reflection: {e}")
                        st.rerun()
        else:
            st.info("Click 'Refresh reflection suggestions' to fetch new ideas for today's reflection.")

    elif admin_view == "Feedback collection":
        st.subheader("📝 Feedback collection (from users)")
        st.write(
            "Here you can see feedback that users have submitted from their Feedback tab "
            "so you can improve content and fix issues."
        )

        feedback_items = load_feedback()
        if not feedback_items:
            st.info("No feedback has been submitted yet.")
        else:
            st.markdown(f"Total feedback items: **{len(feedback_items)}**")
            with st.expander("Show all feedback", expanded=True):
                for i, fb in enumerate(reversed(feedback_items), start=1):
                    username = fb.get("username") or "Unknown user"
                    category = fb.get("category") or "Unspecified"
                    created_at = fb.get("created_at") or "Unknown time"
                    text = fb.get("text") or ""
                    contact = fb.get("contact") or ""

                    st.markdown(f"**#{i} — {username} — {category}**")
                    st.markdown(f"_Submitted at: {created_at}_")
                    if contact:
                        st.markdown(f"_Contact: {contact}_")

                    st.markdown(
                        f"<div class='source-text'>{text}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("---")


# ---------- MAIN USER NAVIGATION ----------
if st.session_state.get("role") == "user":
    main_mode = st.radio(
        "Where would you like to go?",
        [
            "Home",
            "Meditation journey",
            "Mantra chanting journey",
            "My Journey",
            "Feedback",  # NEW
        ],
        horizontal=True,
        key="main_nav_mode",
    )
else:
    main_mode = "Home"

# ---------- USER SAVED STORIES PANEL ----------
if (
    st.session_state.get("role") == "user"
    and st.session_state.get("show_history_panel", False)
    and main_mode == "Home"
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


def get_daily_focus(age_group):
    themes = [
        "Remembering one divine quality again and again.",
        "Bringing kindness into one small action.",
        "Watching the breath for a few quiet moments.",
        "Offering worries into an inner flame of trust.",
        "Seeing every being as carrying a spark of the Divine.",
    ]
    today = datetime.date.today()
    idx = today.toordinal()
    line = themes[idx % len(themes)]
    if age_group == "child":
        child_variants = [
            "Remember one good thing about God again and again today.",
            "Try one extra kind action today.",
            "Close your eyes and feel 5 soft breaths.",
            "Give one worry to God in your heart.",
            "Look at people and think: 'There is a little light inside them.'",
        ]
        line = child_variants[idx % len(child_variants)]
    return line


def get_micro_practice(age_group):
    adult_items = [
        "Before checking your phone in the morning, place your hand on your heart and remember your chosen deity once.",
        "Take 3 conscious breaths before starting any important task today.",
        "When irritation arises, pause for one breath and silently repeat a divine name once.",
        "Before sleep, mentally offer the best and worst moments of your day into a small inner flame.",
        "Choose one action today and consciously dedicate it as a small offering.",
    ]
    child_items = [
        "Say thank you to God once today in your own words.",
        "Take 3 slow breaths and imagine light in your heart.",
        "When you feel angry, count to 5 and think of your favourite form of God.",
        "Before sleep, tell the Divine one thing you liked today.",
        "Share one toy or snack and imagine the Divine smiling.",
    ]
    today = datetime.date.today()
    idx = today.toordinal()
    if age_group == "child":
        return child_items[idx % len(child_items)]
    else:
        return adult_items[idx % len(adult_items)]


# ---------- HOME ----------
if main_mode == "Home":
    def run_question_flow(question_text: str):
        if not question_text:
            return
        st.session_state["messages"].append({"role": "user", "content": question_text})
        passages, metas = retrieve_passages(question_text)
        answer = answer_question(
            question_text,
            passages,
            book_list,
            history_messages=st.session_state["messages"],
            answer_length=st.session_state.get("answer_length", "Medium"),
        )
        books_used = set()
        for m in metas:
            src = m.get("source")
            if src:
                books_used.add(os.path.basename(src))

        image_url = None
        style_used = None
        if st.session_state.get("generate_image"):
            image_url, style_used = generate_styled_image(question_text, answer)

        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": answer,
                "image_url": image_url,
                "style": style_used,
                "passages": passages,
                "metas": metas,
                "books_used": list(books_used),
            }
        )
        st.rerun()

    age_group = st.session_state.get("age_group")
    try:
        daily_line = get_daily_reflection(age_group)
        daily_focus = get_daily_focus(age_group)
        micro_practice = get_micro_practice(age_group)
    except Exception:
        daily_line = None
        daily_focus = None
        micro_practice = None

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

    if st.session_state.get("role") == "user":
        st.markdown("### Navigation")
        st.write(
            "Use the top menu (Home / Meditation journey / Mantra chanting journey / My Journey / Feedback) "
            "to move between sections."
        )
        st.markdown("---")

    if st.session_state.get("role") == "user":
        st.markdown("### How are you feeling today?")
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        with mcol1:
            if st.button("😟 I feel anxious", key="mood_anxious"):
                run_question_flow(
                    "I feel anxious. Please tell me a gentle dharmic story or guidance to calm my mind from the uploaded books."
                )
        with mcol2:
            if st.button("😞 Low energy", key="mood_low_energy"):
                run_question_flow(
                    "My energy is low. From these books, give me a short story or guidance that brings strength and hope."
                )
        with mcol3:
            if st.button("💪 Need courage", key="mood_courage"):
                run_question_flow(
                    "I need courage for a challenge. Tell me a story or teaching about courage from these dharmic books."
                )
        with mcol4:
            if st.button("❤️ More devotion", key="mood_bhakti"):
                run_question_flow(
                    "I want to feel more devotion and love for the Divine. Share a story or guidance about bhakti from these books."
                )

        st.markdown("---")

    for idx, msg in enumerate(st.session_state["messages"]):
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        else:
            with st.chat_message("assistant"):
                st.markdown(
                    f"<div class='answer-text'>{content}</div>",
                    unsafe_allow_html=True,
                )

                books_used = msg.get("books_used", [])
                if books_used:
                    ref_text = ", ".join(sorted(books_used))
                    st.markdown(f"**References (books used):** _{ref_text}_")

                if msg.get("image_url"):
                    st.image(
                        msg["image_url"],
                        caption=f"Illustration (style: {msg.get('style', '').upper()})",
                        use_column_width=True,
                    )

                if msg.get("passages") and msg.get("metas"):
                    st.markdown("**Passages used from your books:**")
                    for i, (p, m) in enumerate(zip(msg["passages"], msg["metas"])):
                        src = m.get("source", "unknown")
                        fname = os.path.basename(src) if src else "unknown"
                        with st.expander(f"Passage {i+1} — Source file: {fname}"):
                            st.markdown(
                                f"<div class='source-text'>{p}</div>",
                                unsafe_allow_html=True,
                            )

                if st.session_state.get("role") == "user":
                    username = get_current_username()
                    if username:
                        fav_button_key = f"save_story_{idx}"
                        if st.button("⭐ Save this story", key=fav_button_key):
                            favs_all = load_favourites()
                            user_favs = favs_all.get(username, [])
                            if not any(
                                f.get("content") == msg["content"]
                                and f.get("books_used") == msg.get("books_used", [])
                                for f in user_favs
                            ):
                                user_favs.append(
                                    {
                                        "content": msg["content"],
                                        "books_used": msg.get("books_used", []),
                                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    }
                                )
                                favs_all[username] = user_favs
                                save_favourites(favs_all)
                                st.success("Story saved to your favourites.")

    user_input = st.chat_input("Ask for a story (e.g. 'Tell me a story about Shiva's compassion')...")

    if user_input:
        st.session_state["messages"].append(
            {"role": "user", "content": user_input}
        )

        passages, metas = retrieve_passages(user_input)

        answer = answer_question(
            user_input,
            passages,
            book_list,
            history_messages=st.session_state["messages"],
            answer_length=st.session_state.get("answer_length", "Medium"),
        )

        books_used = set()
        for m in metas:
            src = m.get("source")
            if src:
                books_used.add(os.path.basename(src))

        image_url = None
        style_used = None
        if st.session_state["generate_image"]:
            image_url, style_used = generate_styled_image(user_input, answer)

        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": answer,
                "image_url": image_url,
                "style": style_used,
                "passages": passages,
                "metas": metas,
                "books_used": list(books_used),
            }
        )

        st.rerun()

# ---------- MEDITATION JOURNEY ----------
elif main_mode == "Meditation journey":
    st.header("🧘 Meditation journey")
    st.markdown(
        "Move step-by-step through simple guided meditations. "
        "Read the guidance, practice quietly, then mark the level as completed."
    )

    if st.session_state.get("role") != "user":
        st.info("Meditation levels are available for logged-in users only.")
    else:
        approved = load_approved_practices()
        med_practices = approved.get("meditation", [])

        profile = st.session_state.get("user_profile") or {}
        med_level = profile.get("meditation_level", 1)

        if not med_practices:
            st.info(
                "No approved meditation practices are available yet. "
                "Ask the admin to approve some meditation passages from the books."
            )
        else:
            max_level = min(20, len(med_practices))
            if med_level > max_level:
                st.success("You have completed all available meditation levels.")
                st.write(f"Current meditation level: {med_level}")
            else:
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

# ---------- MANTRA JOURNEY ----------
elif main_mode == "Mantra chanting journey":
    st.header("📿 Mantra chanting journey")
    st.markdown(
        "Choose a deity, pick a level (beginner, intermediate, deeper), "
        "and explore the mantras available at that level."
    )
    if st.session_state.get("role") != "user":
        st.info("Mantra levels are available for logged-in users only.")
    else:
        approved = load_approved_practices()
        mantra_practices = approved.get("mantra", []) or []

        profile = st.session_state.get("user_profile") or {}
        age_group = st.session_state.get("age_group")

        if not mantra_practices:
            st.info(
                "No approved mantra practices are available yet. "
                "Ask the admin to approve some mantra-related passages from the books or Guidance panel."
            )
        else:
            def _age_allowed(p):
                target = (p.get("age_group") or "both").lower()
                if target not in ("child", "adult", "both"):
                    target = "both"
                if age_group is None:
                    return True
                if target == "both":
                    return True
                return target == age_group

            filtered_all = [p for p in mantra_practices if _age_allowed(p)]

            if not filtered_all:
                st.info(
                    "There are mantra practices, but none are currently marked "
                    f"for your age group ({age_group or 'unspecified'})."
                )
            else:
                deity_names = set()
                for p in filtered_all:
                    d = (p.get("deity") or "General").strip()
                    if not d:
                        d = "General"
                    deity_names.add(d)

                deity_list = sorted(deity_names, key=str.lower)

                selected_deity = st.selectbox(
                    "Choose a deity to chant for:",
                    deity_list,
                    key="mantra_deity_select_user",
                )

                deity_filtered = []
                for p in filtered_all:
                    d = (p.get("deity") or "General").strip()
                    if not d:
                        d = "General"
                    if d == selected_deity:
                        deity_filtered.append(p)

                if not deity_filtered:
                    st.info(f"No mantras found yet for {selected_deity}.")
                else:
                    level_values = set()
                    for p in deity_filtered:
                        try:
                            lvl = int(p.get("level", 1))
                        except Exception:
                            lvl = 1
                        level_values.add(lvl)

                    level_values = sorted(level_values)

                    def _band_for_level(lvl: int) -> str:
                        if lvl <= 3:
                            return "Beginner"
                        elif lvl <= 7:
                            return "Intermediate"
                        else:
                            return "Deeper"

                    level_labels = []
                    label_to_level = {}
                    for lvl in level_values:
                        band = _band_for_level(lvl)
                        label = f"Level {lvl} – {band}"
                        level_labels.append(label)
                        label_to_level[label] = lvl

                    selected_level_label = st.radio(
                        "Choose your level:",
                        level_labels,
                        horizontal=True,
                        key="mantra_level_choice_user",
                    )

                    selected_level = label_to_level[selected_level_label]

                    level_filtered = []
                    for p in deity_filtered:
                        try:
                            lvl_val = int(p.get("level", 1))
                        except Exception:
                            lvl_val = 1
                        if lvl_val == selected_level:
                            level_filtered.append(p)

                    if not level_filtered:
                        st.info(
                            f"No mantras found for {selected_deity} at level {selected_level}. "
                            "Ask the admin to approve or create some."
                        )
                    else:
                        st.markdown(
                            f"### {selected_deity} — Level {selected_level} mantras ({_band_for_level(selected_level)})"
                        )
                        # Progress summary for this deity and level
                        profile_saved = st.session_state.get("user_profile") or {}
                        saved_mantras = profile_saved.get("saved_mantras", [])
                        explored_count = 0
                        for sm in saved_mantras:
                            try:
                                sm_level = int(sm.get("level", 0))
                            except Exception:
                                sm_level = 0
                            if sm.get("deity") == selected_deity and sm_level == selected_level:
                                explored_count += 1
                        total_count = len(level_filtered)
                        st.markdown(
                            f"_You have saved {explored_count} of {total_count} mantras at this level._"
                        )
                        for idx, p in enumerate(level_filtered, start=1):
                            raw_mantra = p.get("mantra_text") or p.get("text") or ""
                            desc_text = p.get("text") or ""
                            src = p.get("source") or "manual-guidance"

                            st.markdown(f"#### Mantra {idx}")
                            st.markdown(f"_Source: {os.path.basename(src)}_")

                            st.markdown(
                                render_mantra_html(raw_mantra),
                                unsafe_allow_html=True,
                            )

                            if desc_text:
                                st.markdown("**Meaning / practice guidance:**")
                                st.markdown(
                                    render_answer_html(desc_text),
                                    unsafe_allow_html=True,
                                )

                            audio_path = p.get("audio_path")
                            if audio_path and os.path.exists(audio_path):
                                st.markdown("**Audio:**")
                                st.audio(audio_path)

                            image_path = p.get("image_path")
                            if image_path and os.path.exists(image_path):
                                st.markdown("**Image:**")
                                st.image(image_path, use_column_width=True)

                            video_path = p.get("video_path")
                            if video_path and os.path.exists(video_path):
                                st.markdown("**Video:**")
                                st.video(video_path)

                            username = get_current_username()
                            if username:
                                save_key = f"save_mantra_{selected_deity}_{selected_level}_{idx}"
                                if st.button("💾 Save this mantra to My Journey", key=save_key):
                                    profile = st.session_state.get("user_profile") or {}
                                    saved_list = profile.get("saved_mantras", [])

                                    saved_list.append(
                                        {
                                            "username": username,
                                            "deity": selected_deity,
                                            "level": selected_level,
                                            "age_group": age_group,
                                            "mantra_text": raw_mantra,
                                            "description": desc_text,
                                            "audio_path": audio_path,
                                            "image_path": image_path,
                                            "video_path": video_path,
                                            "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        }
                                    )

                                    profile["saved_mantras"] = saved_list
                                    st.session_state["user_profile"] = profile

                                    users = load_users()
                                    uname = profile.get("username") or username
                                    if uname:
                                        users[uname] = profile
                                        save_users(users)

                                    st.success("Mantra saved to your journey.")

# ---------- MY JOURNEY ----------
elif main_mode == "My Journey":
    st.header("🧭 My Journey")
    st.markdown(
        "See an overview of your meditation levels, saved mantras, and favourite stories."
    )
    if st.session_state.get("role") != "user":
        st.info("Your journey view is available for logged-in users only.")
    else:
        profile = st.session_state.get("user_profile") or {}
        username = profile.get("username")
        age_group = st.session_state.get("age_group")

        # Saved mantras (from Mantra journey)
        saved_mantras = profile.get("saved_mantras", [])

        if saved_mantras:
            st.markdown("### 📿 Saved mantras (your mantra reflections)")
            for i, m in enumerate(reversed(saved_mantras), start=1):
                title = f"Mantra {i}"
                deity = m.get("deity")
                level = m.get("level")
                saved_at = m.get("saved_at")

                meta_bits = []
                if deity:
                    meta_bits.append(f"Deity: {deity}")
                if level:
                    meta_bits.append(f"Level {level}")
                if saved_at:
                    meta_bits.append(f"Saved at {saved_at}")
                if meta_bits:
                    title += " — " + " | ".join(meta_bits)

                st.markdown(f"**{title}**")

                raw_text = m.get("mantra_text") or ""
                safe_block = render_mantra_html(raw_text)
                st.markdown(safe_block, unsafe_allow_html=True)

                desc = m.get("description")
                if desc:
                    st.markdown("**Notes / meaning:**")
                    st.markdown(
                        render_answer_html(desc),
                        unsafe_allow_html=True,
                    )

                audio_path = m.get("audio_path")
                if audio_path and os.path.exists(audio_path):
                    st.markdown("**Audio:**")
                    st.audio(audio_path)

                image_path = m.get("image_path")
                if image_path and os.path.exists(image_path):
                    st.markdown("**Image:**")
                    st.image(image_path, use_column_width=True)

                video_path = m.get("video_path")
                if video_path and os.path.exists(video_path):
                    st.markdown("**Video:**")
                    st.video(video_path)

                st.markdown("---")
        else:
            st.info("You have not saved any mantras yet. Go to 'Mantra chanting journey' and tap 'Save this mantra'.")

        st.markdown("### 🛤️ Overall Journey")

        med_refl = profile.get("meditation_reflections") or {}
        mantra_refl = profile.get("mantra_reflections") or {}

        favs_all = load_favourites()
        user_favs = favs_all.get(username, []) if username else []
        saved_story_count = len(user_favs)

        med_level_done = len(med_refl) if med_refl else 0
        mantra_levels_done = len(mantra_refl) if mantra_refl else 0

        badges = []
        if med_level_done >= 1:
            badges.append("🧘 Started meditation journey")
        if med_level_done >= 3:
            badges.append("🌿 3+ meditation reflections")
        if mantra_levels_done >= 3:
            badges.append("📿 3+ mantra reflections")
        if saved_story_count >= 5:
            badges.append("⭐ 5+ stories saved")
        if saved_story_count >= 10:
            badges.append("🌟 Story lover (10+ saved stories)")

        st.subheader("📊 Sadhana overview")
        st.write(f"Meditations completed (with reflections): **{med_level_done}**")
        st.write(f"Mantras explored (with reflections): **{mantra_levels_done}**")
        st.write(f"Stories saved: **{saved_story_count}**")

        if badges:
            st.markdown("#### 🌼 Blessing milestones")
            for b in badges:
                st.write("- " + b)

        st.markdown("---")

        st.subheader("🕰️ Journey timeline")

        timeline_entries = []

        for lvl_str, text in med_refl.items():
            timeline_entries.append({
                "when": None,
                "label": f"Meditation level {lvl_str} reflection",
                "type": "meditation",
            })

        for key, text in mantra_refl.items():
            timeline_entries.append({
                "when": None,
                "label": f"Mantra reflection – {key}",
                "type": "mantra",
            })

        for item in user_favs:
            ts = item.get("timestamp")
            label = "Saved a story"
            if ts:
                label = f"Saved a story ({ts})"
            timeline_entries.append({
                "when": ts,
                "label": label,
                "type": "story",
            })

        def _sort_key(e):
            return e["when"] or ""
        timeline_entries = sorted(timeline_entries, key=_sort_key)

        if not timeline_entries:
            st.write("Your journey timeline will grow as you meditate, chant, and save stories.")
        else:
            for e in timeline_entries:
                bullet = "•"
                if e["type"] == "meditation":
                    bullet = "🧘"
                elif e["type"] == "mantra":
                    bullet = "📿"
                elif e["type"] == "story":
                    bullet = "⭐"
                if e["when"]:
                    st.write(f"{bullet} {e['label']}")
                else:
                    st.write(f"{bullet} {e['label']}")

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🧘 Meditation reflections")
            if not med_refl:
                st.write("No meditation reflections saved yet.")
            else:
                for lvl_str in sorted(med_refl.keys(), key=lambda x: int(x)):
                    st.markdown(f"**Level {lvl_str}**")
                    st.markdown(
                        f"<div class='source-text'>{med_refl[lvl_str]}</div>",
                        unsafe_allow_html=True,
                    )

        with col2:
            st.subheader("📿 Mantra reflections")
            if not mantra_refl:
                st.write("No mantra reflections saved yet.")
            else:
                for key in sorted(mantra_refl.keys()):
                    label = key
                    st.markdown(f"**{label}**")
                    st.markdown(
                        f"<div class='source-text'>{mantra_refl[key]}</div>",
                        unsafe_allow_html=True,
                    )
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
                items = load_feedback()
                items.append(
                    {
                        "username": get_current_username() or "unknown",
                        "category": feedback_category,
                        "text": feedback_text.strip(),
                        "contact": contact_info.strip(),
                        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                )
                save_feedback(items)

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
