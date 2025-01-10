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
        st.session_state.current_question = None
    
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
                st.rerun()
    
    # Main content area
    if st.session_state.industry:
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
            # Add link to view schema
            schema_url = trainer.industry_schemas[st.session_state.industry]["schema_url"]
            st.markdown(f'<a href="{schema_url}" target="_blank" class="button">View Database Schema</a>', unsafe_allow_html=True)
            
            st.write("### Tips")
            st.write("""
            - Make sure to include all necessary JOINs
            - Remember to use appropriate WHERE clauses
            - Consider using aggregations when needed
            """)

if __name__ == "__main__":
    main()
