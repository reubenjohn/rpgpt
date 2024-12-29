import logging
from time import sleep
from typing import Iterator, Optional

import streamlit as st
from swarm import Agent  # type: ignore[import]
from token_world.llm.stream_processing import MessageStream, ToolStream, parse_streaming_response
from token_world.llm.xplore.conversation import SummaryConversation
from token_world.llm.xplore.db import (
    MessageModel,
    SummaryModel,
)
from token_world.llm.xplore.llm import handle_base_model_arg, llm_client

SYSTEM_PROMPT = "You are a helpful assistant who is an expert and providing detailed summaries of "
"conversations."


def get_summary_conversation(
    session,
    latest_message: Optional[MessageModel] = None,
    max_messages: int = 8,
    min_messages: int = 2,
) -> SummaryConversation:
    new_messages_query = session.query(MessageModel)
    if latest_message:
        new_messages_query.filter(MessageModel.id <= latest_message.id)
    new_messages = new_messages_query.order_by(MessageModel.id.desc()).limit(max_messages).all()
    new_messages = list(reversed(new_messages))
    logging.debug(
        f"Found {len(new_messages)} new messages: {[message.id for message in new_messages]}"
    )
    if len(new_messages) < max_messages:
        return SummaryConversation(None, [], new_messages)

    latest_summary = (
        session.query(SummaryModel)
        .where(SummaryModel.summary_until_id < new_messages[-min_messages].id)
        .order_by(SummaryModel.summary_until_id.desc())
        .first()
    )
    latest_summary_id = latest_summary.summary_until_id if latest_summary else 0
    logging.debug(f"Found latest summary ID: {latest_summary_id}")
    messages_to_summarize = (
        session.query(MessageModel)
        .filter(
            MessageModel.id > latest_summary_id, MessageModel.id < new_messages[-min_messages].id
        )
        .all()
    )
    logging.info(
        f"Found {len(messages_to_summarize)} messages to summarize: "
        f"{[message.id for message in messages_to_summarize]}"
    )
    return SummaryConversation(latest_summary, messages_to_summarize, new_messages)


def generate_summary(
    conversation: SummaryConversation, model: Optional[str] = None
) -> Iterator[str]:
    model = handle_base_model_arg(model)
    prev_summary_prompt = (
        f"""Let me first give you a summary of the conversation so far:
## Summary
{conversation.latest_summary.content}

"""
        if conversation.latest_summary
        else ""
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""The following conversation is between a user and an AI in a
roleplaying game.
{prev_summary_prompt}
Here are the most recent messages between the user and the AI:
## Recent Messages
{[message.content for message in conversation.messages_to_summarize]}

Can you please provide a detailed summary of the conversation so far?
1. Make sure you don't miss out any important details.
2. Do not output anything other than the summary.
3. The conversations can vary in length, so don't worry if you summary is as small as 1 paragraph,
   or as large as 12 paragraphs long!
   The important point is that you preserve all the important details,
   especially the most recent little details.

SUMMARY:
""",
        },
    ]

    agent = Agent(
        name="Goal Manager",
        model=model,
        instructions=SYSTEM_PROMPT,
        stream=True,
    )

    chunks = llm_client().run(agent, messages, stream=True)
    for chunk in parse_streaming_response(chunks):
        if isinstance(chunk, MessageStream):
            for content in chunk.content_stream:
                yield content
        elif isinstance(chunk, ToolStream):
            logging.info(f"Tool Use: {chunk}")


def draw_conversation_summary(
    session,
    max_messages: int = 8,
    min_messages: int = 2,
) -> Optional[SummaryConversation]:
    try:
        with st.spinner("Summarizing conversation..."):
            conversation = get_summary_conversation(
                session, max_messages=max_messages, min_messages=min_messages
            )
            logging.info(
                f"Conversation has {len(conversation.messages_to_summarize)} to summarize "
                f"{[message.id for message in conversation.messages_to_summarize]} "
                f"and {len(conversation.new_messages)} new messages "
                f"{[message.id for message in conversation.new_messages]}."
            )
            if conversation.is_summary_required():
                messages_to_summarize = conversation.messages_to_summarize
                with st.spinner(
                    f"Summarizing {len(messages_to_summarize)} new messages "
                    f"({messages_to_summarize[0].id}..{messages_to_summarize[-1].id}) ..."
                ):
                    stream = generate_summary(conversation)
                    text_content = st.write_stream(stream)
                    conversation = SummaryModel(
                        summary_until_id=messages_to_summarize[-1].id, content=text_content
                    )
                    session.add(conversation)
                    session.commit()
                    conversation = get_summary_conversation(
                        session,
                        max_messages=max_messages,
                        min_messages=min_messages,
                    )
            elif conversation.latest_summary:
                st.markdown(conversation.latest_summary.content)
            else:
                st.write("No conversation to summarize.")
            return conversation

    except Exception as e:
        st.error(f"An error occurred: {e}")
        logging.error(f"An error occurred: {e}", exc_info=True)
        if st.button("Retry"):
            with st.spinner("Retrying..."):
                sleep(0.5)
            st.rerun()
        return None
