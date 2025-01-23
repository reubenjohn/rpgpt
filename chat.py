import logging
from typing import Optional
import streamlit as st

from token_world.llm.xplore.character_agent import generate_character_response
from token_world.llm.xplore.db import (
    MessageModel,
    SummaryModel,
    add_message_to_db,
    session_scope,
)
from token_world.llm.xplore.goal_agent import show_goal_management
from token_world.llm.xplore.image import draw_image_prompt
from token_world.llm.xplore.milestone_agent import show_milestone_management
from token_world.llm.xplore.session_state import get_active_storyline
from token_world.llm.xplore.summarize_agent import (
    draw_conversation_summary,
)


def draw_conversation():
    st.header("💬 Chat")
    with session_scope() as session:
        messages = (
            session.query(MessageModel)
            .where(MessageModel.storyline_name == get_active_storyline())
            .order_by(MessageModel.id)
            .all()
        )
        for message in messages:
            msg = message.content_dict
            with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                if msg["role"] != "assistant":
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.write(message.id)
                    with col2:
                        if st.button("🗑️", key=f"delete_{message.id}"):
                            logging.info(f"Deleting message {message.id}")
                            session.query(MessageModel).where(
                                MessageModel.storyline_name == get_active_storyline()
                            ).where(MessageModel.id >= message.id).delete()
                            session.query(SummaryModel).where(
                                SummaryModel.storyline_name == get_active_storyline()
                            ).where(
                                SummaryModel.summary_until_id >= message.id
                            ).delete()
                            session.commit()
                            st.rerun()
                            return
                    st.markdown(msg["content"])
                else:
                    draw_assistant_message(message, session)


def draw_chat_input():
    # Capture user input
    if prompt := st.chat_input("Type your message here..."):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add user message to chat history
        user_message = {"role": "user", "content": prompt}
        with session_scope() as session:
            add_message_to_db(user_message, session)

        with session_scope() as session:
            with st.chat_message("assistant"):
                draw_assistant_message(None, session)
                st.rerun()


def draw_assistant_message(existing_message: Optional[MessageModel], session):
    message_id = existing_message.id if existing_message else "draft"
    col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
    with col1:
        st.write(message_id)
    with col2:
        regenerate = st.button("🔃 Regenerate", key=f"regenerate_{message_id}")

    conversation = draw_conversation_summary(session)
    if not conversation:
        st.error("Summary required...")
        st.rerun()
        return

    with col3:
        if st.button("🖼️ Image Prompt", key=f"image_{message_id}"):
            draw_image_prompt(conversation)

    with col4:
        if existing_message and st.button("🗑️", key=f"delete_{message_id}"):
            logging.info(f"Deleting message {existing_message.id}")
            session.query(MessageModel).where(
                MessageModel.storyline_name == get_active_storyline()
            ).filter(MessageModel.id >= existing_message.id).delete()
            session.commit()
            st.rerun()
            return

    if existing_message and not regenerate:
        st.markdown(existing_message.content_dict["content"])
        return

    if existing_message:
        session.query(MessageModel).where(
            MessageModel.storyline_name == get_active_storyline()
        ).where(MessageModel.id >= existing_message.id).delete()
        session.query(SummaryModel).where(
            SummaryModel.storyline_name == get_active_storyline()
        ).where(SummaryModel.summary_until_id >= existing_message.id).delete()
        session.commit()

    with st.spinner("Managing milestones..."):
        show_milestone_management()
    with st.spinner("Managing goals..."):
        show_goal_management()
    response = generate_character_response(conversation)
    response_text = str(st.write_stream(response))
    if not existing_message:
        with st.spinner("Generating response..."):
            logging.debug(f"AI response: {response_text}")
            ai_message = {"role": "assistant", "content": response_text}
            existing_message = add_message_to_db(ai_message, session)
    else:
        with st.spinner("Regenerating response..."):
            msg = existing_message.content_dict
            msg["content"] = response_text
            add_message_to_db(msg, session)
    session.commit()
    st.rerun()
