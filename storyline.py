import json
import logging
from typing import Optional
import streamlit as st

from token_world.llm.xplore.db import (
    MilestoneModel,
    PropertyModel,
    StorylineModel,
    get_character1_name,
    session_scope,
)
from token_world.llm.xplore.session_state import get_active_storyline


def get_active_storyline_description() -> Optional[str]:
    with session_scope() as session:
        storyline = (
            session.query(StorylineModel)
            .where(StorylineModel.name == get_active_storyline())
            .first()
        )
        character1_name = get_character1_name()
        if not storyline:
            return "There is no explicit storyline, this game is in unscripted mode."
        return storyline.description.replace("{character_name}", character1_name)


def storyline_form():
    with session_scope() as session:
        with st.form(key="new_storyline"):
            storyline_name = st.text_input("Storyline Name")
            if st.form_submit_button("➕ New Storyline"):
                new_storyline = StorylineModel(name=storyline_name, description="")
                session.add(new_storyline)
                session.commit()
                st.session_state.active_storyline = storyline_name
                st.success("New storyline added!")
                st.rerun()

        storylines = session.query(StorylineModel).all()
        storyline_name = st.selectbox(
            "Select a storyline", [storyline.name for storyline in storylines]
        )
        logging.info(f"Selected storyline: {storyline_name}")
        storyline = (
            session.query(StorylineModel).filter(StorylineModel.name == storyline_name).first()
        )
        if not storyline:
            return
        st.session_state.active_storyline = storyline_name
        storyline_name = storyline.name
        storyline_description = storyline.description
        session.merge(PropertyModel(key="active_storyline", value=storyline_name))
        session.commit()

    st.subheader("📖 Storyline")
    with st.form(key="storyline_form"):
        with session_scope() as session:
            storyline_description = st.text_area(
                "Enter the AI character prompt here...",
                value=storyline_description if storyline else None,
                height=300,
            )

        save_button = st.form_submit_button("Save")
        if save_button:
            with session_scope() as session:
                session.merge(
                    StorylineModel(name=storyline_name, description=storyline_description)
                )
                session.commit()
            st.success("Storyline saved!")

        delete_button = st.form_submit_button("🗑️ Delete")
        if delete_button:
            with session_scope() as session:
                storyline_to_delete = (
                    session.query(StorylineModel)
                    .where(StorylineModel.name == storyline_name)
                    .first()
                )
                if storyline_to_delete:
                    session.delete(storyline_to_delete)
                    session.commit()
                    st.success(f"Storyline '{storyline_name}' deleted!")
                    st.session_state.active_storyline = None
                    st.rerun()

    st.header("📚 Milestones")
    bulk_milestone_prompt = st.text_area(
        "Bulk milestone prompt",
        value='[\n\t{"order": 1, "name": "Milestone 1", "description": "Description 1"},\n'
        '\t{"order": 2, "name": "Milestone 2", "description": "Description 2"}\n]',
        height=150,
    )
    # if st.button("Bulk Add Milestones"):
    st.json(bulk_milestone_prompt)
    if st.button("Bulk Add Milestones"):
        with session_scope() as session:
            for i, milestone in enumerate(json.loads(bulk_milestone_prompt)):
                new_milestone = MilestoneModel(
                    storyline_name=storyline_name,
                    name=milestone["name"],
                    order=milestone["order"],
                    description=milestone["description"],
                    completed=False,
                )
                session.add(new_milestone)
            session.commit()
        st.success("Bulk milestones added!")
        st.rerun()

    with session_scope() as session:
        milestones = (
            session.query(MilestoneModel)
            .where(MilestoneModel.storyline_name == get_active_storyline())
            .order_by(MilestoneModel.order)
            .all()
        )
        for milestone in milestones:
            with st.form(key=f"edit_milestone_form_{milestone.name}"):
                milestone_order = st.text_input("Milestone Number", value=milestone.order)
                milestone_name = st.text_input("Milestone Name", value=milestone.name)
                milestone_description = st.text_area(
                    "Milestone Description", value=milestone.description, height=150
                )
                milestone_completed = st.checkbox("Completed", value=milestone.completed)

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.form_submit_button("💾 Save Changes"):
                        with session_scope() as session:
                            milestone_to_update = (
                                session.query(MilestoneModel)
                                .where(MilestoneModel.storyline_name == get_active_storyline())
                                .where(MilestoneModel.name == milestone.name)
                                .first()
                            )
                            milestone_to_update.name = milestone_name
                            milestone_to_update.description = milestone_description
                            milestone_to_update.completed = milestone_completed
                            session.commit()
                            st.success(f"Milestone '{milestone_name}' updated!")
                with col2:
                    if st.form_submit_button("🗑️ Delete"):
                        with session_scope() as session:
                            milestone_to_delete = (
                                session.query(MilestoneModel)
                                .where(MilestoneModel.storyline_name == get_active_storyline())
                                .where(MilestoneModel.name == milestone.name)
                                .first()
                            )
                            session.delete(milestone_to_delete)
                            session.commit()
                            st.success(f"Milestone '{milestone_name}' deleted!")
                            st.rerun()

        st.divider()
        st.subheader("➕ Add New milestone")
        with st.form(key="new_milestone_form"):
            milestone_order = st.text_input("Milestone Number", value=len(milestones) + 1)
            milestone_name = st.text_input("Milestone Name")
            milestone_description = st.text_area("Milestone Description", height=150)
            add_button = st.form_submit_button("➕ Add milestone")
            if add_button:
                with session_scope() as session:
                    new_milestone = MilestoneModel(
                        storyline_name=get_active_storyline(),
                        name=milestone_name,
                        order=milestone_order,
                        description=milestone_description,
                        completed=False,
                    )
                    session.add(new_milestone)
                    session.commit()
                st.success("New milestone added!")
                st.rerun()


def get_active_milestone(session) -> Optional[MilestoneModel]:
    milestone = (
        session.query(MilestoneModel)
        .where(MilestoneModel.storyline_name == get_active_storyline())
        .where(MilestoneModel.completed.is_(False))
        .order_by(MilestoneModel.order)
        .first()
    )
    if not milestone:
        logging.info("All milestones complete. No milestones remaining.")
        return None
    logging.info(f"Current milestone: '{milestone.name}'")
    return milestone


def get_active_milestone_markdown() -> str:
    with session_scope() as session:
        milestone = get_active_milestone(session)
        if not milestone:
            logging.info("All milestones complete. No milestones remaining.")
            return "<All milestones complete. No milestones remaining.>"

        logging.info(f"Current milestone: '{milestone.name}'")
        return f"""## Milestone#{milestone.order}: {milestone.name}
    {milestone.description}
    """


def mark_milestone_completed(milestone_name: str):
    with session_scope() as session:
        milestone = (
            session.query(MilestoneModel)
            .where(MilestoneModel.storyline_name == get_active_storyline())
            .where(MilestoneModel.name == milestone_name)
            .first()
        )
        logging.info(f"Marking milestone '{milestone_name}' as completed...")
        if milestone:
            milestone.completed = True
            session.commit()
            return True
        return False


def get_active_milestone_classification_example() -> str:
    with session_scope() as session:
        milestone = get_active_milestone(session)
        if not milestone:
            return "<All milestones complete. No milestones remaining.>"
        return f"""An example of an INCOMPLETE classification output:

## Internal Milestone Completion Classification Reasoning

### Step 1: Understand the conversation so far
<...your reasoning here...>

### Step 2: Classify the milestone '{milestone.name}' as INCOMPLETE or COMPLETE
<...your internal incomplete classification reasoning here (see examples below)...>

MILESTONE CLASSIFICATION: INCOMPLETE

An example of a COMPLETE classification output:

## Internal Milestone Completion Classification Reasoning

### Step 1: Understand the conversation so far
<...your reasoning here...>

### Step 2: Classify the milestone '{milestone.name}' as INCOMPLETE or COMPLETE
<...your internal completion classification reasoning here (see examples below)...>

MILESTONE CLASSIFICATION: COMPLETE

---

Some examples of internal reasoning when classifying a milestone as INCOMPLETE:
1. The current milestone '{milestone.name}' talks about ...
However, so far the conversation has not even touched upon this milestone.
Hence, the milestone is still incomplete.

2. The current milestone '{milestone.name}' talks about ...
However, so far the conversation has talked about ...,
    but once cannot clearly or unambiguously conclude that the milestone '{milestone.name}'
    has been completed. Hence, the milestone is still incomplete.

3. The current milestone '{milestone.name}' talks about ...
However, while the character has completed it, the milestone is about the AI.
Hence the milestone is still incomplete.

4. <similar to 3 but vice-versa with AI/character>

5. The current milestone '{milestone.name}' talks about ...
    However, the AI has not done it satisfactorily as described by the milestone description.
    Hence, the milestone is still incomplete.

An example of internal reasoning when classifying a milestone as COMPLETE:
The current milestone '{milestone.name}' talks about ...
The conversation so far talks about...
From "<quote relevant part of conversation>" and "...", it is clear and unambiguous
    that the milestone critetia are satisfied, and has been completed fully and satisfactorily.
Hence, the milestone is complete.
    """
