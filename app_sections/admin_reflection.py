import json
import os
import time
import streamlit as st

from admin_tools import fetch_online_practices
from rag import client as openai_client


def _generate_deity_image(deity_name: str):
    """Create a high-detail ACK-style illustration for the given deity."""
    name_clean = (deity_name or "").strip()
    if not name_clean:
        return None

    prompt = f"""
Create a 4K, hyper-detailed yet respectful illustration of {name_clean} in the spirit of classic
Amar Chitra Katha artwork.

Rules:
- Indian facial features, traditional attire, dharmic symbols
- Warm, realistic lighting and intricate textures
- Rich background elements (temple, nature, ornaments) but no modern objects
- Composition should feel devotional, serene, and story-like
- Avoid gore, violence, and caricature
"""

    try:
        res = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            n=1,
        )
        return res.data[0].url
    except Exception as e:
        st.info(f"Could not generate image for {name_clean}: {e}")
        return None


def _save_uploaded_media(uploaded_file, media_dir: str):
    """Persist uploaded image/gif and return its path."""
    if uploaded_file is None:
        return None

    os.makedirs(media_dir, exist_ok=True)
    base = uploaded_file.name.replace(" ", "_")
    ts = int(time.time())
    filename = f"reflection_{ts}_{base}"
    dest_path = os.path.join(media_dir, filename)
    try:
        with open(dest_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return dest_path
    except Exception as e:
        st.error(f"Could not save uploaded file: {e}")
        return None


def render_admin_reflection(DAILY_REFLECTION_FILE, MEDIA_DIR):
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
            entry = overrides.get(key)
            if not entry:
                continue
            if isinstance(entry, dict):
                txt = entry.get("text")
                img = entry.get("image_url")
            else:
                txt = entry
                img = None
            st.markdown(f"**{label}:**")
            if img:
                st.image(img, use_column_width=True, caption=f"{label} reflection image")
            if txt:
                st.markdown(
                    f"<div class='source-text'>{txt}</div>",
                    unsafe_allow_html=True,
                )
        st.markdown("---")

    deity_name = st.text_input(
        "Optional deity / god focus for suggestions",
        key="ref_deity_name",
    )
    if st.session_state.get("deity_image_url") and not deity_name.strip():
        # Clear cached image if the deity field is emptied.
        st.session_state.pop("deity_image_url", None)
        st.session_state.pop("deity_image_name", None)

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

    img_mode = st.radio(
        "Choose image source",
        ["AI-generated", "Upload image / GIF"],
        horizontal=True,
        key="reflection_image_mode",
    )

    uploaded_media = None
    if img_mode == "Upload image / GIF":
        uploaded_media = st.file_uploader(
            "Upload an image or GIF for this reflection",
            type=["png", "jpg", "jpeg", "gif"],
            key="reflection_media_uploader",
        )
        if uploaded_media is not None and st.button("Use uploaded file", key="use_uploaded_reflection_media"):
            saved_path = _save_uploaded_media(uploaded_media, MEDIA_DIR)
            if saved_path:
                st.session_state["deity_image_url"] = saved_path
                st.session_state["deity_image_name"] = uploaded_media.name
                st.success("Uploaded media saved for this reflection.")

    if st.button("🔄 Refresh reflection suggestions", key="refresh_reflections_button"):
        hint_deity = deity_name.strip() if deity_name.strip() else ""
        if img_mode == "AI-generated" and hint_deity:
            with st.spinner(f"Rendering 4K ACK-style illustration for {hint_deity}..."):
                image_url = _generate_deity_image(hint_deity)
                if image_url:
                    st.session_state["deity_image_url"] = image_url
                    st.session_state["deity_image_name"] = hint_deity
                else:
                    st.session_state.pop("deity_image_url", None)
                    st.session_state.pop("deity_image_name", None)
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

    if st.session_state.get("deity_image_url"):
        st.markdown("#### Deity image preview")
        caption_name = st.session_state.get("deity_image_name") or "Deity"
        st.image(
            st.session_state["deity_image_url"],
            caption=f"{caption_name} — reflection image",
            use_column_width=True,
        )

    # Manual save block so admin can pair any text with the current image/upload.
    current_entry = overrides.get(age_key) if isinstance(overrides, dict) else None
    if isinstance(current_entry, dict):
        current_text = current_entry.get("text", "")
    elif isinstance(current_entry, str):
        current_text = current_entry
    else:
        current_text = ""

    manual_text = st.text_area(
        f"Reflection text to save for {age_choice}",
        value=current_text,
        key=f"manual_reflection_text_{age_key}",
        height=120,
    )
    if st.button("Save reflection text + current image", key="save_manual_reflection"):
        overrides = overrides or {}
        entry = {
            "text": manual_text.strip(),
            "image_url": st.session_state.get("deity_image_url"),
        }
        overrides[age_key] = entry
        try:
            with open(DAILY_REFLECTION_FILE, "w", encoding="utf-8") as f:
                json.dump(overrides, f, ensure_ascii=False, indent=2)
            st.success(
                f"Saved reflection and image for {age_choice}. It will now appear on the home page "
                "for that audience."
            )
        except Exception as e:
            st.error(f"Could not save reflection: {e}")
        st.rerun()

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
                    entry = {
                        "text": reflection_text.strip(),
                        "image_url": st.session_state.get("deity_image_url"),
                    }
                    overrides[age_key] = entry
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
