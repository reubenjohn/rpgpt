import json
import logging
from typing import Iterator, Optional

import streamlit as st
from swarm import Agent  # type: ignore[import]
from token_world.llm.stream_processing import MessageStream, ToolStream, parse_streaming_response
from token_world.llm.xplore.conversation import get_current_messages
from token_world.llm.xplore.db import AgentGoalModel, session_scope
from token_world.llm.xplore.goals import (
    get_active_goals_markdown,
    mark_goal_completed,
    random_goal_completion_output,
)
from token_world.llm.xplore.llm import handle_base_model_arg, llm_client
from token_world.llm.xplore.session_state import get_active_storyline
from token_world.llm.xplore.storyline import get_active_milestone_markdown
from token_world.llm.xplore.summarize_agent import (
    SummaryConversation,
    draw_conversation_summary,
)


# Define initial system prompt for storyline
SYSTEM_PROMPT = (
    "You are an intelligent goal managing agent in an NSWF sexualized roleplaying game."
    "You manage the goals of the main AI in the game. "
    "You will be provided with a summary of the conversation between the user and the AI character "
    "so far, followed by the most recent messages. "
    "You will then be asked to perform various tasks involving managing the goals. "
)


def handle_goal_completion(response_text: str):
    """Parse the response text for any goal completion commands and mark the goals as completed."""
    # Regex pattern to match goal completion commands
    goal_part = response_text.rsplit("GOAL CLASSIFICATIONS:", 1)[-1].strip()
    logging.info(f"Goal part to parse classifications from: {goal_part}")
    completion_classifications = json.loads(goal_part)
    for goal_name, completion_status in completion_classifications.items():
        if completion_status == "INCOMPLETE":
            continue
        if mark_goal_completed(goal_name):
            st.success(f"Goal '{goal_name}' marked as completed.")
            logging.info(f"Goal '{goal_name}' marked as completed.")
        else:
            st.warning(f"Goal '{goal_name}' not found.")
            logging.warning(f"Goal '{goal_name}' not found.")


def handle_goal_creation(response_text: str):
    """Parse the response text for any goal completion commands and mark the goals as completed."""
    # Regex pattern to match goal completion commands
    goal_part = response_text.rsplit("NEW GOALS:", 1)[-1].strip()
    goal_part = goal_part.rsplit("{", 1)[-1].strip()
    goal_part = goal_part.rsplit("}", 1)[0].strip()
    goal_part = "{" + goal_part + "}"
    logging.info(f"Goal part to parse goal creation from: {goal_part}")
    goal_creation = json.loads(goal_part)
    for goal_name, goal_description in goal_creation.items():
        if not goal_name or not goal_description:
            st.error(f"Goal name or description are empty: {goal_name=}, {goal_description=}.")
        with session_scope() as session:
            if (
                session.query(AgentGoalModel)
                .where(AgentGoalModel.storyline_name == get_active_storyline())
                .where(AgentGoalModel.name == goal_name)
                .count()
                > 0
            ):
                st.error(f"Goal '{goal_name}' already exists.")
                logging.warning(f"Goal '{goal_name}' already exists.")
                continue
            session.add(
                AgentGoalModel(
                    storyline_name=get_active_storyline(),
                    name=goal_name,
                    description=goal_description,
                    completed=False,
                    persistence="Medium",
                )
            )
            session.commit()
            st.success(f"Goal '{goal_name}' added.")
            logging.info(f"Goal '{goal_name}' added.")


def generate_completed_goals(
    storyline: str, summary: str, ai_prompt: str, user_prompt: str, model: Optional[str] = None
) -> Iterator[str]:
    model = handle_base_model_arg(model)
    try:
        if summary:
            summary_prompt = f"""Let me first give you a summary of the conversation so far:
## Summary
{summary}

"""
        else:
            summary_prompt = ""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""{summary_prompt}Here are the most recent messages:
## Recent Messages
---
AI: {ai_prompt}
---
User: {user_prompt}
---

Finally, here are the current goals of the AI character:
## Goals (alphabetical order)
{get_active_goals_markdown(exclude_forever=True)}

Given these goals, can you determine if the most recent messages of the AI satisfy any of the goals?
Think step-by-step showing your thought process, but don't overcomplicate things,
 keep the reasoning simple and concise (1-3 sentences), and then provide your answer.
Be conservative and look for clear evidence from the conversation
 (and quote it while outputting your internal reasoning) before marking a goal as COMPLETE.

Your answer must be in the format:

## Internal Goal Completion Classification Reasoning

### Step 1: Understand the conversation so far
<...your reasoning here...>

### Step 2: Classify 'goal name 1' as completed or not
<...your reasoning here... (let's assume you conclude it is INCOMPLETE)>
Hence, I classify this goal 'goal name 1' as INCOMPLETE.)

### Step 3: Classify 'goal name 2' as completed or not
<...your reasoning here... (let's assume you conclude it is COMPLETE)>
Hence, I classify this goal 'goal name 2' as COMPLETE.
...

GOAL CLASSIFICATIONS: {{"goal name 1": "INCOMPLETE", "goal name 2": "COMPLETE", ...}}

Notice that that 'GOAL CLASSIFICATIONS:' is case sensitive,
 and the goals classifications are in valid JSON.
ALWAYS OUTPUT 'GOAL CLASSIFICATIONS:' FOLLOWED BY THIS JSON OBJECT AT THE END.

For example:
---
{random_goal_completion_output(storyline)}
""",
            },
        ]
        logging.info(f"Generating response for {messages[-1]} messages")

        agent = Agent(
            name="Goal Completion Classifier",
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


def generate_new_goals(
    storyline: str, summary: str, ai_prompt: str, user_prompt: str, model: Optional[str] = None
) -> Iterator[str]:
    model = handle_base_model_arg(model)
    try:
        if summary:
            summary_prompt = f"""Let me start by giving you a summary of the conversation so far:

## Summary
{summary}

"""
        else:
            summary_prompt = ""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Can you help me decide if any new goals need to be created
 for the AI in the game? And only if yes, what should they be?

{summary_prompt}Here are the most recent messages:
## Recent Messages
---
AI: {ai_prompt}
---
User: {user_prompt}
---

The currently active milestone in the storyline is:
{get_active_milestone_markdown()}

And here are the active goals of the AI character:
{get_active_goals_markdown()}

Given the currently active milestone, the existing incomplete goals
 and the latest developments in the conversation,
 can you suggest if any new goals that the AI character should to pursue?
Or, if no new goals are required, provide your reasoning.
A general rule of thumb is to have 1-3 goals at a time. No more, no less.
A goal is something that the AI character should strive to achieve over multiple turns.
Don't suggest a goal that can be achieved in one turn.
Think step-by-step showing your thought process, but don't overcomplicate things,
 keep the reasoning simple and concise, and then provide your answer.
Your answer must be in the format:

## Internal Goal Creation Reasoning

### Step 1: Understand the conversation so far
<...your reasoning here...>

### Step 2: Decide if it any new goal needs to be created
<...your reasoning here... (let's assume you suggest a new goal)>
Hence, I suggest the new goal 'goal name 1'.

### Step 3: <... repeat for other goals...>


...

NEW GOALS: {{"goal name 1": "description of goal 1", "goal name 2": "description of goal 2", ...}}

Alternatively, if you decide that no new goals are required, you can output:

## Internal Goal Creation Reasoning

### Step 1: Understand the conversation so far
<...your reasoning here...>

### Step 2: Decide if it any new goal needs to be created
<...your reasoning here... (let's assume you decide no new goals are required)>
Hence, I suggest no new goals are required.

NEW GOALS: {{}}

---
Notice that 'NEW GOALS:' is case sensitive,
    and the new goals are in valid JSON.
ALWAYS OUTPUT 'NEW GOALS:' FOLLOWED BY THIS JSON OBJECT AT THE END.

For example:
---
{random_goal_completion_output(storyline)}
""",
            },
        ]
        logging.info(f"Generating response for {messages[-1]} messages")

        agent = Agent(
            name="Goal Creator",
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


def show_goal_completion_classification(storyline: str, summary: SummaryConversation):
    with st.spinner("Detecting completed goals..."):
        logging.info("Detecting completed goals...")
        with session_scope() as session:
            n_incomplete_goals = (
                session.query(AgentGoalModel)
                .where(AgentGoalModel.storyline_name == storyline)
                .where(AgentGoalModel.completed.is_(False))
                .count()
            )
            if n_incomplete_goals == 0:
                st.write("All goals completed.")
                return

        current_messages = get_current_messages(summary)
        if not current_messages or current_messages.ai is None:
            st.warning("No messages to process.")
            return
        stream = generate_completed_goals(
            storyline,
            str(summary.latest_summary.content) if summary.latest_summary else "",
            current_messages.ai.content_val if current_messages.ai else "",
            current_messages.user.content_val,
        )
        text_response = str(st.write_stream(stream))
        logging.debug(f"Goal completion classification response: {text_response}")
        handle_goal_completion(text_response)
    st.write("Goal completion classification complete.")


def show_goal_creation(storyline: str, summary: SummaryConversation):
    with st.spinner("Determining if new goals need to be created..."):
        logging.info("Detecting completed goals...")
        with session_scope() as session:
            n_incomplete_goals = (
                session.query(AgentGoalModel)
                .where(AgentGoalModel.storyline_name == storyline)
                .where(AgentGoalModel.completed.is_(False))
                .count()
            )
            if n_incomplete_goals > 5:
                st.warning("Too many incomplete goals. Skipping goal creation.")
                return

        current_messages = get_current_messages(summary)
        if not current_messages or current_messages.ai is None:
            st.warning("No messages to process.")
            return
        stream = generate_new_goals(
            storyline,
            str(summary.latest_summary.content) if summary.latest_summary else "",
            current_messages.ai.content_val if current_messages.ai else "",
            current_messages.user.content_val,
        )
        text_response = str(st.write_stream(stream))
        logging.debug(f"Goal creation response: {text_response}")
        handle_goal_creation(text_response)
    st.write("Goal creation complete.")


def show_goal_management():
    logging.info("Showing goal management...")
    with session_scope() as session:
        with st.expander("📜 Conversation Summary", expanded=True):
            summary = draw_conversation_summary(session, max_messages=2)
            if not summary or summary.is_summary_required():
                st.error("Summary required...")
                st.rerun()
                return

        logging.info("Summarization for goals complete...")
        with st.expander("🎯 Goal Management", expanded=True):
            show_goal_completion_classification(summary)
            st.divider()
            show_goal_creation(summary)
