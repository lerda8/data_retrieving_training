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
        self.industry_schemas = {
            "logistics": {
                "schema_url": "https://claude.site/artifacts/bf15ac3a-7ad0-4693-80ab-0bdcfa1cd2ae",
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

    def get_schema_prompt(self, industry: str) -> str:
        """Creates a detailed prompt describing the database schema"""
        schema = self.industry_schemas.get(industry)
        if not schema:
            return "Industry not found"
            
        prompt = f"Database Schema for {industry.title()}:\n\n"
        
        # Add tables
        prompt += "Tables:\n"
        for table, columns in schema["tables"].items():
            prompt += f"- {table} ({', '.join(columns)})\n"
        
        # Add relationships
        prompt += "\nRelationships:\n"
        for rel in schema["relationships"]:
            prompt += f"- {rel}\n"
            
        return prompt

    def generate_stakeholder_question(self, industry: str) -> str:
        """Generates a business question using Claude"""
        schema_prompt = self.get_schema_prompt(industry)
        
        prompt = f"""
        {schema_prompt}
    
        Act as a business stakeholder in the {industry} industry.
        Ask for a report that requires SQL to generate.
        Don't add any fluff, just ask for the data.
        The question should be simple.
        Only max 2 joins, SUM(), COUNT(), MIN(), MAX() functions should be needed.
        
        Example format:
        "I need a report showing [business need]."
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=150,
                temperature=0.7,
                system="You are a business stakeholder asking for data.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Error generating question: {str(e)}")

    def validate_sql(self, query: str, industry: str, question: str) -> Dict:
        """Validates the SQL query using Claude"""
        schema_prompt = self.get_schema_prompt(industry)
        
        prompt = f"""
        {schema_prompt}
    
        The stakeholder asked: "{question}"
        
        The user provided this SQL query:
        {query}
        
        Please analyze if this query correctly answers the question. Provide:
        1. Whether the query is correct (yes/no)
        2. Specific feedback about what's right or wrong
        3. A hint if the query needs improvement
        4. The correct query if the user's query is wrong
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=500,
                temperature=0,
                system="You are a SQL expert providing feedback.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            feedback = response.content[0].text
            
            # Parse the response into parts
            is_correct = "yes" in feedback.lower().split("\n")[0]
            
            return {
                "is_correct": is_correct,
                "feedback": feedback,
                "hint": feedback if not is_correct else "",
                "correct_query": feedback if not is_correct else query
            }
        except Exception as e:
            raise Exception(f"Error validating SQL: {str(e)}")

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
        # Get the list of industries from the dictionary keys
        industries = list(trainer.industry_schemas.keys())
        industry = st.selectbox(
            "What industry do you work in?",
            industries
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
