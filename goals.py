import json
import logging
import random
from typing import Optional
import streamlit as st
from token_world.llm.xplore.db import AgentGoalModel, session_scope


def goal_editor():
    with session_scope() as session:
        if st.button("✖️ Uncheck All"):
            session.query(AgentGoalModel).update({AgentGoalModel.completed: False})
            session.commit()

        goals = session.query(AgentGoalModel).order_by(AgentGoalModel.completed).all()

        for goal in goals:
            goal_form(goal)

        st.divider()

        st.subheader("➕ Add New Goal")
        goal_form(None)


def goal_form(goal: Optional[AgentGoalModel] = None):
    expanded = goal is None
    if goal is None:
        goal = AgentGoalModel(name="", description="", completed=False, persistence="Medium")
    expander_name = str(goal.name)
    if goal.completed:
        expander_name = f"~{expander_name}~"
    with st.expander(expander_name, expanded=expanded), st.form(key=f"form_{goal.name}"):
        name = st.text_input("Name", value=goal.name)
        description = st.text_area("Description", value=goal.description)
        persistence = st.selectbox(
            "Persistence",
            ["Low", "Medium", "High", "Forever"],
            index=["Low", "Medium", "High", "Forever"].index(str(goal.persistence)),
        )

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            completed = st.checkbox("Completed", value=bool(goal.completed))
        with col2:
            if st.form_submit_button("Save"):
                with st.spinner("Saving..."):
                    with session_scope() as session2:
                        goal_to_update = (
                            session2.query(AgentGoalModel)
                            .filter(AgentGoalModel.name == goal.name)
                            .first()
                        )
                        goal_to_update.completed = completed
                        goal_to_update.name = name
                        goal_to_update.description = description
                        goal_to_update.persistence = persistence
                        session2.commit()
                        st.success("Goal updated!")
                st.rerun()
        with col3:
            if st.form_submit_button("🗑️"):
                with session_scope() as session2:
                    session2.delete(
                        session2.query(AgentGoalModel)
                        .where(AgentGoalModel.name == goal.name)
                        .first()
                    )
                    session2.commit()
                    st.success("Goal deleted!")
                st.rerun()


def random_goal_completion_output() -> str:
    with session_scope() as session:
        goals = (
            session.query(AgentGoalModel)
            .where(AgentGoalModel.completed.is_(False))
            .order_by(AgentGoalModel.name)
            .all()
        )
        goal_classifications = {
            goal.name: random.choice(["COMPLETE", "INCOMPLETE"]) for goal in goals
        }
        return f"""
## Internal Goal Completion Classification Reasoning
...

GOALS:
{json.dumps(goal_classifications)}"""


def get_active_goals_markdown(exclude_forever: bool = False) -> str:
    """Retrieve all incomplete goals and return them as a markdown table."""
    with session_scope() as session:
        goals_query = session.query(AgentGoalModel).where(AgentGoalModel.completed.is_(False))
        if exclude_forever:
            goals_query = goals_query.where(AgentGoalModel.persistence != "Forever")
        goals = goals_query.order_by(AgentGoalModel.name).all()
        logging.info(f"Found {len(goals)} goals")
        return f"""
        ## Current Goals
        | Name | Description | Completed | Persistence |
        | --- | --- | --- | --- |
        {" | ".join([f"{goal.name} | {goal.description} | {goal.completed} | {goal.persistence}"
                      for goal in goals])}
        """


def mark_goal_completed(goal_name: str):
    with session_scope() as session:
        goal = session.query(AgentGoalModel).filter(AgentGoalModel.name == goal_name).first()
        if goal:
            goal.completed = True
            session.commit()
            return True
        return False
