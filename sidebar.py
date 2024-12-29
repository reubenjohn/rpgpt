import streamlit as st

from token_world.llm.xplore.admin import admin_panel
from token_world.llm.xplore.characters import character_editor
from token_world.llm.xplore.db import (
    session_scope,
)
from token_world.llm.xplore.goals import goal_editor
from token_world.llm.xplore.summarize_agent import (
    draw_conversation_summary,
)
from token_world.llm.xplore.storyline import storyline_form


def draw_sidebar():
    with st.sidebar:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["📖 Storyline", "🧑 Characters", "🎯 Goals", "📝 Summary", "🔧 Admin"]
        )

        with tab1:
            storyline_form()

        with tab2:
            character_editor()

        with tab3:
            goal_editor()

        with tab4:
            with session_scope() as session:
                draw_conversation_summary(session)

        with tab5:
            admin_panel()
