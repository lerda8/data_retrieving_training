import streamlit as st
from typing import Dict, List, Optional, Tuple
import anthropic
import json
from datetime import datetime
import re

class SQLTrainer:
    def __init__(self):
        # Initialize Anthropic client with better error handling
        self.client = self._initialize_anthropic_client()
        
        # Enhanced schema definitions with additional metadata
        self.industry_schemas: Dict[str, Dict] = {
            "logistics": {
                "schema_url": "https://claude.site/artifacts/bf15ac3a-7ad0-4693-80ab-0bdcfa1cd2ae",
                "description": "Logistics and warehouse management system tracking inventory, shipments, and carriers.",
                "tables": {
                    "warehouses": ["warehouse_id", "name", "location", "capacity"],
                    "inventory": ["item_id", "warehouse_id", "product_name", "quantity", "reorder_point"],
                    "shipments": ["shipment_id", "origin_warehouse", "destination", "status", "carrier_id"],
                    "carriers": ["carrier_id", "name", "service_level", "cost_per_mile"]
                },
                "relationships": [
                    "inventory.warehouse_id -> warehouses.warehouse_id",
                    "shipments.origin_warehouse -> warehouses.warehouse_id",
                    "shipments.carrier_id -> carriers.carrier_id"
                ]
            },
            "healthcare": {
                "schema_url": "https://claude.site/artifacts/96e82497-f107-4e25-97c1-220b727b1c3b",
                "description": "Healthcare management system tracking patients, appointments, and treatments.",
                "tables": {
                    "patients": ["patient_id", "name", "dob", "insurance_id"],
                    "appointments": ["appointment_id", "patient_id", "doctor_id", "date", "status"],
                    "doctors": ["doctor_id", "name", "specialty", "department"],
                    "treatments": ["treatment_id", "patient_id", "doctor_id", "diagnosis", "date"]
                },
                "relationships": [
                    "appointments.patient_id -> patients.patient_id",
                    "appointments.doctor_id -> doctors.doctor_id",
                    "treatments.patient_id -> patients.patient_id"
                ]
            }
        }
        
        # Track user progress
        if 'user_stats' not in st.session_state:
            st.session_state.user_stats = {
                'total_attempts': 0,
                'correct_answers': 0,
                'questions_history': []
            }

    def _initialize_anthropic_client(self) -> anthropic.Anthropic:
        """Initialize Anthropic client with error handling"""
        try:
            if 'ANTHROPIC_API_KEY' not in st.secrets:
                raise RuntimeError("ANTHROPIC_API_KEY not found in secrets.toml")
            return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        except Exception as e:
            st.error(f"Failed to initialize Anthropic client: {str(e)}")
            raise

    def get_schema_prompt(self, industry: str) -> str:
        """Creates a detailed prompt describing the database schema with examples"""
        schema = self.industry_schemas.get(industry)
        if not schema:
            return "Industry not found"
        
        prompt = f"Database Schema for {industry.title()}:\n\n"
        prompt += f"Description: {schema['description']}\n\n"
        
        # Add tables with detailed formatting
        prompt += "Tables:\n"
        for table, columns in schema["tables"].items():
            prompt += f"- {table}\n"
            for col in columns:
                prompt += f"  └─ {col}\n"
        
        # Add relationships
        prompt += "\nRelationships:\n"
        for rel in schema["relationships"]:
            prompt += f"- {rel}\n"
            
        return prompt

    def _format_sql_query(self, query: str) -> str:
        """Format SQL query with proper indentation and capitalization"""
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        # Capitalize SQL keywords
        keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'ON', 'GROUP BY', 'ORDER BY', 'HAVING']
        for keyword in keywords:
            query = re.sub(rf'\b{keyword}\b', keyword, query, flags=re.IGNORECASE)
            
        return query

    def generate_stakeholder_question(self, industry: str) -> Tuple[str, str]:
        """Generates a business question using Claude"""
        schema_prompt = self.get_schema_prompt(industry)
        
        prompt = f"""
        {schema_prompt}
    
        Act as a business stakeholder in the {industry} industry.
        Generate a question that requires SQL to answer.
        Use only max 2 joins and basic aggregation functions like COUNT, SUM.
        
        Return both the business question AND the correct SQL query to solve it.
        Format the response as:
        QUESTION: [your question]
        SQL: [the correct sql query]
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=500,
                temperature=0.7,
                system="You are a business stakeholder asking for data.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response to get question and solution
            content = response.content[0].text
            question_match = re.search(r'QUESTION:\s*(.*?)\s*SQL:', content, re.DOTALL)
            sql_match = re.search(r'SQL:\s*(.*?)$', content, re.DOTALL)
            
            if not question_match or not sql_match:
                raise ValueError("Could not parse question and SQL from response")
                
            question = question_match.group(1).strip()
            solution = sql_match.group(1).strip()
            
            if not question or not solution:
                raise ValueError("Empty question or SQL solution")
                
            return question, solution
            
        except Exception as e:
            st.error(f"Error generating question: {str(e)}")
            return "Failed to generate question. Please try again.", ""

    def validate_sql(self, query: str, industry: str, question: str, correct_sql: str) -> Dict:
        """Validates the SQL query using Claude with enhanced feedback"""
        schema_prompt = self.get_schema_prompt(industry)
        
        prompt = f"""
        {schema_prompt}
    
        The stakeholder asked: "{question}"
        
        User's SQL query:
        {self._format_sql_query(query)}
        
        Correct SQL query:
        {self._format_sql_query(correct_sql)}
        
        Analyze the user's query and provide:
        1. Is the query correct? (yes/no)
        2. Detailed feedback about what's right and wrong
        3. Specific hints for improvement if needed
        4. Explanation of any potential performance issues
        5. Tips for better SQL practices
        
        Format as JSON with keys: is_correct, feedback, hints, performance_notes
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                temperature=0,
                system="You are a SQL expert providing detailed feedback.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            feedback_dict = json.loads(response.content[0].text)
            
            # Update user stats
            st.session_state.user_stats['total_attempts'] += 1
            if feedback_dict['is_correct']:
                st.session_state.user_stats['correct_answers'] += 1
            
            # Add to history
            st.session_state.user_stats['questions_history'].append({
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'question': question,
                'user_query': query,
                'correct': feedback_dict['is_correct']
            })
            
            return feedback_dict
            
        except Exception as e:
            st.error(f"Error validating SQL: {str(e)}")
            return {
                "is_correct": False,
                "feedback": "Error occurred during validation",
                "hints": [],
                "performance_notes": ""
            }

def render_progress_tracker():
    """Render user progress statistics"""
    stats = st.session_state.user_stats
    
    st.write("### Your Progress")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Attempts", stats['total_attempts'])
    with col2:
        st.metric("Correct Answers", stats['correct_answers'])
    with col3:
        accuracy = (stats['correct_answers'] / stats['total_attempts'] * 100) if stats['total_attempts'] > 0 else 0
        st.metric("Accuracy", f"{accuracy:.1f}%")

def main():
    st.set_page_config(layout="wide", page_title="SQL Training Assistant")
    
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error(f"Error initializing SQL Trainer: {str(e)}")
        return
    
    # Initialize session state
    if 'industry' not in st.session_state:
        st.session_state.industry = None
        st.session_state.current_question = None
        st.session_state.current_solution = None
    
    st.title("SQL Training Assistant 🎓")
    
    # Industry selection screen
    if not st.session_state.industry:
        st.header("Welcome to SQL Training! 👋")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("""
            Practice writing SQL queries for real-world business scenarios.
            Select an industry to get started!
            """)
            
            industry = st.selectbox(
                "Choose your industry:",
                list(trainer.industry_schemas.keys()),
                format_func=lambda x: x.title()
            )
            
            if st.button("Start Training ▶️", type="primary"):
                st.session_state.industry = industry
                st.rerun()
        
        with col2:
            st.write("### Features:")
            st.write("""
            - 🎯 Real-world business scenarios
            - 📊 Interactive schema viewer
            - 🎓 Detailed feedback
            - 📈 Progress tracking
            """)
    
    # Main training interface
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Generate new question
            if st.button("Get New Question 🎯") or not st.session_state.current_question:
                with st.spinner('Generating new question... 🤔'):
                    question, solution = trainer.generate_stakeholder_question(
                        st.session_state.industry
                    )
                    st.session_state.current_question = question
                    st.session_state.current_solution = solution
            
            st.write("### Business Question 📋")
            st.info(st.session_state.current_question)
            
            # SQL input with syntax highlighting
            user_query = st.text_area(
                "Your SQL Query:",
                height=150,
                help="Write your SQL query here. Use proper syntax and formatting."
            )
            
            col_submit, col_hint = st.columns([2, 1])
            with col_submit:
                if st.button("Submit Query 🚀", type="primary"):
                    if user_query:
                        with st.spinner('Analyzing your query... 🔍'):
                            feedback = trainer.validate_sql(
                                user_query,
                                st.session_state.industry,
                                st.session_state.current_question,
                                st.session_state.current_solution
                            )
                        
                        if feedback["is_correct"]:
                            st.success("✨ Correct! " + feedback["feedback"])
                            st.write("🚀 Performance notes: " + feedback["performance_notes"])
                        else:
                            st.error("❌ " + feedback["feedback"])
                            st.info("💡 Hints: " + "\n".join(feedback["hints"]))
            
            with col_hint:
                if st.button("Show Solution 💡"):
                    st.code(st.session_state.current_solution, language="sql")
        
        with col2:
            st.header("Help")
            
            # Change Industry button
            if st.button("Change Industry 🔄"):
                st.session_state.industry = None
                st.session_state.current_question = None
                st.rerun()
            
            # Schema URL button
            schema_url = trainer.industry_schemas[st.session_state.industry]["schema_url"]
            st.link_button("View Database Schema 📊", schema_url)
            
            # Progress tracker
            render_progress_tracker()
            
            # Tips section
            st.write("### Tips 💡")
            st.write("""
            - 🔗 Make sure to include all necessary JOINs
            - 🎯 Remember to use appropriate WHERE clauses
            - 📊 Consider using aggregations when needed
            """)

if __name__ == "__main__":
    main()
