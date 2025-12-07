import json
import streamlit as st

from admin_tools import fetch_online_practices


def render_admin_reflection(DAILY_REFLECTION_FILE):
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
