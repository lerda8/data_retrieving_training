import streamlit as st
from typing import TypedDict, Dict, List, Optional
import anthropic
import json
from datetime import datetime
import time

class SchemaDict(TypedDict):
    schema_url: str
    tables: Dict[str, List[str]]
    relationships: List[str]
    sample_data: Dict[str, List[Dict]]  # Added sample data

class UserProgress(TypedDict):
    correct_queries: int
    total_attempts: int
    last_question: str
    bookmarks: List[str]

class SQLTrainer:
    def __init__(self):
        if 'ANTHROPIC_API_KEY' not in st.secrets:
            raise RuntimeError("ANTHROPIC_API_KEY not found in secrets.toml")
            
        self.client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        self._load_schemas()
        
    def _load_schemas(self):
        """Load schemas from configuration file"""
        try:
            with open('schemas.json', 'r') as f:
                self.industry_schemas: Dict[str, SchemaDict] = json.load(f)
        except FileNotFoundError:
            # Fallback to built-in schemas
            self.industry_schemas = {...}  # Original schemas here

    def get_hint(self, question: str, industry: str) -> str:
        """Generate a hint without revealing the full solution"""
        schema_prompt = self.get_schema_prompt(industry)
        
        prompt = f"""
        {schema_prompt}
        
        For this question: "{question}"
        
        Provide a helpful hint that guides the user toward the solution without giving it away.
        Focus on the key concepts needed to solve this problem.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=150,
                temperature=0.5,
                system="You are a helpful SQL tutor providing guidance.",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Unable to generate hint: {str(e)}"

    def validate_sql(self, query: str, industry: str, question: str) -> Dict:
        """Validates the SQL query with enhanced error handling"""
        if not query.strip():
            return {
                "is_correct": False,
                "feedback": "Query cannot be empty",
                "hint": "Please enter a SQL query",
                "correct_query": None
            }

        # Basic SQL syntax validation
        if not self._validate_basic_syntax(query):
            return {
                "is_correct": False,
                "feedback": "Invalid SQL syntax",
                "hint": "Check your SQL syntax",
                "correct_query": None
            }

        try:
            return super().validate_sql(query, industry, question)
        except Exception as e:
            return {
                "is_correct": False,
                "feedback": f"Error validating query: {str(e)}",
                "hint": "Please try again",
                "correct_query": None
            }

    def _validate_basic_syntax(self, query: str) -> bool:
        """Basic SQL syntax validation"""
        required_keywords = ['SELECT', 'FROM']
        query_upper = query.upper()
        return all(keyword in query_upper for keyword in required_keywords)

    def update_user_progress(self, correct: bool):
        """Update user progress in session state"""
        if 'user_progress' not in st.session_state:
            st.session_state.user_progress = UserProgress(
                correct_queries=0,
                total_attempts=0,
                last_question="",
                bookmarks=[]
            )
        
        progress = st.session_state.user_progress
        progress['total_attempts'] += 1
        if correct:
            progress['correct_queries'] += 1

def main():
    st.set_page_config(layout="wide")
    
    # Initialize all session state variables at the start
    if 'industry' not in st.session_state:
        st.session_state.industry = None
    if 'current_question' not in st.session_state:
        st.session_state.current_question = None
    if 'user_progress' not in st.session_state:
        st.session_state.user_progress = {
            'correct_queries': 0,
            'total_attempts': 0,
            'last_question': '',
            'bookmarks': []
        }
    
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error("Error: API key not found in secrets.toml. Please add your Anthropic API key to .streamlit/secrets.toml")
        return
    
    # Industry selection (only shown at start)
    if not st.session_state.industry:
        st.header("Select Industry 🏭")
        industry = st.selectbox(
            "What industry do you work in?",
            list(trainer.industry_schemas.keys())
        )
        if st.button("Start Training ▶️"):
            st.session_state.industry = industry
            # Generate first question immediately after industry selection
            with st.spinner('Generating new question... 🤔'):
                st.session_state.current_question = trainer.generate_stakeholder_question(industry)
            st.rerun()
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Generate new question button
            if st.button("Get New Question 🎯"):
                with st.spinner('Generating new question... 🤔'):
                    try:
                        st.session_state.current_question = trainer.generate_stakeholder_question(
                            st.session_state.industry
                        )
                    except Exception as e:
                        st.error(f"Error generating question: {str(e)}")
                        st.session_state.current_question = None
            
            # Display current question if it exists
            if st.session_state.current_question:
                st.write("### Question 📋")
                st.info(st.session_state.current_question)
                
                # SQL input
                user_query = st.text_area("Your SQL Query: ⌨️", height=150)
                
                if st.button("Submit Query 🚀"):
                    if user_query:
                        with st.spinner('Analyzing your SQL code... 🔍'):
                            try:
                                feedback = trainer.validate_sql(
                                    user_query,
                                    st.session_state.industry,
                                    st.session_state.current_question
                                )
                                
                                if feedback["is_correct"]:
                                    st.success("🎉 " + feedback["feedback"])
                                else:
                                    st.error("❌ " + feedback["feedback"])
                            except Exception as e:
                                st.error(f"Error validating query: {str(e)}")
                    else:
                        st.warning("Please enter a SQL query before submitting.")
            else:
                # Generate initial question if none exists
                with st.spinner('Generating new question... 🤔'):
                    try:
                        st.session_state.current_question = trainer.generate_stakeholder_question(
                            st.session_state.industry
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generating question: {str(e)}")
        
        with col2:
            st.header("Help")
            
            # Change Industry button
            if st.button("Change Industry 🔄"):
                st.session_state.industry = None
                st.session_state.current_question = None
                st.rerun()
            
            # Add link button to view schema URL in new tab
            schema_url = trainer.industry_schemas[st.session_state.industry]["schema_url"]
            st.link_button("View Database Schema 📊", schema_url)
            
            st.write("### Tips 💡")
            st.write("""
            - 🔗 Make sure to include all necessary JOINs
            - 🎯 Remember to use appropriate WHERE clauses
            - 📊 Consider using aggregations when needed
            """)

if __name__ == "__main__":
    main()
