import os
import subprocess
import streamlit as st

from database import list_book_names, load_unreadable


def render_admin_books(BOOKS_DIR):
    st.subheader("📚 Books & indexing")

    st.write(
        "Upload new PDF/EPUB books here. They will be stored only on the server "
        "(not in GitHub) and used after you reindex."
    )

    uploaded_books = st.file_uploader(
        "Upload one or more books (PDF / EPUB)",
        type=["pdf", "epub"],
        accept_multiple_files=True,
        key="admin_books_uploader",
    )

    if uploaded_books:
        if st.button("📥 Save uploaded books", key="save_uploaded_books"):
            saved_files = []
            for f in uploaded_books:
                original_name = os.path.basename(f.name)
                if not original_name:
                    continue

                base, ext = os.path.splitext(original_name)
                if not ext:
                    ext = ".pdf"

                dest_path = os.path.join(BOOKS_DIR, original_name)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(BOOKS_DIR, f"{base}_{counter}{ext}")
                    counter += 1

                with open(dest_path, "wb") as out:
                    out.write(f.getbuffer())

                saved_files.append(os.path.basename(dest_path))

            if saved_files:
                st.success(f"Saved {len(saved_files)} book(s): " + ", ".join(saved_files))
                st.info("Now click **'🔄 Reindex books now'** below so the app can read them.")
            else:
                st.warning("No valid files were saved. Please try again.")

    st.markdown("---")

    if st.button("🔄 Reindex books now", key="admin_reindex"):
        with st.spinner("Reindexing books from the 'books' folder..."):
            try:
                result = subprocess.run(
                    ["python3", "prepare_data.py"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                st.success("Reindexing finished successfully.")

                if result.stdout:
                    st.text_area("Reindex log (stdout)", result.stdout, height=200)
                if result.stderr:
                    st.text_area("Reindex log (stderr)", result.stderr, height=200)

                st.cache_data.clear()
                st.cache_resource.clear()
            except subprocess.CalledProcessError as e:
                st.error("Reindexing failed. See log below.")
                err_text = e.stderr or str(e)
                st.text_area("Error log", err_text, height=200)

    st.markdown("---")

    unreadable = load_unreadable()
    if unreadable:
        st.warning("Some books could not be read completely (scanned or problematic):")
        for path, reason in unreadable.items():
            st.write(f"- `{os.path.basename(path)}` — {reason}")

    book_list = list_book_names()
    if book_list:
        with st.expander("Books currently available"):
            for b in book_list:
                st.write("•", b)
    else:
        st.info("No books found yet in 'books/' folder.")
