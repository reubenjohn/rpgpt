import argparse
import logging
from dotenv import load_dotenv
import streamlit as st

from token_world.llm.xplore.chat import draw_chat_input, draw_conversation
from token_world.llm.xplore.db import (
    initialize_db,
)
from token_world.llm.xplore.session_state import has_active_storyline
from token_world.llm.xplore.sidebar import draw_sidebar
from token_world.llm.xplore.storyline import get_active_storyline_description


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

    st.title("🤖 RPGPT")

    draw_sidebar()

    if not has_active_storyline():
        st.error("Please select a storyline to get started.")
        return
    if not get_active_storyline_description():
        st.error("Please enter a storyline to get started.")
        return

    draw_conversation()
    draw_chat_input()


if __name__ == "__main__":
    main()
