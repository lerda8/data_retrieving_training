import streamlit as st
from typing import Dict, List
import anthropic
import json

class SQLTrainer:
    def __init__(self):
        if 'ANTHROPIC_API_KEY' not in st.secrets:
            raise RuntimeError("ANTHROPIC_API_KEY not found in secrets.toml")
            
        self.client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        self.industry_schemas: Dict[str, Dict] = {
            "logistics": {
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
            
        prompt = f"You are working with a {industry} database with the following structure:\n\n"
        
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
        Make it sound natural, like a real stakeholder would ask.
        The question should require joining at least 2 tables.
        
        Example format:
        "Hi, I need a report showing [business need]. Can you help me get this data?"
        """
        
        response = self.client.messages.create(
            model="claude-3-opus-20240229",
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

    def validate_sql(self, query: str, industry: str, question: str) -> Dict:
        """Validates the SQL query using Claude"""
        schema_prompt = self.get_schema_prompt(industry)
        
        prompt = f"""
        {schema_prompt}

        The stakeholder asked: "{question}"
        
        The user provided this SQL query:
        {query}
        
        Please analyze the query and provide feedback in the following JSON format:
        {{
            "is_correct": true/false,
            "feedback": "Detailed feedback about what's right or wrong",
            "hint": "A hint if the query is wrong",
            "correct_query": "The correct query if the user's query is wrong"
        }}

        Ensure the output is valid JSON.
        """
        
        response = self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=500,
            temperature=0,
            system="You are a SQL expert providing feedback. Always respond with valid JSON.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            return {
                "is_correct": False,
                "feedback": "Error processing feedback",
                "hint": "Please try again",
                "correct_query": None
            }

def main():
    st.title("Industry-Specific SQL Trainer")
    
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error("Error: API key not found in secrets.toml. Please add your Anthropic API key to .streamlit/secrets.toml")
        return
        
    # Initialize session state
    if 'industry' not in st.session_state:
        st.session_state.industry = None
        st.session_state.current_question = None
    
    # Industry selection (only shown at start)
    if not st.session_state.industry:
        industry = st.selectbox(
            "What industry do you work in?",
            list(trainer.industry_schemas.keys())
        )
        if st.button("Start Training"):
            st.session_state.industry = industry
            st.rerun()
    
    # Main training interface
    else:
        # Show schema button
        if st.button("Show Database Schema"):
            st.code(trainer.get_schema_prompt(st.session_state.industry))
        
        # Generate new question
        if st.button("Get New Question") or not st.session_state.current_question:
            st.session_state.current_question = trainer.generate_stakeholder_question(
                st.session_state.industry
            )
        
        st.write("Stakeholder:", st.session_state.current_question)
        
        # SQL input
        user_query = st.text_area("Your SQL Query:", height=150)
        
        if st.button("Submit"):
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
                    if st.button("Show Hint"):
                        st.info(feedback["hint"])
                    if st.button("Show Solution"):
                        st.code(feedback["correct_query"])

if __name__ == "__main__":
    main()