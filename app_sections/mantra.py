import os
import streamlit as st
import datetime
from database import (
    load_approved_practices,
    get_deity_list_for_structured_mantras,
    get_next_uncompleted_mantra,
    mark_mantra_completed,
    get_level_progress_summary,
)
from auth import save_users, load_users
from helpers import get_current_username
from ui import render_mantra_html, render_answer_html


def render_mantra_journey():
    st.header("📿 Mantra chanting journey")
    st.markdown(
        "Choose a deity, pick a level (beginner, intermediate, deeper), "
        "and explore the mantras available at that level."
    )
    if st.session_state.get("role") != "user":
        st.info("Mantra levels are available for logged-in users only.")
        return

    approved = load_approved_practices()
    mantra_practices = approved.get("mantra", []) or []

    profile = st.session_state.get("user_profile") or {}
    age_group = st.session_state.get("age_group")
    username = get_current_username()

    # Structured mantra unlock flow (Levels 1-5, sections)
    st.markdown("### 🔓 Structured deity levels (1–5)")
    structured_deities = get_deity_list_for_structured_mantras()
    if not structured_deities:
        st.info("No structured mantras have been created yet. Ask the admin to add some under Guidance.")
    elif not username:
        st.info("Log in to start the structured mantra journey.")
    else:
        chosen_structured_deity = st.selectbox(
            "Choose a deity (structured journey):",
            structured_deities,
            key="structured_deity_user",
        )
        next_mantra, stats = get_next_uncompleted_mantra(username, chosen_structured_deity)
        if not next_mantra:
            st.success(f"All sections completed for {chosen_structured_deity}.")
            prog = get_level_progress_summary(username, chosen_structured_deity)
            if prog:
                for lvl in sorted(prog.keys()):
                    done, total = prog[lvl]
                    st.write(f"Level {lvl}: {done}/{total} completed")
        else:
            lvl = next_mantra["level_number"]
            sec = next_mantra["section_number"]
            st.markdown(f"**Next unlocked section:** {chosen_structured_deity} — Level {lvl}, Section {sec}")
            if next_mantra.get("title"):
                st.markdown(f"**Title:** {next_mantra['title']}")
            st.markdown(
                render_mantra_html(next_mantra.get("content") or ""),
                unsafe_allow_html=True,
            )
            reflection = st.text_area(
                "How did this mantra make you feel?",
                key=f"structured_reflection_{chosen_structured_deity}_{lvl}_{sec}",
            )
            if st.button("Mark as done and unlock next", key=f"structured_complete_{chosen_structured_deity}_{lvl}_{sec}"):
                saved = mark_mantra_completed(username, next_mantra["id"], reflection or "")
                if saved:
                    st.success("Saved reflection and unlocked the next section.")
                    st.rerun()
                else:
                    st.info("Already completed. Move on to the next available section.")
        st.markdown("---")

    if not mantra_practices:
        st.info(
            "No approved mantra practices are available yet. "
            "Ask the admin to approve some mantra-related passages from the books or Guidance panel."
        )
        return

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
        return

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
        return

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
        return

    st.markdown(
        f"### {selected_deity} — Level {selected_level} mantras ({_band_for_level(selected_level)})"
    )
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
            feeling = st.text_input(
                "Openly express your feeling and thoughts here (*encrypted)",
                key=f"mantra_feeling_{selected_deity}_{selected_level}_{idx}",
            )
            if st.button("💾 Save this mantra to My Journey", key=save_key):
                if not feeling.strip():
                    st.error("Openly express your feeling and thoughts here (*encrypted).")
                    st.stop()
                profile = st.session_state.get("user_profile") or {}
                saved_list = profile.get("saved_mantras", [])
                already = any(
                    sm.get("mantra_text") == raw_mantra
                    and sm.get("deity") == selected_deity
                    and sm.get("level") == selected_level
                    for sm in saved_list
                )
                if already:
                    st.info("Already saved this mantra.")
                    st.stop()
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
                        "feeling": feeling.strip(),
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
