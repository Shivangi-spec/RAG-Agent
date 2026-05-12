# ui.py
import streamlit as st
import requests 
import json    

# URL of running FastAPI backend
FASTAPI_URL = "http://127.0.0.1:8000/chat"

st.title("Federal Register Document Assistant") # You can change the title

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display prior chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input at the bottom
if prompt := st.chat_input("Ask something about U.S. Federal Register documents..."):
    # Add user message to chat history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get assistant response by calling the FastAPI backend
    with st.chat_message("assistant"):
        message_placeholder = st.empty() # For a "typing..." effect or to update later
        full_response_content = ""
        try:
            # Prepare the request payload
            payload = {"user_message": prompt}
            
            # Make the POST request to your FastAPI backend
            api_response = requests.post(FASTAPI_URL, json=payload)
            api_response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            
            response_data = api_response.json() # Parses the JSON response
            agent_reply = response_data.get("agent_response", "Error: No 'agent_response' field in API reply.")

            full_response_content = agent_reply
            message_placeholder.markdown(full_response_content)

        except requests.exceptions.RequestException as e:
            full_response_content = f"Error connecting to the agent backend: {e}"
            message_placeholder.error(full_response_content)
        except json.JSONDecodeError:
            full_response_content = "Error: Could not decode JSON response from the agent backend."
            message_placeholder.error(full_response_content)
        except Exception as e:
            full_response_content = f"An unexpected error occurred: {e}"
            message_placeholder.error(full_response_content)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response_content})