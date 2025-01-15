import streamlit as st
from typing import Dict, List
import anthropic
import json
import webbrowser
import hmac

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
    # ... rest of your SQLTrainer class remains the same ...

def main():
    st.set_page_config(layout="wide")
    
    if not check_password():
        st.stop()  # Do not continue if check_password is False
        
    try:
        trainer = SQLTrainer()
    except RuntimeError as e:
        st.error("Error: API key not found in secrets.toml")
        return
        
    # Rest of your main() function remains the same...

if __name__ == "__main__":
    main()
