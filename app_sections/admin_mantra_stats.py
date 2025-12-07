import streamlit as st

from database import get_top_completed_mantras


def render_admin_mantra_stats():
    st.subheader("Most listened/completed structured mantras")
    top_items = get_top_completed_mantras(limit=15)
    if not top_items:
        st.info("No completion data yet. Users need to finish structured mantras for stats to appear.")
        return
    for item in top_items:
        deity = item.get("deity_id") or "Unknown deity"
        lvl = item.get("level_number")
        sec = item.get("section_number")
        title = item.get("title") or "Untitled"
        cnt = item.get("completed_count", 0)
        st.markdown(f"**{deity} — Level {lvl}, Section {sec}: {title}**")
        st.caption(f"Completed {cnt} time(s)")
        st.markdown("---")
