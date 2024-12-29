import streamlit as st


def has_active_storyline() -> bool:
    return "active_storyline" in st.session_state and st.session_state.active_storyline


def get_active_storyline() -> str:
    storyline_name = st.session_state.get("active_storyline", None)
    if not storyline_name:
        raise ValueError("No active storyline found.")
    return storyline_name
