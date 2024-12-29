import logging
from typing import Iterator, Optional
import streamlit as st
from swarm import Agent  # type: ignore[import]

from token_world.llm.stream_processing import MessageStream, ToolStream, parse_streaming_response
from token_world.llm.xplore.db import (
    PropertyModel,
    get_character1_name,
    session_scope,
)
from token_world.llm.xplore.goals import get_active_goals_markdown
from token_world.llm.xplore.llm import handle_base_model_arg, llm_client
from token_world.llm.xplore.summarize_agent import SummaryConversation


# Define initial system prompt for storyline
def get_system_prompt(character_name) -> str:
    with session_scope() as session:
        storyline = session.query(PropertyModel).filter(PropertyModel.key == "storyline").first()
        if not storyline:
            raise ValueError("Storyline not found in the database")
        return storyline.value.replace("{character_name}", character_name)


def generate_character_response(
    summarized_conversation: SummaryConversation, model: Optional[str] = None
) -> Iterator[str]:
    model = handle_base_model_arg(model)
    try:
        character1_name = get_character1_name()
        if summarized_conversation.is_summary_required():
            st.write("Summary required...")
            st.rerun()
            return

        messages = summarized_conversation.new_messages
        logging.info(f"Generating response for {len(messages)} messages")
        # Include system prompt and conversation history
        all_messages = []
        msgs = [message.content_dict for message in messages]

        latest_summary = summarized_conversation.latest_summary
        if latest_summary is not None:
            all_messages.append(
                {
                    "role": "system",
                    "content": f"""Let me first give you a summary of the conversation so far:
    {latest_summary.content}""",
                }
            )
        all_messages.extend(msgs[:-1])
        all_messages.append(
            {
                "role": "system",
                "content": f"""{character1_name}'s internal goals are:
{get_active_goals_markdown()}
Note: The persistence of a goal indicates how persistently the AI character should pursue that goal.
The persistence levels are: Low, Medium, High, Forever.
A goal marked as 'Forever' should be pursued indefinitely.
A goal marked as 'Low' for example, may not be pursued with the utmost urgency.

{character1_name} must ensure that the responses align with these goals.
A response can vary widely in size but the upper limit is usually a few paragraphs
 unless it is obvious it should be longer.""",
            }
        )
        all_messages.append(msgs[-1])

        agent = Agent(
            name=character1_name,
            model=model,
            instructions=get_system_prompt(character1_name),
            stream=True,
        )

        chunks = llm_client().run(agent, all_messages, stream=True)
        elements = 0
        for stream in parse_streaming_response(chunks):
            logging.debug(f"stream: {type(stream)}")
            if isinstance(stream, MessageStream):
                for chunk in stream.content_stream:
                    yield chunk
                    logging.debug(f"chunk: {chunk}")
                    elements += 1
            elif isinstance(stream, ToolStream):
                logging.debug(f"Tool Use: {stream}")
        logging.info(f"Response generation complete with {elements} elements")
    except Exception as e:
        logging.error(f"Error generating response: {e}", exc_info=True)
        yield f"An error '{e}' occurred while generating the response. Please try again."