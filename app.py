import streamlit as st
from typing import Dict, List
import anthropic
import json

class SQLTrainer:
    # [Previous SQLTrainer class implementation remains the same until get_schema_prompt]
    
    def get_schema_diagram_url(self, industry: str) -> str:
        """Returns the URL for the schema diagram"""
        urls = {
            "logistics": "https://claude.site/artifacts/bf15ac3a-7ad0-4693-80ab-0bdcfa1cd2ae",
            "healthcare": "https://claude.site/artifacts/96e82497-f107-4e25-97c1-220b727b1c3b"
        }
        return urls.get(industry, "")

def show_schema_page(trainer: SQLTrainer, industry: str):
    """Displays the schema visualization page"""
    st.title(f"{industry.title()} Database Schema")
    
    # Display the diagram
    diagram_url = trainer.get_schema_diagram_url(industry)
    st.write(f"[View Full Database Diagram]({diagram_url})")
    
    # Add a button to return to the main page
    if st.button("Return to SQL Practice"):
        st.session_state.show_schema = False
        st.rerun()

def show_main_page(trainer: SQLTrainer):
    """Displays the main SQL practice page"""
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Practice SQL")
        # Generate new question
        if st.button("Get New Question") or not st.session_state.current_question:
            st.session_state.current_question = trainer.generate_stakeholder_question(
                st.session_state.industry
            )
        
        st.write("### Business Question:")
        st.info(st.session_state.current_question)
        
        # SQL input
        user_query = st.text_area("Your SQL Query:", height=150)
        
        if st.button("Submit Query"):
            if user_query:
                feedback = trainer.validate_sql(
                    user_query,
                    st.session_state.industry,
                    st.session_state.current_question
                )
                
                if feedback["is_correct"]:
                    st.success(feedback["feedback"])
                else:
                    st.error(feedback["feedback"])
    
    with col2:
        st.header("Help")
        # Add button to view schema
        if st.button("View Database Schema"):
            st.session_state.show_schema = True
            st.rerun()
        
        st.write("### Tips")
        st.write("""
        - Make sure to include all necessary JOINs
        - Remember to use appropriate WHERE clauses
        - Consider using aggregations when needed
        """)

def main():
    st.set_page_config(layout="wide")
    
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error("Error: API key not found in secrets.toml. Please add your Anthropic API key to .streamlit/secrets.toml")
        return
    
    # Initialize session state
    if 'industry' not in st.session_state:
        st.session_state.industry = None
    if 'current_question' not in st.session_state:
        st.session_state.current_question = None
    if 'show_schema' not in st.session_state:
        st.session_state.show_schema = False
    
    # Sidebar
    with st.sidebar:
        st.title("SQL Trainer")
        
        # Industry selection (only shown at start)
        if not st.session_state.industry:
            st.header("Select Industry")
            industry = st.selectbox(
                "What industry do you work in?",
                list(trainer.industry_schemas.keys())
            )
            if st.button("Start Training"):
                st.session_state.industry = industry
                st.rerun()
        else:
            # Add option to change industry
            if st.button("Change Industry"):
                st.session_state.industry = None
                st.session_state.current_question = None
                st.session_state.show_schema = False
                st.rerun()
    
    # Main content area
    if st.session_state.industry:
        if st.session_state.show_schema:
            show_schema_page(trainer, st.session_state.industry)
        else:
            show_main_page(trainer)

if __name__ == "__main__":
    main()
