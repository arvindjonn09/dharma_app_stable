import datetime


def bootstrap_session_state(
    st,
    load_sessions,
    save_sessions,
    load_users,
    SESSION_TTL_MINUTES,
):
    """Initialize session defaults and attempt auto-restore from query token."""
    if "role" not in st.session_state:
        st.session_state["role"] = "guest"
    if "user_name" not in st.session_state:
        st.session_state["user_name"] = None
    if "age_group" not in st.session_state:
        st.session_state["age_group"] = None
    if "user_profile" not in st.session_state:
        st.session_state["user_profile"] = {}

    if "show_history_panel" not in st.session_state:
        st.session_state["show_history_panel"] = False
    if "session_token" not in st.session_state:
        st.session_state["session_token"] = None
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "answer_length" not in st.session_state:
        st.session_state["answer_length"] = "Medium"
    if "generate_image" not in st.session_state:
        st.session_state["generate_image"] = False
    if "online_search_results" not in st.session_state:
        st.session_state["online_search_results"] = []
    if "reflection_suggestions" not in st.session_state:
        st.session_state["reflection_suggestions"] = []

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
                                try:
                                    current_year = datetime.datetime.now().year
                                    age = current_year - year
                                    age_group = "adult" if age >= 22 else "child"
                                except Exception:
                                    age_group = None
                            st.session_state["role"] = "user"
                            st.session_state["user_name"] = profile.get("first_name") or username_from_sess
                            st.session_state["age_group"] = age_group
                            st.session_state["user_profile"] = profile
                            st.session_state["session_token"] = token

    try:
        # Soft reminder about session expiry after 30 minutes
        sess_token = st.session_state.get("session_token")
        if sess_token:
            sessions = load_sessions()
            sess = sessions.get(sess_token)
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
