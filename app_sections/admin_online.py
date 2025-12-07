import streamlit as st

from admin_tools import fetch_online_practices
from database import load_practice_candidates, save_practice_candidates


def render_admin_online():
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
