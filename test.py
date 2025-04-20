# test_read.py
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import traceback

print("--- Starting Supabase Read Test ---")

# --- Load Environment Variables ---
print("Loading .env file...")
load_dotenv()
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY") # Ensure this is the SERVICE_ROLE key

print(f"Supabase URL loaded: {'Yes' if supabase_url else 'No - CHECK .env!'}")
print(f"Supabase Key loaded: {'Yes' if supabase_key else 'No - CHECK .env!'}")

if not supabase_url or not supabase_key:
    print("FATAL: Credentials not loaded. Exiting.")
    exit()

# --- Initialize Client ---
supabase = None
try:
    print("Initializing Supabase client...")
    supabase: Client = create_client(supabase_url, supabase_key)
    print("Client initialized successfully.")
except Exception as client_err:
    print("\n!!! FAILED TO INITIALIZE CLIENT !!!")
    traceback.print_exc()
    exit()

# --- Perform Test Select ---
if supabase:
    # Test 1: Read from 'site_reviews'
    table_to_test = 'site_reviews' # CHANGE if this table doesn't exist or has no data
    print(f"\n--- Attempting to read from '{table_to_test}' table ---")
    try:
        # Simplest Select: Get all columns for first 5 rows
        response = supabase.table(table_to_test).select('*').limit(5).execute()

        print("\n--- RAW Response Object ---")
        # Use vars() to see attributes, safer than assuming specific structure
        try:
            print(vars(response))
        except TypeError:
            print(response) # Print directly if vars() fails

        print("\n--- Response Analysis ---")
        # Check for common attributes expected from supabase-py
        if hasattr(response, 'data'):
             print(f"Found 'data' attribute. Length: {len(response.data)}")
             print(f"Data content: {response.data}")
        else:
             print("'data' attribute MISSING from response.")

        if hasattr(response, 'error') and response.error:
             print(f"Found 'error' attribute: {response.error}")
        else:
            print("'error' attribute not found or is None/False.")

        if hasattr(response, 'status_code'): # Older versions might have this
             print(f"Found 'status_code' attribute: {response.status_code}")

        # Add check for PostgrestResponse attributes if needed
        if 'model_dump' in dir(response): # Check for newer pydantic model response
             print(f"Response model dump: {response.model_dump()}")


    except Exception as select_err:
        print(f"\n!!! EXCEPTION during SELECT on '{table_to_test}' !!!")
        traceback.print_exc()

    # Test 2: Read from 'reviews' for specific doctor_id (Optional)
    # doctor_table = 'reviews'
    # known_doctor_id = 1 # <<< Change this ID if needed
    # print(f"\n--- Attempting to read from '{doctor_table}' for doctor_id={known_doctor_id} ---")
    # try:
    #      response_doc = supabase.table(doctor_table).select('*').eq('doctor_id', known_doctor_id).limit(5).execute()
    #      print("\n--- RAW Response Object (Doctor Reviews) ---")
    #      try: print(vars(response_doc))
    #      except TypeError: print(response_doc)
    #      # ... (Analysis similar to above) ...
    # except Exception as select_err_doc:
    #      print(f"\n!!! EXCEPTION during SELECT on '{doctor_table}' !!!")
    #      traceback.print_exc()


print("\n--- Test Script Finished ---")