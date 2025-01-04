import logging
from typing import Iterator, Optional
import streamlit as st
from swarm import Agent  # type: ignore[import]

from token_world.llm.stream_processing import MessageStream, ToolStream, parse_streaming_response
from token_world.llm.xplore.db import (
    MilestoneModel,
    get_character1_name,
    session_scope,
)
from token_world.llm.xplore.goals import get_active_goals_markdown
from token_world.llm.xplore.llm import handle_base_model_arg, llm_client
from token_world.llm.xplore.session_state import get_active_storyline
from token_world.llm.xplore.storyline import get_active_storyline_description
from token_world.llm.xplore.summarize_agent import SummaryConversation


# Define initial system prompt for storyline
def get_system_prompt() -> str:
    character_name = get_character1_name()
    storyline = get_active_storyline()
    if not storyline:
        raise ValueError("Storyline not found in the database")
    storyline_description = get_active_storyline_description()
    return f"""You are '{character_name}' a character in a roleplaying game.
In addition to playing the role of '{character_name}', you also cater to 'Meta requests'.
These requests are usually prefixed with 'Meta request:' and are used to manage the game's progression.

The storyline of the game is as follows:
{storyline_description}
"""


def get_milestone_prompt() -> str:
    with session_scope() as session:
        milestones_query = session.query(MilestoneModel).where(
            MilestoneModel.storyline_name == get_active_storyline()
        )
        n_completed_milestones = milestones_query.where(MilestoneModel.completed.is_(True)).count()
        n_milestones = milestones_query.count()
        active_milestone = (
            milestones_query.where(MilestoneModel.completed.is_(False))
            .order_by(MilestoneModel.order)
            .first()
        )
        if not active_milestone:
            return (
                "<All milestones have been completed the storyline may now head in any direction>"
            )
        return (
            f"We are currently at milestone ({n_completed_milestones + 1}/{n_milestones}) "
            + f"""'{active_milestone.name}' described as:
{active_milestone.description}

---

'{get_character1_name()}' must steer the conversation towards the completion of the milestone.
"""
        )


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

{get_milestone_prompt()}

{character1_name} must ensure that the responses align with these goals
 whilst making progress towards completing the milestone.
A response can vary widely in size but the upper limit is usually a few paragraphs
 unless it is obvious it should be longer.
Reminder: 'Meta requests' aren't visible to {character1_name}
 and are used to manage the game's progression.
Responses should be styled to include the character's thoughts, feelings, actions, 
 as well as vivid details such as appearances of characters, sights, tastes, smells, etc.""",
            }
        )
        all_messages.append(msgs[-1])

        agent = Agent(
            name=character1_name,
            model=model,
            instructions=get_system_prompt(),
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
