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
