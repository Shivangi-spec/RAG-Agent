# RAG Agent 

This project is a Retrieval-Augmented Generation based assistant built using FastAPI, Streamlit, MySQL, and an LLM through an Ollama/OpenAI-compatible API. The system allows users to ask questions and receive context-aware responses by retrieving relevant information from a database and generating answers using a language model.

## Tech Stack

**Backend:** FastAPI, Python  
**Frontend:** Streamlit  
**Database:** MySQL  
**Database Connector:** aiomysql  
**LLM Integration:** Ollama / OpenAI-compatible API  
**Other Tools:** REST API, Git, GitHub

## Features

- FastAPI backend with REST API endpoint
- Streamlit-based user interface
- MySQL database integration
- Asynchronous database handling using aiomysql
- LLM-powered response generation
- Retrieval-Augmented Generation workflow
- User query processing through a `/chat` API endpoint
- Organized project structure for backend and frontend communication

## Project Structure

RAG-Agent/
├── main.py
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── ...

How to Run
1. Clone the repository
git clone https://github.com/Shivangi-spec/RAG-Agent.git
cd RAG-Agent
2. Install dependencies
pip install -r requirements.txt
3. Create environment file
Create a .env file and add your required configuration values, such as database credentials and model settings.

Example:

DB_HOST=localhost
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=your_database
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=llama3

Do not upload the .env file to GitHub.

4. Run the FastAPI backend
uvicorn main:app --reload

The backend will usually run on: http://127.0.0.1:8000

5. Run the Streamlit frontend
Open a new terminal and run: streamlit run app.py

API Endpoint
The main API endpoint is: POST /chat

It accepts a user query and returns an LLM-generated response based on retrieved database context.

Purpose of the Project

The purpose of this project is to demonstrate a practical RAG-based AI assistant that connects a user interface, backend API, database, and language model together. It shows how LLMs can be combined with structured data retrieval to produce more relevant and context-aware responses.

What I Learned

Through this project, I gained hands-on experience in:

Building REST APIs using FastAPI
Creating a Streamlit frontend
Connecting Python applications with MySQL
Using asynchronous database operations with aiomysql
Integrating LLMs through an Ollama/OpenAI-compatible API
Structuring an AI application for real-world use
Using Git and GitHub for version control

Future Enhancements:
Add authentication for users
Improve document retrieval accuracy
Add support for PDF/document upload
Add conversation history
Improve UI design
Deploy the application online

Author: Shivangi Thakur
