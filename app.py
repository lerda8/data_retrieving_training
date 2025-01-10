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
            
            # Change Industry button
            if st.button("Change Industry"):
                st.session_state.industry = None
                st.session_state.current_question = None
                st.rerun()
            
            # Add link button to view schema URL in new tab
            schema_url = trainer.industry_schemas[st.session_state.industry]["schema_url"]
            st.link_button("View Database Schema", schema_url)
            
            st.write("### Tips")
            st.write("""
            - Make sure to include all necessary JOINs
            - Remember to use appropriate WHERE clauses
            - Consider using aggregations when needed
            """)

if __name__ == "__main__":
    main()
