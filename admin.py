import os
from dotenv import find_dotenv, load_dotenv
import pandas as pd
import streamlit as st

from token_world.llm.xplore.db import (
    MessageModel,
    SummaryModel,
    get_all_tables,
    session_scope,
)
from token_world.llm.xplore.session_state import get_active_storyline


@st.cache_data
def environment_variables():
    # Replace with your data loading logic
    return dict(os.environ)


def admin_panel():
    col1, col2, col3, _ = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("💀 Wipe DB"):
            os.remove("chat_history.db")
            st.rerun()

    with col2:
        if st.button("🧹 Clear Conversation"):
            st.session_state["messages"] = []
            with session_scope() as session:
                session.query(MessageModel).where(
                    MessageModel.storyline_name == get_active_storyline()
                ).delete()
                session.commit()
                st.rerun()

    with col3:
        if st.button("🧹 Clear Summaries"):
            with session_scope() as session:
                session.query(SummaryModel).where(
                    SummaryModel.storyline_name == get_active_storyline()
                ).delete()
                session.commit()
                st.rerun()

    st.subheader("Environment Variables")
    if st.button("🔁 Refresh"):
        st.write(f"Found dotenv file: {find_dotenv()}")
        load_dotenv(override=True)

    st.dataframe(os.environ.items(), width=1000, height=200)

    tables = get_all_tables()
    st.dataframe(pd.DataFrame(tables, columns=["Table Name", "SQL"]))
