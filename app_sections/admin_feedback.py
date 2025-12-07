import streamlit as st


def render_admin_feedback(load_feedback_func, FEEDBACK_FILE):
    st.subheader("📝 Feedback collection (from users)")
    st.write(
        "Here you can see feedback that users have submitted from their Feedback tab "
        "so you can improve content and fix issues."
    )

    feedback_items = load_feedback_func(FEEDBACK_FILE)
    if not feedback_items:
        st.info("No feedback has been submitted yet.")
    else:
        st.markdown(f"Total feedback items: **{len(feedback_items)}**")
        with st.expander("Show all feedback", expanded=True):
            for i, fb in enumerate(reversed(feedback_items), start=1):
                username = fb.get("username") or "Unknown user"
                category = fb.get("category") or "Unspecified"
                created_at = fb.get("created_at") or "Unknown time"
                text = fb.get("text") or ""
                contact = fb.get("contact") or ""

                st.markdown(f"**#{i} — {username} — {category}**")
                st.markdown(f"_Submitted at: {created_at}_")
                if contact:
                    st.markdown(f"_Contact: {contact}_")

                st.markdown(
                    f"<div class='source-text'>{text}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("---")
