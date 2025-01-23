import logging
from typing import Iterator, Optional
from swarm import Agent  # type: ignore[import]
import streamlit as st
from token_world.llm.stream_processing import (
    MessageStream,
    ToolStream,
    parse_streaming_response,
)
from token_world.llm.xplore.conversation import SummaryConversation
from token_world.llm.xplore.llm import handle_base_model_arg, llm_client


def draw_image_prompt(conversation: SummaryConversation, model: Optional[str] = None):
    logging.info("Generating image prompt...")
    with st.spinner("Generating image prompt..."):
        image_prompt = generate_image_prompt(conversation, model)
        prompt = st.write_stream(image_prompt)
        st.code(prompt, language="text", wrap_lines=True)


def generate_image_prompt(
    conversation: SummaryConversation, model: Optional[str] = None
) -> Iterator[str]:
    model = handle_base_model_arg(model)
    agent = Agent(
        name="Image Prompter",
        model=model,
        instructions="""You are a helpful assistant who is an expert in providing concise
image generation prompts based on the provided information.
The prompt must not contain full sentences or paragraphs,
but rather a comma separated list of keywords.
Note that larger more complex prompts result in unwanted artefacts in the image.
So use unambiguous keywords that clearly and vividly capture the scene.
Pro tips: Using keywords like artistic, vivid, model, beutiful, etc. can help.
Some keywords may describe the scene, physical traits, and visual actions.""",
        stream=True,
    )

    summary_text = ""
    if conversation.latest_summary:
        summary_text = f"""Let me first give you a summary of the conversation so far.
Note that this is only for context and may not be relevant
for the image prompt you need to generate.

Summary:
{conversation.latest_summary.content}

"""

    messages = [
        {
            "role": "user",
            "content": f"""{summary_text}The actual message for which
you need to generate an image prompt is:
{conversation.new_messages[-1].content_dict["content"]}

---

Based on the above message, please generate a concise image prompt
consisting of comma separated keywords clearly following the prescribed instructions.
Make sure to include keywords for the scene, physical descriptions of the character,
character poses/actions, etc. Complex keywords are not recommended.
A good prompt will have between 5-10 keywords.
Examples of GOOD keywords are: ninja, sword, tent, etc
Examples of BAD keywords are: anticipation, jealousy, grace, etc since they are abstract.
Also avoid names since they don't have any visual representation.""",
        }
    ]
    chunks = llm_client().run(agent, messages, stream=True)

    for stream in parse_streaming_response(chunks):
        if isinstance(stream, MessageStream):
            for chunk in stream.content_stream:
                yield chunk
        elif isinstance(stream, ToolStream):
            logging.debug(f"Tool Use: {stream}")
