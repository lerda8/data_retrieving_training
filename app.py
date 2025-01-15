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
    
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error("Error: API key not found in secrets.toml. Please add your Anthropic API key to .streamlit/secrets.toml")
        return

    # Initialize session state
    if 'user_progress' not in st.session_state:
        st.session_state.user_progress = UserProgress(
            correct_queries=0,
            total_attempts=0,
            last_question="",
            bookmarks=[]
        )

    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Main training interface
        # ... (existing code)

        # Add syntax highlighting for SQL input
        user_query = st.text_area(
            "Your SQL Query: ⌨️",
            height=150,
            key="sql_input",
            help="Write your SQL query here"
        )

        col1_1, col1_2, col1_3 = st.columns(3)
        
        with col1_1:
            if st.button("Submit Query 🚀"):
                process_query(trainer, user_query)
                
        with col1_2:
            if st.button("Get Hint 💡"):
                with st.spinner('Generating hint...'):
                    hint = trainer.get_hint(
                        st.session_state.current_question,
                        st.session_state.industry
                    )
                    st.info(hint)
                    
        with col1_3:
            if st.button("Reset Query 🔄"):
                st.session_state.sql_input = ""
                st.rerun()

    with col2:
        # Progress tracking
        st.header("Your Progress 📊")
        progress = st.session_state.user_progress
        st.metric("Correct Queries", progress['correct_queries'])
        st.metric("Success Rate", 
                 f"{(progress['correct_queries'] / max(progress['total_attempts'], 1)) * 100:.1f}%")

    with col3:
        # Learning resources
        st.header("Learning Resources 📚")
        st.write("Related SQL Concepts:")
        if st.session_state.current_question:
            # Generate relevant concepts based on current question
            concepts = generate_relevant_concepts(st.session_state.current_question)
            for concept in concepts:
                st.write(f"- {concept}")

def process_query(trainer: SQLTrainer, query: str):
    """Process and validate the SQL query"""
    if not query:
        st.error("Please enter a SQL query")
        return

    with st.spinner('Analyzing your SQL code... 🔍'):
        try:
            feedback = trainer.validate_sql(
                query,
                st.session_state.industry,
                st.session_state.current_question
            )
            
            trainer.update_user_progress(feedback["is_correct"])
            
            if feedback["is_correct"]:
                st.success("🎉 " + feedback["feedback"])
                if feedback["correct_query"]:
                    st.code(feedback["correct_query"], language="sql")
            else:
                st.error("❌ " + feedback["feedback"])
                if feedback["hint"]:
                    st.info("💡 " + feedback["hint"])
                    
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

def generate_relevant_concepts(question: str) -> List[str]:
    """Generate relevant SQL concepts based on the current question"""
    # This could be enhanced with Claude's help
    concepts = ["Basic SELECT statements",
                "JOINs",
                "Aggregation functions",
                "WHERE clauses"]
    return concepts

if __name__ == "__main__":
    main()
