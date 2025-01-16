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

    # First run or password not yet entered
    if "password_correct" not in st.session_state:
        st.text_input(
            "Password", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        return False
    
    # Password already entered and correct
    elif st.session_state["password_correct"]:
        return True
    
    # Password entered but incorrect
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
        # Check for required secrets
        required_secrets = ['ANTHROPIC_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY']
        missing_secrets = [secret for secret in required_secrets if secret not in st.secrets]
        if missing_secrets:
            raise RuntimeError(f"Missing required secrets: {', '.join(missing_secrets)}")
            
        self.client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        self.supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        self.industry_schemas: Dict[str, Dict] = {
            "logistics": {
                "schema_url": "https://claude.site/artifacts/98ddf448-03e9-496c-928a-48d0604d4759", 
                "tables": {
                    "products": ["product_id", "sku", "name", "description", "category", "unit_weight", "unit_volume", "base_price", "minimum_stock", "is_active"],
                    "warehouses": ["warehouse_id", "name", "address", "city", "state", "zip_code", "total_capacity", "temperature_controlled", "operating_hours", "status"],
                    "zones": ["zone_id", "warehouse_id", "zone_name", "zone_type", "capacity", "temperature_range"],
                    "inventory": ["inventory_id", "product_id", "warehouse_id", "zone_id", "quantity", "lot_number", "expiration_date", "last_counted_date"],
                    "suppliers": ["supplier_id", "name", "contact_person", "email", "phone", "address", "payment_terms", "rating", "active"],
                    "purchase_orders": ["po_id", "supplier_id", "warehouse_id", "order_date", "expected_delivery", "status", "total_amount"],
                    "po_items": ["po_item_id", "po_id", "product_id", "quantity", "unit_price"],
                    "employees": ["employee_id", "first_name", "last_name", "email", "phone", "role", "warehouse_id", "hire_date", "certification"],
                    "shipments": ["shipment_id", "warehouse_id", "destination_address", "carrier", "tracking_number", "status", "ship_date", "estimated_delivery", "actual_delivery"],
                    "shipment_items": ["shipment_item_id", "shipment_id", "product_id", "quantity", "picked_by", "picked_from_zone"]
                },
                "relationships": [
                    "zones.warehouse_id -> warehouses.warehouse_id",
                    "inventory.product_id -> products.product_id",
                    "inventory.warehouse_id -> warehouses.warehouse_id",
                    "inventory.zone_id -> zones.zone_id",
                    "purchase_orders.supplier_id -> suppliers.supplier_id",
                    "purchase_orders.warehouse_id -> warehouses.warehouse_id",
                    "po_items.po_id -> purchase_orders.po_id",
                    "po_items.product_id -> products.product_id",
                    "employees.warehouse_id -> warehouses.warehouse_id",
                    "shipments.warehouse_id -> warehouses.warehouse_id",
                    "shipment_items.shipment_id -> shipments.shipment_id",
                    "shipment_items.product_id -> products.product_id",
                    "shipment_items.picked_by -> employees.employee_id",
                    "shipment_items.picked_from_zone -> zones.zone_id"
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
        
            You are a business stakeholder in the {industry} industry who needs data for analysis.
            Generate ONE business question that can be answered with SQL.
        
            The database contains:
            - Warehouses with inventory
            - Products with quantities and minimum stock levels
            - Active shipments and orders
            
            Focus your question on:
            - Current inventory levels
            - Basic warehouse statistics
            - Simple product counts
            
            Requirements:
            - Question must be specific and actionable
            - Query should require at most 1 JOIN
            - Can use basic aggregations (SUM, COUNT, MIN, MAX)
            - Must be answerable using basic warehouse/inventory metrics
            
            Format your response as:
            "I need a report showing [specific metric] for [specific business purpose]."
        """
        
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

    def validate_sql(self, query: str, industry: str, question: str) -> Dict:
        """Validates the SQL query using Claude"""
        schema_prompt = self.get_schema_prompt(industry)
        
        prompt = f"""
        {schema_prompt}
    
        The stakeholder asked: "{question}"
        
        The user provided this SQL query:
        {query}
        
        Please analyze if this query correctly answers the question. The query should follow PostgressSQL syntax. Provide:
        1. Whether the query is correct (yes/no)
        2. Specific feedback about what's right or wrong
        3. A hint if the query needs improvement
        4. The correct query if the user's query is wrong.
        """
        
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
    
    def execute_query(self, query: str) -> Dict:
        """Executes the SQL query against Supabase database"""
        try:
            # Remove trailing semicolon and whitespace
            cleaned_query = query.strip().rstrip(';')
            
            result = self.supabase.rpc('execute_query', {'query_text': cleaned_query}).execute()
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

def main():
    st.set_page_config(layout="wide")
    
    if not check_password():
        st.stop()  # Do not continue if check_password is False
    
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error(f"Error: {str(e)}")
        return
    
    # Initialize session state
    if 'industry' not in st.session_state:
        st.session_state.industry = None
        st.session_state.current_question = None
    
    st.title("SQL Trainer")
    
    # Industry selection (only shown at start)
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
            # Generate new question with loading spinner
            if st.button("Get New Question 🎯") or not st.session_state.current_question:
                with st.spinner('Generating new question... 🤔'):
                    st.session_state.current_question = trainer.generate_stakeholder_question(
                        st.session_state.industry
                    )
            
            st.write("### Question 📋")
            st.info(st.session_state.current_question)
            
            # SQL input
            user_query = st.text_area("Your SQL Query: ⌨️", height=150)
            
            # Create two columns for the buttons
            button_col1, button_col2 = st.columns(2)
            
            with button_col1:
                if st.button("Submit for Validation 🔍"):
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
            
            with button_col2:
                if st.button("Query Database 📊"):
                    if user_query:
                        with st.spinner('Executing query... 🔄'):
                            result = trainer.execute_query(user_query)
                            
                            if result["success"]:
                                st.write("### Query Results")
                                st.dataframe(result["data"])
                            else:
                                st.error(f"Query Error: {result['error']}")
        
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
            - 🚀 Use 'Submit for Validation' to check your query
            - 🔍 Use 'Query Database' to see actual results
            """)

if __name__ == "__main__":
    main()
