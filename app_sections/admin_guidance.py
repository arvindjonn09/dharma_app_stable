import os
import datetime
import streamlit as st

from database import load_approved_practices, save_approved_practices
from admin_tools import fetch_online_practices
from ui import render_source_html


def render_admin_guidance(GUIDANCE_AUDIO_DIR, GUIDANCE_MEDIA_DIR):
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

        level_number = st.selectbox(
            "Mantras level (1 to 5)",
            [1, 2, 3, 4, 5],
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
