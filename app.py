import streamlit as st
from typing import Dict, List
import anthropic
import json
import webbrowser
import hmac
from supabase import create_client

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["PASSWORD"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Remove password from session state
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "Password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        return False
    
    elif st.session_state["password_correct"]:
        return True
    
    else:
        st.text_input(
            "Password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.error("😕 Password incorrect")
        return False

class SQLTrainer:
    def __init__(self):
        if 'ANTHROPIC_API_KEY' not in st.secrets:
            raise RuntimeError("ANTHROPIC_API_KEY not found in secrets.toml")
        if 'SUPABASE_URL' not in st.secrets or 'SUPABASE_KEY' not in st.secrets:
            raise RuntimeError("Supabase credentials not found in secrets.toml")
            
        self.client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        self.supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        
        self.industry_schemas: Dict[str, Dict] = {
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

    def execute_query(self, query: str) -> Dict:
        """Executes the SQL query against Supabase database"""
        try:
            # Execute the query using Supabase
            result = self.supabase.rpc('execute_query', {'query_text': query}).execute()
            
            return {
                "success": True,
                "data": result.data,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    # ... [Previous methods remain unchanged] ...

def main():
    st.set_page_config(layout="wide")
    
    if not check_password():
        st.stop()
    
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error("Error: Required credentials not found in secrets.toml")
        return
    
    if 'industry' not in st.session_state:
        st.session_state.industry = None
        st.session_state.current_question = None
    
    st.title("SQL Trainer")
    
    if not st.session_state.industry:
        st.header("Select Industry 🏭")
        industry = st.selectbox(
            "What industry do you work in?",
            list(trainer.industry_schemas.keys())
        )
        if st.button("Start Training ▶️"):
            st.session_state.industry = industry
            st.rerun()
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button("Get New Question 🎯") or not st.session_state.current_question:
                with st.spinner('Generating new question... 🤔'):
                    st.session_state.current_question = trainer.generate_stakeholder_question(
                        st.session_state.industry
                    )
            
            st.write("### Question 📋")
            st.info(st.session_state.current_question)
            
            user_query = st.text_area("Your SQL Query: ⌨️", height=150)
            
            col1_1, col1_2 = st.columns(2)
            
            with col1_1:
                if st.button("Submit Query for Validation 🔍"):
                    if user_query:
                        with st.spinner('Analyzing your SQL code... 🔍'):
                            feedback = trainer.validate_sql(
                                user_query,
                                st.session_state.industry,
                                st.session_state.current_question
                            )
                        
                        if feedback["is_correct"]:
                            st.success("🎉 " + feedback["feedback"])
                        else:
                            st.error("❌ " + feedback["feedback"])
            
            with col1_2:
                if st.button("Query Database 📊"):
                    if user_query:
                        with st.spinner('Executing query... 💫'):
                            result = trainer.execute_query(user_query)
                            
                        if result["success"]:
                            st.dataframe(result["data"])
                        else:
                            st.error(f"Query execution failed: {result['error']}")
        
        with col2:
            st.header("Help")
            
            if st.button("Change Industry 🔄"):
                st.session_state.industry = None
                st.session_state.current_question = None
                st.rerun()
            
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
