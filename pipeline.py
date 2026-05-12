import asyncio
import aiohttp
import aiomysql
import json
from datetime import date, timedelta, datetime 

# --- Configuration ---
# Federal Register API
API_BASE_URL = "https://www.federalregister.gov/api/v1/documents.json"
FIELDS_TO_FETCH = [
    "document_number", "title", "abstract", "publication_date",
    "type", "agency_names", "html_url", "pdf_url", "raw_text_url"
]

# MySQL Database Connection Details
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456', 
    'db': 'federal_register_db',
    'autocommit': True
}

# Directory to store raw downloaded JSON data
RAW_DATA_DIR = "./raw_federal_register_data"


# --- Ensure raw data directory exists ---
import os
os.makedirs(RAW_DATA_DIR, exist_ok=True)


# --- Fetch Data from Federal Register API ---
async def fetch_federal_register_data(session, publication_date_str):
    params = {
        "per_page": 1000,
        "page": 1,
        "conditions[publication_date][is]": publication_date_str,
        "fields[]": FIELDS_TO_FETCH
    }
    all_results = []
    print(f"Fetching data for publication date: {publication_date_str}...")

    while True:
        try:
            async with session.get(API_BASE_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json()

                if not data.get("results"):
                    print(f"No results found for page {params['page']} on {publication_date_str}.")
                    break

                all_results.extend(data["results"])
                print(f"Fetched page {params['page']}: {len(data['results'])} documents.")

                if data.get("next_page_url"):
                    params["page"] += 1
                else:
                    break
        except aiohttp.ClientError as e:
            print(f"Error fetching data for {publication_date_str}, page {params['page']}: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for {publication_date_str}, page {params['page']}: {e}. Response text: {await response.text()[:200]}")
            break

    if all_results:
        raw_file_path = os.path.join(RAW_DATA_DIR, f"fr_data_{publication_date_str.replace('-', '_')}.json")
        with open(raw_file_path, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"Saved raw data for {publication_date_str} to {raw_file_path}")

    return all_results

# --- Process Data (largely handled by FIELDS_TO_FETCH) ---
# Minimal processing, focused on direct mapping.

# --- Store Data in MySQL ---
async def store_data_in_mysql(pool, documents):
    if not documents:
        print("No documents to store.")
        return

   
    # Ensures the SQL query matches the data being passed.
    if not isinstance(documents, list) or not documents:
        print("Documents data is not a non-empty list.")
        return

    sample_doc_keys = set(documents[0].keys())
    db_columns = [col for col in FIELDS_TO_FETCH if col in sample_doc_keys]

    if not db_columns:
        print("Error: No columns derived from FIELDS_TO_FETCH that match keys in fetched data.")
        return

    column_names_str = ", ".join([f"`{col}`" for col in db_columns])
    placeholders_str = ", ".join(["%s"] * len(db_columns))

    # Build the ON DUPLICATE KEY UPDATE part using the new alias syntax
    update_clauses = []
    for col in db_columns:
        if col != "document_number": # Don't update the primary key itself
            update_clauses.append(f"`{col}` = new_values.`{col}`")
    update_statements_str = ", ".join(update_clauses)

    sql_query = f"""
        INSERT INTO documents ({column_names_str})
        VALUES ({placeholders_str})
        AS new_values
        ON DUPLICATE KEY UPDATE {update_statements_str};
    """
    # print(f"SQL Query: {sql_query}") # For debugging

    records_to_insert = []
    for doc in documents:
        record_values = []
        valid_record = True
        for col_name in db_columns: # Iterate in the order of db_columns
            value = doc.get(col_name)
            if isinstance(value, list): # Example: convert list (like agency_names) to JSON string
                record_values.append(json.dumps(value))
            else:
                record_values.append(value)

        if len(record_values) == len(db_columns):
            records_to_insert.append(tuple(record_values))
        else:
            
            print(f"Skipping document {doc.get('document_number', 'N/A')} due to mismatched data for columns (expected {len(db_columns)}, got {len(record_values)}).")


    if not records_to_insert:
        print("No valid records to insert after processing.")
        return

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.executemany(sql_query, records_to_insert)
                # await conn.commit() # Not needed due to autocommit=True
                print(f"Successfully inserted/updated {cur.rowcount} documents.")
            except Exception as e:
                print(f"Database error: {e}")
                # For debugging, you might want to log the query and the first problematic record
                # print(f"Failed SQL Query: {sql_query}")
                # if records_to_insert:
                #     print(f"Problematic record (first one): {records_to_insert[0]}")


# --- Main Function ---
async def run_pipeline(start_date_str, end_date_str):
    pool = await aiomysql.create_pool(**DB_CONFIG, loop=asyncio.get_event_loop())

    async with aiohttp.ClientSession() as session:
        current_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        while current_date <= end_date:
            date_to_fetch_str = current_date.strftime("%Y-%m-%d")
            print(f"\n--- Processing data for {date_to_fetch_str} ---")

            documents_data = await fetch_federal_register_data(session, date_to_fetch_str)
            if documents_data:
                await store_data_in_mysql(pool, documents_data)
            else:
                print(f"No documents fetched for {date_to_fetch_str}.")

            current_date += timedelta(days=1)
            await asyncio.sleep(1) # Polite delay

    pool.close()
    await pool.wait_closed()
    print("\nPipeline run finished.")

# --- Entry Point ---
if __name__ == "__main__":
    start_date_pipeline = "2025-05-28"
    end_date_pipeline = "2025-05-30"

    print(f"Starting pipeline for dates: {start_date_pipeline} to {end_date_pipeline}")
    asyncio.run(run_pipeline(start_date_pipeline, end_date_pipeline))