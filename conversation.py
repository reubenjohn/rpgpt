import logging
from typing import List, NamedTuple, Optional

import streamlit as st
from token_world.llm.xplore.db import (
    MessageModel,
    SummaryModel,
)


class SummaryConversation(NamedTuple):
    latest_summary: Optional[SummaryModel]
    messages_to_summarize: List[MessageModel]
    new_messages: List[MessageModel]

    def is_summary_required(self) -> bool:
        return bool(self.messages_to_summarize)


class CurrentMessages(NamedTuple):
    ai: Optional[MessageModel]
    user: MessageModel


def get_current_messages(summary: SummaryConversation) -> Optional[CurrentMessages]:
    if len(summary.new_messages) == 1:
        ai_message, user_message = None, summary.new_messages[0]
    elif len(summary.new_messages) == 2:
        ai_message, user_message = summary.new_messages
    else:
        st.error("Expected one or two new messages.")
        return None

    logging.info(
        f"Current messages {len(summary.new_messages)} unsummarized messages: "
        f"{ai_message.content_dict['role'] if ai_message else None}, "
        f"{user_message.content_dict['role'] if user_message else None}"
    )

    if ai_message:
        ai_msg = ai_message.content_dict
        if ai_msg["role"] != "assistant":
            st.error(
                "Expected second last message to be an assistant message, but was:"
                f" {ai_msg['role']}."
            )
            return None
    else:
        ai_msg = None
    user_msg = user_message.content_dict
    if user_msg["role"] != "user":
        st.error("Expected last message to be a user message.")
        return None

    return CurrentMessages(ai_message, user_message)
