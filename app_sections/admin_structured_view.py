import os
import streamlit as st

from database import (
    add_mantra,
    update_structured_mantra,
    delete_structured_mantra,
    reorder_mantras_for_level,
    get_next_section_and_sort,
    get_deity_list_for_structured_mantras,
    get_mantras_for_level,
)


def render_admin_structured_view():
    st.subheader("Structured deity levels (1–5) with auto-numbered sections")
    st.caption(
        "Deities have levels 1–5; sections auto-increment per level. Users unlock sections in order; next level unlocks only after all sections are completed."
    )

    deities = get_deity_list_for_structured_mantras() or []
    choice_list = deities + ["(Add new deity)"]
    selected = st.selectbox(
        "Choose deity to manage",
        choice_list,
        index=0 if deities else len(choice_list) - 1,
        key="structured_view_deity_select",
    )

    if selected == "(Add new deity)" or not deities:
        deity_name = st.text_input("New deity name", key="structured_view_new_deity")
    else:
        deity_name = selected

    level_choice = st.selectbox(
        "Level (fixed 1–5)",
        [1, 2, 3, 4, 5],
        key="structured_view_level",
    )

    next_section = None
    if deity_name:
        next_section = get_next_section_and_sort(deity_name.strip(), int(level_choice))
        st.text_input(
            "Section (auto-assigned)",
            value=str(next_section),
            disabled=True,
            key="structured_view_auto_section",
        )

    title = st.text_input("Title", key="structured_view_title")
    content = st.text_area("Mantra text (exactly as chanted)", key="structured_view_content", height=140)
    desc = st.text_area(
        "Description / meaning / practice guidance (optional)",
        key="structured_view_desc",
        height=120,
    )

    uploaded_audio = st.file_uploader(
        "Optional: upload an audio file",
        type=["mp3", "wav", "m4a", "ogg"],
        key="structured_view_audio",
    )
    uploaded_image = st.file_uploader(
        "Optional: upload an image",
        type=["png", "jpg", "jpeg", "webp"],
        key="structured_view_image",
    )
    uploaded_video = st.file_uploader(
        "Optional: upload a video",
        type=["mp4", "mov", "m4v", "webm", "mpeg4"],
        key="structured_view_video",
    )

    if st.button("➕ Add mantra/section", key="structured_view_add"):
        if not deity_name or not deity_name.strip():
            st.error("Please enter/select a deity.")
        elif not content.strip():
            st.error("Please enter mantra content.")
        else:
            full_content = content.strip() + (f"\n\n{desc.strip()}" if desc.strip() else "")
            extra_paths = {}
            try:
                import datetime
                GUIDANCE_AUDIO_DIR = "guidance_audio"
                GUIDANCE_MEDIA_DIR = "guidance_media"
                os.makedirs(GUIDANCE_AUDIO_DIR, exist_ok=True)
                os.makedirs(GUIDANCE_MEDIA_DIR, exist_ok=True)

                if uploaded_audio is not None:
                    original_name = uploaded_audio.name
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = original_name.replace(" ", "_")
                    audio_path = os.path.join(GUIDANCE_AUDIO_DIR, f"struct_audio_{ts}_{safe_name}")
                    with open(audio_path, "wb") as f:
                        f.write(uploaded_audio.getbuffer())
                    extra_paths["audio_path"] = audio_path
                    extra_paths["audio_original_name"] = original_name

                if uploaded_image is not None:
                    original_name = uploaded_image.name
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = original_name.replace(" ", "_")
                    image_path = os.path.join(GUIDANCE_MEDIA_DIR, f"struct_img_{ts}_{safe_name}")
                    with open(image_path, "wb") as f:
                        f.write(uploaded_image.getbuffer())
                    extra_paths["image_path"] = image_path
                    extra_paths["image_original_name"] = original_name

                if uploaded_video is not None:
                    original_name = uploaded_video.name
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = original_name.replace(" ", "_")
                    video_path = os.path.join(GUIDANCE_MEDIA_DIR, f"struct_vid_{ts}_{safe_name}")
                    with open(video_path, "wb") as f:
                        f.write(uploaded_video.getbuffer())
                    extra_paths["video_path"] = video_path
                    extra_paths["video_original_name"] = original_name
            except Exception:
                extra_paths = {}

            added = add_mantra(
                deity_name.strip(),
                int(level_choice),
                title.strip(),
                full_content,
            )
            if added:
                # Persist media paths if present
                if extra_paths:
                    from database import update_structured_mantra
                    # Append media paths to content as metadata (lightweight approach)
                    content_with_paths = added.get("content") or full_content
                    meta_lines = []
                    if extra_paths.get("audio_path"):
                        meta_lines.append(f"[audio]: {extra_paths['audio_path']}")
                    if extra_paths.get("image_path"):
                        meta_lines.append(f"[image]: {extra_paths['image_path']}")
                    if extra_paths.get("video_path"):
                        meta_lines.append(f"[video]: {extra_paths['video_path']}")
                    if meta_lines:
                        content_with_paths += "\n\n" + "\n".join(meta_lines)
                        update_structured_mantra(added["id"], title.strip(), content_with_paths)

                st.success(
                    f"Added for {deity_name} / Level {level_choice} as Section {added['section_number']}."
                )
                st.rerun()
            else:
                st.error("Could not add mantra. Please try again.")

    st.markdown("---")
    st.markdown("### Existing mantra deities")
    if not deities:
        st.info("No structured mantras yet. Add one above to get started.")
        return

    # View/edit per level
    view_deity = st.selectbox(
        "View/edit deity",
        sorted(deities, key=str.lower),
        key="structured_view_deity_view",
    )
    view_level = st.selectbox(
        "View/edit level",
        [1, 2, 3, 4, 5],
        key="structured_view_level_view",
    )

    mantras = get_mantras_for_level(view_deity, view_level)
    if not mantras:
        st.info("No sections yet in this deity/level.")
    else:
        for m in mantras:
            section_num = m.get("section_number")
            title_label = m.get("title") or "Untitled"
            with st.expander(f"Section {section_num} — {title_label}", expanded=False):
                raw_content = m.get("content") or ""

                def _split_content_and_media(text: str):
                    lines = text.splitlines()
                    media = {"audio": [], "image": [], "video": []}
                    body_lines = []
                    for ln in lines:
                        lower = ln.lower().strip()
                        if lower.startswith("[audio]:"):
                            media["audio"].append(ln.split(":", 1)[1].strip())
                        elif lower.startswith("[image]:"):
                            media["image"].append(ln.split(":", 1)[1].strip())
                        elif lower.startswith("[video]:"):
                            media["video"].append(ln.split(":", 1)[1].strip())
                        else:
                            body_lines.append(ln)
                    return "\n".join(body_lines).strip(), media

                body_text, media = _split_content_and_media(raw_content)

                new_title = st.text_input(
                    "Title",
                    value=m.get("title") or "",
                    key=f"edit_title_{m['id']}",
                )
                new_content = st.text_area(
                    "Mantra text (exactly as chanted) + notes",
                    value=body_text,
                    key=f"edit_content_{m['id']}",
                    height=160,
                )

                # Show attached media if present
                if media["audio"] or media["image"] or media["video"]:
                    st.markdown("**Attached media:**")
                    for ap in media["audio"]:
                        if ap and os.path.exists(ap):
                            st.audio(ap)
                        else:
                            st.caption(f"Audio: {ap}")
                    for ip in media["image"]:
                        if ip and os.path.exists(ip):
                            st.image(ip, use_column_width=True)
                        else:
                            st.caption(f"Image: {ip}")
                    for vp in media["video"]:
                        if vp and os.path.exists(vp):
                            st.video(vp)
                        else:
                            st.caption(f"Video: {vp}")

                if st.button("Save updates", key=f"save_m_{m['id']}"):
                    # Preserve existing media markers
                    meta_lines = []
                    for ap in media["audio"]:
                        meta_lines.append(f"[audio]: {ap}")
                    for ip in media["image"]:
                        meta_lines.append(f"[image]: {ip}")
                    for vp in media["video"]:
                        meta_lines.append(f"[video]: {vp}")
                    combined = new_content.strip()
                    if meta_lines:
                        combined += "\n\n" + "\n".join(meta_lines)
                    update_structured_mantra(m["id"], new_title.strip(), combined)
                    st.success("Updated.")
                    st.rerun()

                if st.button("🗑️ Delete this section", key=f"delete_m_{m['id']}"):
                    delete_structured_mantra(m["id"])
                    # Renumber remaining sections in this level
                    remaining = get_mantras_for_level(view_deity, view_level)
                    ordered_ids = [x["id"] for x in remaining]
                    reorder_mantras_for_level(view_deity, view_level, ordered_ids)
                    st.warning("Section deleted.")
                    st.rerun()
