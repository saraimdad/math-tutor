from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import streamlit as st

from src.tutor import Tutor
from src.video import create_video


def render_math(text: str) -> None:
    """Render common LaTeX delimiters in Streamlit."""
    text = text.replace(r"\[", "$$").replace(r"\]", "$$")
    text = text.replace(r"\(", "$").replace(r"\)", "$")
    st.markdown(text)


st.set_page_config(page_title="Math Tutor", page_icon="🧮")
st.title("🧮 Math Tutor")
st.caption("Upload a math problem, get an explanation, and generate a video.")

api_key = os.getenv("OPENAI_API_KEY")

uploaded_file = st.file_uploader("Upload a picture", type=["png", "jpg", "jpeg", "webp"])

if "explanation" not in st.session_state:
    st.session_state.explanation = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "video_path" not in st.session_state:
    st.session_state.video_path = ""

if uploaded_file:
    st.image(uploaded_file, caption="Your math problem", width=450)

if st.button("Explain this problem", type="primary", disabled=not uploaded_file or not api_key):
    tutor = Tutor(api_key)
    with st.spinner("Reading and explaining the problem..."):
        try:
            st.session_state.explanation = tutor.explain_image(
                uploaded_file.getvalue(),
                uploaded_file.type or "image/png",
            )
            st.session_state.messages = []
            st.session_state.video_path = ""
        except Exception as error:
            st.error(f"Could not explain the image: {error}")

if st.session_state.explanation:
    st.subheader("Explanation")
    render_math(st.session_state.explanation)

    st.divider()
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            render_math(message["content"])

    if question := st.chat_input("What would you like explained differently?"):
        st.session_state.video_path = ""
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = Tutor(api_key).follow_up(
                        st.session_state.explanation,
                        st.session_state.messages,
                        question,
                    )
                    render_math(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as error:
                    st.error(f"Could not answer: {error}")

    if st.button("🎬 Generate video"):
        tutor = Tutor(api_key)
        conversation = "\n\n".join(
            f"{message['role'].title()}: {message['content']}"
            for message in st.session_state.messages
        )
        lesson_context = (
            f"Latest corrections and follow-up discussion:\n{conversation}\n\n"
            "Use the original explanation only for details that were not corrected:\n"
            f"{st.session_state.explanation}"
        )
        with st.spinner("Writing, narrating, and rendering your lesson..."):
            try:
                scenes = tutor.make_video_plan(lesson_context)
                path = Path(f"runtime/videos/math-lesson-{uuid4().hex[:8]}.mp4")
                st.session_state.video_path = str(create_video(tutor, scenes, path))
            except Exception as error:
                st.error(f"Could not generate the video: {error}")

    if st.session_state.video_path:
        st.video(st.session_state.video_path)
        with open(st.session_state.video_path, "rb") as video_file:
            st.download_button("Download video", video_file, file_name="math-lesson.mp4")
