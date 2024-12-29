import argparse
import logging
from dotenv import load_dotenv
import streamlit as st

from token_world.llm.xplore.admin import admin_panel
from token_world.llm.xplore.characters import character_editor
from token_world.llm.xplore.chat import draw_chat_input, draw_conversation
from token_world.llm.xplore.db import (
    initialize_db,
    session_scope,
)
from token_world.llm.xplore.goals import goal_editor
from token_world.llm.xplore.summarize_agent import (
    draw_conversation_summary,
)
from token_world.llm.xplore.storyline import get_storyline, storyline_form


def parse_args():
    parser = argparse.ArgumentParser(description="Streamlit app for managing message trees.")
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    st.set_page_config(page_title="AI Chat App", page_icon="🤖")
    args = parse_args()

    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Initialize database
    initialize_db()

    st.title("🤖 AI Chat App")

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

    if not get_storyline():
        st.error("Please enter a storyline to get started.")
        return

    draw_conversation()
    draw_chat_input()


if __name__ == "__main__":
    main()
