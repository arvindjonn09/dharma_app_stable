import os
import streamlit as st

from database import (
    list_book_names,
    load_practice_candidates,
    save_practice_candidates,
    load_approved_practices,
    save_approved_practices,
)
from admin_tools import scan_practice_candidates_from_chroma


def render_admin_practices():
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
                            key="mantra_level_{idx}",
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
        kind_filter = None

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
