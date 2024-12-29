import logging
from typing import Iterator, Optional

import streamlit as st
from swarm import Agent  # type: ignore[import]
from token_world.llm.stream_processing import MessageStream, ToolStream, parse_streaming_response
from token_world.llm.xplore.conversation import get_current_messages
from token_world.llm.xplore.db import session_scope
from token_world.llm.xplore.llm import handle_base_model_arg, llm_client
from token_world.llm.xplore.storyline import (
    get_active_milestone,
    get_active_milestone_classification_example,
    get_active_milestone_markdown,
    get_active_storyline_description,
    mark_milestone_completed,
)
from token_world.llm.xplore.summarize_agent import (
    SummaryConversation,
    draw_conversation_summary,
)


# Define initial system prompt for storyline
SYSTEM_PROMPT = (
    "You are an intelligent milestone managing agent in roleplaying game."
    "You manage the milestones of the main AI in the game. "
    "You will be provided with a summary of the conversation between the user and the AI character "
    "so far, followed by the most recent messages. "
    "You will then be asked to perform various tasks involving managing the milestones. "
)


def handle_milestone_completion(milestone_name: str, response_text: str):
    completion_status = response_text.rsplit("MILESTONE CLASSIFICATION:", 1)[-1].strip()
    logging.info(f"Milestone classification part to parse: {completion_status}")

    if completion_status == "INCOMPLETE":
        st.info(f"Milestone '{milestone_name}' is incomplete.")
        logging.info(f"Milestone '{milestone_name}' is incomplete.")
    elif completion_status == "COMPLETE":
        if mark_milestone_completed(milestone_name):
            st.success(f"Milestone '{milestone_name}' marked as completed.")
            logging.info(f"Milestone '{milestone_name}' marked as completed.")
        else:
            st.warning(f"Milestone '{milestone_name}' not found.")
            logging.warning(f"Milestone '{milestone_name}' not found.")
    else:
        st.error(
            f"Unknown completion status '{completion_status}' for milestone '{milestone_name}'."
        )
        logging.error(
            f"Unknown completion status '{completion_status}' for milestone '{milestone_name}'."
        )


def generate_milestone_classification(
    summary: str, ai_prompt: str, user_prompt: str, model: Optional[str] = None
) -> Iterator[str]:
    model = handle_base_model_arg(model)
    try:
        summary_prompt = ""
        if summary:
            summary_prompt = f"""Next, let me give you a summary of the conversation so far:
## Summary
{summary}

"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Can you help me classify the current milestone
  as either INCOMPLETE/COMPLETE based on the conversation so far?

Let's me start by giving you some context about the overall storyline of the game:
{get_active_storyline_description()}

{summary_prompt}And here are the most recent messages:
## Recent Messages
---
AI: {ai_prompt}
---
User: {user_prompt}
---

Finally, here is the current milestone of the AI character you need to classify:
{get_active_milestone_markdown()}

Given this milestone and the overall storyline,
 can you determine if the most recent messages of the AI satisfy the milestone?
Think step-by-step showing your thought process, but don't overcomplicate things,
    keep the reasoning simple and concise (1-3 sentences), and then provide your answer.
Be conservative and look for clear evidence from the conversation
    (and quote it while outputting your internal reasoning)
    before marking the milestone as COMPLETE.

Your answer must be in the format:

## Internal Milestone Completion Classification Reasoning

### Step 1: Understand the conversation so far
<...your reasoning here...>

### Step 2: Classify the milestone as completed or not
<...your reasoning here... (let's assume you conclude it is INCOMPLETE)>
Hence, I classify this milestone as INCOMPLETE.

MILESTONE CLASSIFICATION: <INCOMPLETE or COMPLETE>

Notice that 'MILESTONE CLASSIFICATION:' is case sensitive,
    and the classification must be either 'INCOMPLETE' or 'COMPLETE'.
ALWAYS OUTPUT 'MILESTONE CLASSIFICATION:' FOLLOWED BY THE CLASSIFICATION.

For example:
---
{get_active_milestone_classification_example()}
""",
            },
        ]
        logging.info(f"Generating response for {messages[-1]} messages")

        agent = Agent(
            name="Milestone Completion Classifier",
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
    except Exception as e:
        st.error(f"Error generating response: {e}.")
        return logging.error(f"Error generating response: {e}", exc_info=True)


def show_milestone_completion_classification(summary: SummaryConversation):
    with st.spinner("Detecting milestone completion..."):
        logging.info("Detecting milestone completion...")
        with session_scope() as session:
            active_milestone = get_active_milestone(session)
            if not active_milestone:
                st.write("All milestones completed.")
                return

            current_messages = get_current_messages(summary)
            if not current_messages or current_messages.ai is None:
                st.warning("No messages to process.")
                return
            stream = generate_milestone_classification(
                str(summary.latest_summary.content) if summary.latest_summary else "",
                current_messages.ai.content_val if current_messages.ai else "",
                current_messages.user.content_val,
            )
            text_response = str(st.write_stream(stream))
            logging.debug(f"Milestone completion classification response: {text_response}")
            handle_milestone_completion(str(active_milestone.name), text_response)
    st.info("Milestone completion classification complete.")


def show_milestone_management():
    logging.info("Showing milestone management...")
    with session_scope() as session:
        with st.expander("📜 Conversation Summary", expanded=True):
            summary = draw_conversation_summary(session, max_messages=2)
            if not summary or summary.is_summary_required():
                st.error("Summary required...")
                st.rerun()
                return

        logging.info("Summarization for milestones complete...")
        with st.expander("🔖 Milestone Management", expanded=True):
            show_milestone_completion_classification(summary)
