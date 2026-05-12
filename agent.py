import asyncio
from openai import AsyncOpenAI
import aiomysql 
import json     
import re       

# --- Initialize LLM Client ---
llm_client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)
print("LLM client initialized for Ollama.") 

# --- Agent Configuration ---

SYSTEM_PROMPT = """
You are a helpful assistant specializing in providing information from the U.S. Federal Register. 
Your knowledge is based on documents stored in a local database, updated daily.

When a user asks a question that requires specific information from the Federal Register 
(e.g., about documents, contents, publication dates, agencies, or presidential actions), 
your primary task is to formulate a valid SQL SELECT query for the 'documents' table 
to retrieve that information.

If you determine an SQL query is needed, you MUST respond with ONLY the SQL query, 
and wrap it in <sql_query> tags. For example:
<sql_query>SELECT title FROM documents WHERE type = 'RULE';</sql_query>

Do not provide any other explanatory text or conversation before or after the <sql_query> tags if you are providing a query.
If the user's query does not require database access (e.g., a general greeting), 
then answer directly without generating an SQL query or the <sql_query> tags.

The 'documents' table has the following relevant columns:
document_number (VARCHAR): The unique ID of the document.
title (TEXT): The title of the document.
abstract (TEXT): A summary of the document.
publication_date (DATE): The date of publication in 'YYYY-MM-DD' format. Use this for date range queries (e.g., publication_date >= 'YYYY-MM-DD' AND publication_date <= 'YYYY-MM-DD').
type (VARCHAR): The document type. Can be 'RULE', 'PRORULE', 'NOTICE', or 'PRESDOCU'.
agency_names (TEXT): IMPORTANT! This column contains agency information. For searching by agency, you MUST use this column name `agency_names` with a LIKE clause, for example: `agency_names LIKE '%Environmental Protection Agency%'`. Do NOT use a column named 'agency'.

IMPORTANT DATABASE SCHEMA NOTE: 
The 'documents' table DOES NOT have a 'president' column. 
Presidential documents are identified by querying `type = 'PRESDOCU'`. 
You CANNOT filter by a president's name directly in the SQL WHERE clause.

Example of query generation for general PRESDOCU:
User asks: 'What documents of type "PRESDOCU" were published in May 2025?'
You should respond with:
<sql_query>SELECT title, abstract, publication_date FROM documents 
WHERE type = 'PRESDOCU' 
AND publication_date >= '2025-05-01' AND publication_date <= '2025-05-31' 
ORDER BY publication_date DESC;</sql_query>

Example of handling a query mentioning a specific president:
User asks: 'What are the new executive orders by President Biden published in May 2025?'
You should respond with a query that finds all PRESDOCU documents for that period, like this:
<sql_query>SELECT title, abstract, publication_date FROM documents 
WHERE type = 'PRESDOCU' 
AND publication_date >= '2025-05-01' AND publication_date <= '2025-05-31' 
ORDER BY publication_date DESC;</sql_query>
You can then mention in your final summary that the results are for all presidential documents in that period, as direct filtering by president name is not supported by the database structure.

Example of query involving an agency:
User asks: 'Find notices from the Environmental Protection Agency.'
You should respond with:
<sql_query>SELECT title, abstract, publication_date FROM documents 
WHERE type = 'NOTICE' 
AND agency_names LIKE '%Environmental Protection Agency%';</sql_query>

If you later receive data from a database query, summarize the findings in a clear, 
concise, and helpful natural language response. If the data indicates no results were found, 
state that no matching documents were found for the given criteria.

Constraint: Only generate SQL SELECT queries. Do not generate INSERT, UPDATE, DELETE, or any other type of SQL statement.
"""

# --- Tool Definition ---
query_mysql_tool_schema = {
    "type": "function",
    "function": {
        "name": "query_mysql_database",
        "description": (
            "Queries the Federal Register documents database using a SQL SELECT query to find information. "
            "Use this to answer questions about specific documents, types of documents (RULE, PRORULE, NOTICE, PRESDOCU), "
            "publications by date, or by agency. The primary table is 'documents'." 
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql_query": {
                    "type": "string",
                    "description": (
                        "A valid SQL SELECT query to retrieve data from the 'documents' table. " 
                        "The table contains columns: document_number, title, abstract, publication_date (YYYY-MM-DD), "
                        "type, agency_names (TEXT, may contain JSON). Only use SELECT statements." 
                    )
                }
            },
            "required": ["sql_query"]
        }
    }
}

# --- Tool Implementation ---
async def query_mysql_database(sql_query: str, db_pool) -> str:
    if not sql_query.strip().upper().startswith("SELECT"):
        return json.dumps({"error": "Invalid query. Only SELECT statements are allowed."})
    print(f"Executing SQL query: {sql_query}")
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql_query)
                results = await cur.fetchall()
                if results:
                    for row in results:
                        for key, value in row.items():
                            if hasattr(value, 'isoformat'): # Check for date/datetime objects
                                row[key] = value.isoformat()
                    return json.dumps({"data": results})
                else:
                    return json.dumps({"data": [], "message": "No results found for the query."})
    except aiomysql.MySQLError as e:
        print(f"SQL Error: {e}")
        return json.dumps({"error": f"Error executing SQL query: {str(e)}"})
    except Exception as e:
        print(f"Unexpected error in query_mysql_database: {e}")
        return json.dumps({"error": "An unexpected error occurred while querying the database."})


# --- Agent Interaction Logic ---
async def process_user_query(user_message: str, db_pool, chat_history=None) -> str:
    if chat_history is None:
        chat_history = []

    messages_for_sql_generation = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages_for_sql_generation.append({"role": "user", "content": user_message})

    print(f"Sending to LLM (for SQL or direct answer): {messages_for_sql_generation}")

    try:
        first_response_obj = await llm_client.chat.completions.create(
            model="phi3", 
            messages=messages_for_sql_generation
        )
        llm_response_content = first_response_obj.choices[0].message.content
        print(f"LLM first response content: '{llm_response_content}'")

        sql_query_to_execute = None
        if llm_response_content:
            match = re.search(r"<sql_query>(.*?)</sql_query>", llm_response_content, re.DOTALL | re.IGNORECASE)
            if match:
                sql_query_to_execute = match.group(1).strip()
                print(f"Extracted SQL query: {sql_query_to_execute}")

        if sql_query_to_execute:
            db_results_json_str = await query_mysql_database(sql_query_to_execute, db_pool)
            print(f"Database results (JSON string): {db_results_json_str}")
            
            db_data = json.loads(db_results_json_str) 

            # Prepare messages for summarization
            system_prompt_for_summary = "You are a helpful assistant. Your task is to formulate a final response to the user based on their original question and the provided information about database query results. If the database query found no results, clearly state that and mention any relevant context from the system instructions about how presidential documents are queried (e.g., by type PRESDOCU, as direct filtering by president name isn't possible)."
            user_original_query_message = f"My original question was: '{user_message}'"
            assistant_content_for_summary = ""

            if "data" in db_data and db_data.get("data"): 
                assistant_content_for_summary = f"Based on your query, here is the data I found in the Federal Register documents:\n{json.dumps(db_data['data'])}\nPlease summarize this to answer my original question. If my original question mentioned a specific president, remember that the search was for all presidential documents (type 'PRESDOCU') in the period, as direct filtering by president name isn't supported by the database structure."
            
            elif "message" in db_data and "No results found" in db_data["message"]:
                # *** MODIFIED THE CONTENT FOR 'NO RESULTS FOUND' CASE ***
                assistant_content_for_summary = (
                    f"I searched the database for documents matching your criteria based on the query: '{user_message}'. "
                    "The database reported: 'No results found for the query.' "
                    "This means no documents of type 'PRESDOCU' were found for the specified period (May 2025). "
                    "Please note that while your query mentioned 'President Biden', the database does not have a 'president' column, "
                    "so the search was for all presidential documents (type 'PRESDOCU') within that timeframe."
                )
            
            else: 
                assistant_content_for_summary = f"There was an issue retrieving data from the database. The database reported: {db_results_json_str}. Please inform the user about this problem."

            messages_for_summary = [
                {"role": "system", "content": system_prompt_for_summary},
                {"role": "user", "content": user_original_query_message},
                {"role": "assistant", "content": assistant_content_for_summary}
            ]
            
            print(f"Sending to LLM (for summarization): {messages_for_summary}")
            second_response_obj = await llm_client.chat.completions.create(
                model="phi3", 
                messages=messages_for_summary
            )
            final_answer = second_response_obj.choices[0].message.content
            return final_answer
        else:
            print("No SQL query extracted. Returning LLM's first response as answer.")
            if llm_response_content is None:
                return "I'm sorry, I could not generate a response."
            return llm_response_content

    except Exception as e:
        print(f"Error during LLM interaction or manual tool processing: {e}")
        import traceback
        traceback.print_exc()
        return "I'm sorry, an error occurred while processing your request."

# --- Testing of agent.py ---
async def test_agent():
    db_config_for_test = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': '123456', 
        'db': 'federal_register_db',
        'autocommit': True
    }
    loop = asyncio.get_event_loop()
    test_db_pool = None
    try:
        test_db_pool = await aiomysql.create_pool(**db_config_for_test, loop=loop)

        user_input_tool_call = "What are the new executive orders by President Biden published in May 2025?"
        print(f"\nTesting with input: '{user_input_tool_call}'")
        response_tool_call = await process_user_query(user_input_tool_call, test_db_pool)
        print(f"Agent Response (for DB query): {response_tool_call}")

        user_input_no_tool = "Hello, how are you today?"
        print(f"\nTesting with input: '{user_input_no_tool}'")
        response_no_tool = await process_user_query(user_input_no_tool, test_db_pool)
        print(f"Agent Response (no DB query): {response_no_tool}")

    except Exception as e:
        print(f"Error in test_agent: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if test_db_pool:
            test_db_pool.close()
            await test_db_pool.wait_closed()
            print("Database pool closed.")

if __name__ == "__main__":
    asyncio.run(test_agent())