import os
import streamlit as st

from database import load_favourites
from ui import render_mantra_html, render_answer_html


def render_my_journey():
    st.header("🧭 My Journey")
    st.markdown(
        "See an overview of your meditation levels, saved mantras, and favourite stories."
    )
    if st.session_state.get("role") != "user":
        st.info("Your journey view is available for logged-in users only.")
        return

    profile = st.session_state.get("user_profile") or {}
    username = profile.get("username")
    age_group = st.session_state.get("age_group")

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
    st.write(f"Meditation reflections saved: **{med_level_done}**")
    st.write(f"Mantra reflections saved: **{mantra_levels_done}**")
    st.write(f"Saved stories count: **{saved_story_count}**")

    if badges:
        st.markdown("#### 🌼 Blessing milestones")
        for b in badges:
            st.write("- " + b)

    st.markdown("---")

    st.subheader("🕰️ Journey timeline")

    timeline_entries = []

    for lvl_str, text in med_refl.items():
        timeline_entries.append(
            {
                "when": None,
                "label": f"Meditation level {lvl_str} reflection",
                "type": "meditation",
            }
        )

    for key, text in mantra_refl.items():
        timeline_entries.append(
            {
                "when": None,
                "label": f"Mantra reflection – {key}",
                "type": "mantra",
            }
        )

    for item in user_favs:
        ts = item.get("timestamp")
        label = "Saved a story"
        if ts:
            label = f"Saved a story ({ts})"
        timeline_entries.append(
            {
                "when": ts,
                "label": label,
                "type": "story",
            }
        )

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

    st.markdown("### 📌 Age group")  # or show
    st.write(f"Current age group mode: {age_group or 'unspecified'}")
