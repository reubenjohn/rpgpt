import streamlit as st
from token_world.llm.xplore.db import (
    CharacterModel,
    session_scope,
)
from token_world.llm.xplore.session_state import get_active_storyline


def character_editor():
    with session_scope() as session:
        if (storyline := get_active_storyline()) is None:
            st.error("Please select a storyline to get started.")
            return

        characters = (
            session.query(CharacterModel)
            .where(CharacterModel.storyline_name == storyline)
            .order_by(CharacterModel.name)
            .all()
        )
        col1, col2, col3 = st.columns([2, 4, 1])
        col1.write("Type")
        col2.write("Name")
        col3.write("Delete")

        st.divider()

        for character in characters:
            col1, col2, col5 = st.columns([2, 4, 1])
            col1.write(character.type)
            col2.write(character.name)
            if col5.button("🗑️", key=f"delete_character_{character.name}"):
                session.delete(character)
                session.commit()
                st.rerun()

        character_type = st.selectbox("Type", ["player1", "character1"], key="character_type")
        name = st.text_input("Name", key="character_name")
        if st.button("Add Character"):
            session.add(CharacterModel(storyline_name=storyline, type=character_type, name=name))
            session.commit()
            st.rerun()
