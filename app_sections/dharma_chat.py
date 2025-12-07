import datetime
import os
import streamlit as st

from helpers import get_current_username
from rag import retrieve_passages, answer_question, generate_styled_image
from database import load_favourites, save_favourites


def render_dharma_chat(book_list):
    """Full chat experience moved off Home."""

    def run_question_flow(question_text: str):
        if not question_text:
            return
        st.session_state["messages"].append({"role": "user", "content": question_text})
        passages, metas = retrieve_passages(question_text)
        answer = answer_question(
            question_text,
            passages,
            book_list,
            history_messages=st.session_state["messages"],
            answer_length=st.session_state.get("answer_length", "Medium"),
        )
        books_used = set()
        for m in metas:
            src = m.get("source")
            if src:
                books_used.add(os.path.basename(src))

        image_url = None
        style_used = None
        if st.session_state.get("generate_image"):
            # Use "cartoon" as a nudge toward illustrative output, but the helper defines exact styles
            image_url, style_used = generate_styled_image(question_text, answer)

        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": answer,
                "image_url": image_url,
                "style": style_used,
                "passages": passages,
                "metas": metas,
                "books_used": list(books_used),
            }
        )
        st.rerun()

    st.header("🗣️ Dharma chat")
    st.checkbox(
        "Generate image (realistic animation style)",
        key="generate_image",
        help="Adds a playful, illustrative image that matches the answer.",
    )
    st.write(
        "Ask for stories, guidance, or use quick mood buttons. All conversations and saves stay the same; "
        "they're just moved here from Home."
    )

    if st.session_state.get("role") == "user":
        st.markdown("### How are you feeling today?")
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        with mcol1:
            if st.button("😟 I feel anxious", key="mood_anxious"):
                run_question_flow(
                    "I feel anxious. Please tell me a gentle dharmic story or guidance to calm my mind from the uploaded books."
                )
        with mcol2:
            if st.button("😞 Low energy", key="mood_low_energy"):
                run_question_flow(
                    "My energy is low. From these books, give me a short story or guidance that brings strength and hope."
                )
        with mcol3:
            if st.button("💪 Need courage", key="mood_courage"):
                run_question_flow(
                    "I need courage for a challenge. Tell me a story or teaching about courage from these dharmic books."
                )
        with mcol4:
            if st.button("❤️ More devotion", key="mood_bhakti"):
                run_question_flow(
                    "I want to feel more devotion and love for the Divine. Share a story or guidance about bhakti from these books."
                )

        st.markdown("---")

    for idx, msg in enumerate(st.session_state["messages"]):
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        else:
            with st.chat_message("assistant"):
                st.markdown(
                    f"<div class='answer-text'>{content}</div>",
                    unsafe_allow_html=True,
                )

                books_used = msg.get("books_used", [])
                if books_used:
                    ref_text = ", ".join(sorted(books_used))
                    st.markdown(f"**References (books used):** _{ref_text}_")

                if msg.get("image_url"):
                    st.image(
                        msg["image_url"],
                        caption=f"Illustration (style: {msg.get('style', '').upper()})",
                        use_column_width=True,
                    )

                if msg.get("passages") and msg.get("metas"):
                    st.markdown("**Passages used from your books:**")
                    for i, (p, m) in enumerate(zip(msg["passages"], msg["metas"])):
                        src = m.get("source", "unknown")
                        fname = os.path.basename(src) if src else "unknown"
                        with st.expander(f"Passage {i+1} — Source file: {fname}"):
                            st.markdown(
                                f"<div class='source-text'>{p}</div>",
                                unsafe_allow_html=True,
                            )

                if st.session_state.get("role") == "user":
                    username = get_current_username()
                    if username:
                        fav_button_key = f"save_story_{idx}"
                        if st.button("⭐ Save this story", key=fav_button_key):
                            favs_all = load_favourites()
                            user_favs = favs_all.get(username, [])
                            if not any(
                                f.get("content") == msg["content"]
                                and f.get("books_used") == msg.get("books_used", [])
                                for f in user_favs
                            ):
                                user_favs.append(
                                    {
                                        "content": msg["content"],
                                        "books_used": msg.get("books_used", []),
                                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    }
                                )
                                favs_all[username] = user_favs
                                save_favourites(favs_all)
                                st.success("Story saved to your favourites.")

    user_input = st.chat_input("Ask for a story (e.g. 'Tell me a story about Shiva's compassion')...")

    if user_input:
        st.session_state["messages"].append(
            {"role": "user", "content": user_input}
        )

        passages, metas = retrieve_passages(user_input)

        answer = answer_question(
            user_input,
            passages,
            book_list,
            history_messages=st.session_state["messages"],
            answer_length=st.session_state.get("answer_length", "Medium"),
        )

        books_used = set()
        for m in metas:
            src = m.get("source")
            if src:
                books_used.add(os.path.basename(src))

        image_url = None
        style_used = None
        if st.session_state["generate_image"]:
            image_url, style_used = generate_styled_image(user_input, answer)

        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": answer,
                "image_url": image_url,
                "style": style_used,
                "passages": passages,
                "metas": metas,
                "books_used": list(books_used),
            }
        )

        st.rerun()
