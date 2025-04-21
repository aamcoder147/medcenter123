# --- START OF FILE app.py ---

# --- Standard Library Imports ---
import os                       # Used for accessing environment variables (like API keys, secrets).
import json                     # Used for handling JSON data, especially parsing availability strings.
import math                     # Used for mathematical functions, specifically ceiling for star ratings.
import traceback                # Used for getting detailed error information (stack traces).
from datetime import datetime, timedelta, date, time  # Used for handling dates and times for availability, bookings, comparisons.
from collections import defaultdict # Used for easily aggregating data, like counting reviews per doctor.
import uuid                     # Potentially for generating unique IDs, though not explicitly used in visible logic here.

# --- Third-Party Library Imports ---
from flask import (
    Flask,                  # The core Flask class to create the web application instance.
    render_template,        # Function to render HTML templates.
    # json, -> Duplicate, already imported above. Standard library 'json' is usually preferred.
    request,                # Object to access incoming request data (forms, query parameters, JSON).
    redirect,               # Function to redirect the user's browser to a different URL.
    url_for,                # Function to generate URLs for Flask routes dynamically.
    send_from_directory,    # Function to send a static file from a directory (not used here, but common).
    flash,                  # Function to display temporary messages (flashes) to the user.
    jsonify,                # Function to create a JSON response.
    make_response           # Function to create a custom Flask response object (e.g., to set headers).
)
# REMOVED: import sqlite3 -> Comment indicating SQLite3 is no longer needed as Supabase is used.
from flask_login import (
    LoginManager,           # Class to manage user sessions and authentication.
    UserMixin,              # Helper class for user models providing default Flask-Login implementations.
    current_user            # Proxy object representing the currently logged-in user (if using Flask-Login).
)
from supabase import create_client, Client # Imports Supabase client factory and type hint.
from dotenv import load_dotenv        # Function to load environment variables from a `.env` file.

# --- Environment Variable Loading ---
load_dotenv() # Executes the function to load variables from a `.env` file into the environment.

# --- Supabase Client Initialization ---
supabase_url: str = os.environ.get("SUPABASE_URL") # Retrieves the Supabase URL from environment variables. Type hint 'str'.
supabase_key: str = os.environ.get("SUPABASE_KEY") # Retrieves the Supabase service key from environment variables. Type hint 'str'.

# Check if Supabase credentials are set
if not supabase_url or not supabase_key:
    # Raise an error if the essential Supabase URL or key is missing in the environment.
    raise ValueError("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in the .env file")
else:
    # If credentials exist, try to initialize the Supabase client.
    try:
        # Create the Supabase client instance using the URL and key. Type hint 'Client'.
        supabase: Client = create_client(supabase_url, supabase_key)
        # Print a confirmation message upon successful initialization.
        print("Supabase client initialized.")
    except Exception as init_err:
        # If initialization fails, print a fatal error message.
        print(f"FATAL: Failed to initialize Supabase client: {init_err}")
        # Print the full traceback for detailed debugging of the initialization error.
        traceback.print_exc()
        # Re-raise the caught exception to halt the application if Supabase can't connect.
        raise init_err
# --- End Supabase Setup ---

# --- Flask Application Initialization ---
# Creates the Flask application instance.
# __name__ helps Flask locate templates and static files relative to this script.
# static_folder='static' explicitly sets the folder for static files (CSS, JS, images).
app = Flask(__name__, static_folder='static')

# --- Flask Secret Key Configuration ---
# Sets the secret key for the Flask application, required for session management and flash messages.
# It tries to get the key from the environment variable 'FLASK_SECRET_KEY'.
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
# Checks if the secret key was loaded successfully.
if not app.secret_key:
     # Prints a warning if the key isn't set, indicating a security risk (using a default).
     print("WARNING: FLASK_SECRET_KEY not set in environment. Using default (unsafe).")
     # Sets a default, insecure secret key if none was found in the environment. **Should be replaced in production.**
     app.secret_key = 'your_default_secret_key_12345' # UNSAFE - Change this immediately if deployed!

# --- Flask-Login Setup ---
# Initialize the LoginManager extension.
login_manager = LoginManager()
# Attach the LoginManager to the Flask app instance.
login_manager.init_app(app)

# Defines a simple User class required by Flask-Login.
# It inherits from UserMixin for default implementations (like is_authenticated).
class User(UserMixin):
    # The constructor takes a user ID.
    def __init__(self, id):
        # Stores the user ID.
        self.id = id

# Decorator that tells Flask-Login how to load a user object from a user ID stored in the session.
@login_manager.user_loader
# Function called by Flask-Login to retrieve a user by ID.
def load_user(user_id):
    # If a user_id exists in the session cookie...
    if user_id:
        # ...create a User object with that ID and return it.
        # In a real app, this would likely involve querying the database for user details.
        return User(user_id)
    # If no user_id is found, return None.
    return None
# --- End Login Manager Setup ---

# --- Helper Functions ---

# Function to safely parse availability data, which might be a dict or a JSON string.
def parse_availability(raw_availability, doctor_id_for_log="Unknown"):
    """Safely parses availability data, expecting dict or JSON string, returns dict."""
    # Check if the input is already a dictionary.
    if isinstance(raw_availability, dict):
        # If it is, return it directly. (DEBUG print commented out)
        # print(f"DEBUG (parse_availability): Dr {doctor_id_for_log} - Availability is already a dict.")
        return raw_availability
    # Check if the input is a string.
    elif isinstance(raw_availability, str):
        # If it's a string, try to parse it as JSON.
        try:
            # Attempt to load the string as JSON.
            parsed_avail = json.loads(raw_availability)
            # Check if the parsed result is actually a dictionary.
            if isinstance(parsed_avail, dict):
                 # If parsing successful and it's a dict, return it. Print warning suggesting DB change. (WARN print commented out)
                 # print(f"WARN (parse_availability): Dr {doctor_id_for_log} - Parsed availability string to dict. Recommend DB column type JSON/JSONB.")
                 return parsed_avail
            else:
                 # If parsing succeeded but it's not a dict, log an error and return empty dict.
                 print(f"ERROR (parse_availability): Dr {doctor_id_for_log} - Parsed availability string is not a dict ({type(parsed_avail)}). Returning empty.")
                 return {}
        # Handle errors during JSON parsing (e.g., invalid format).
        except json.JSONDecodeError:
            # Log an error if the string couldn't be parsed as JSON and return empty dict.
            print(f"ERROR (parse_availability): Dr {doctor_id_for_log} - Failed to parse availability JSON string: '{raw_availability[:100]}...'. Returning empty.")
            return {}
    # If the input is neither a dict nor a string.
    else:
         # Log a warning and return an empty dictionary. (WARN print commented out)
         # print(f"WARN (parse_availability): Dr {doctor_id_for_log} - Availability is not dict or string (type: {type(raw_availability)}). Returning empty.")
         return {}

# Function to load doctor data from the Supabase 'doctors' table.
def load_doctors_from_db():
    """Fetches doctors from Supabase, parses availability, and calculates average rating."""
    # Print a message indicating the start of the loading process.
    print("Loading doctors data from Supabase...")
    # Initialize an empty list to hold doctor data.
    doctors_list = []
    # Start a try block to handle potential database errors.
    try:
        # Query Supabase 'doctors' table, selecting all columns ('*').
        # Order the results by the 'name' column in ascending order (desc=False).
        response_docs = supabase.table('doctors').select('*').order('name', desc=False).execute()

        # Check if the query returned any data.
        if not response_docs.data:
            # If no doctors are found, print a warning and return an empty list.
            print("Warn: No doctors found in Supabase 'doctors' table.")
            return []

        # If data exists, assign it to the doctors_list.
        doctors_list = response_docs.data

        # Iterate through each doctor dictionary in the list.
        for doc in doctors_list:
            # Get the doctor's ID, defaulting to 'Unknown' if missing.
            doc_id = doc.get('id', 'Unknown')
            # Parse the 'availability' field using the helper function, handling potential JSON strings.
            doc['availability'] = parse_availability(doc.get('availability'), doc_id) # Use helper
            # Initialize the average rating for the doctor to 0.0.
            doc['average_rating'] = 0.0
            # Initialize the review count for the doctor to 0.
            doc['review_count'] = 0

        # Query the 'reviews' table to fetch ratings for ALL approved reviews.
        # Select only 'doctor_id' and 'rating' columns.
        # Filter for reviews where 'is_approved' is 1 (or True).
        response_reviews = supabase.table('reviews').select('doctor_id, rating').eq('is_approved', 1).execute()

        # Check if the reviews query returned any data.
        if response_reviews.data:
             # Initialize a defaultdict to aggregate ratings. Lambdas provide default {'total': 0, 'count': 0}.
             ratings_agg = defaultdict(lambda: {'total': 0, 'count': 0})
             # Iterate through each review dictionary.
             for review in response_reviews.data:
                  # Check if the review has both a 'rating' and a 'doctor_id'.
                  if review.get('rating') is not None and review.get('doctor_id') is not None:
                    # Try to convert the rating to a float and validate it's between 1 and 5.
                    try:
                        # Attempt conversion to float.
                        rating_val = float(review['rating'])
                        # Check if the rating is within the valid range (1-5).
                        if 1 <= rating_val <= 5:
                           # If valid, add the rating to the total for this doctor_id.
                           ratings_agg[review['doctor_id']]['total'] += rating_val
                           # Increment the count of reviews for this doctor_id.
                           ratings_agg[review['doctor_id']]['count'] += 1
                    # Handle cases where rating is not a number.
                    except (ValueError, TypeError):
                        # Print a warning if a rating is non-numeric and ignore it.
                        print(f"Warn: Non-numeric rating '{review['rating']}' for doctor {review['doctor_id']} ignored.")

             # Iterate through the doctors_list again to apply the calculated ratings.
             for doc in doctors_list:
                # Get the doctor's ID.
                doc_id = doc.get('id')
                # Check if the doctor's ID exists and has aggregated rating data.
                if doc_id and doc_id in ratings_agg:
                    # Get the aggregated data for this doctor.
                    agg_data = ratings_agg[doc_id]
                    # Set the 'review_count' based on the aggregated count.
                    doc['review_count'] = agg_data['count']
                    # Check if there are any reviews counted.
                    if agg_data['count'] > 0:
                         # Calculate and set the 'average_rating', rounding to one decimal place.
                         doc['average_rating'] = round(agg_data['total'] / agg_data['count'], 1)
                # If no rating data found for this doc, average_rating and review_count remain 0 (from initialization).

        # Print a summary message of the loaded data.
        print(f"Loaded {len(doctors_list)} doctors from Supabase with rating info.")
        # Return the list of doctors with processed availability and ratings.
        return doctors_list

    # Catch any exception during the Supabase interaction or data processing.
    except Exception as e:
        # Print a critical error message indicating failure to load doctor data.
        print(f"CRITICAL: Supabase error loading doctors data:")
        # Print the full traceback for debugging.
        traceback.print_exc()
        # Add a flash message to inform the user about the error loading data.
        # Tries to get a specific error message from the exception, otherwise uses the string representation.
        flash(f'Error loading doctor data from Supabase: {getattr(e, "message", str(e))}', 'error')
        # Return an empty list as the loading failed.
        return []

# Function to get the current doctor data, currently just calls load_doctors_from_db.
# This acts as a single point of access, potentially allowing for caching later.
def get_current_doctors_data():
    """ Central function to retrieve doctor data, potentially with caching later """
    # Call the function to fetch fresh data from the database.
    return load_doctors_from_db()

# --- Jinja Context Processor ---
# Decorator registers the function to run before rendering templates, making its return value available in the template context.
@app.context_processor
# Defines the utility processor function.
def utility_processor():
    # Defines the helper function 'get_stars' which will be available in Jinja templates.
    def get_stars(rating):
        """ Calculates a list of Font Awesome star classes based on a numerical rating (0-5). """
        # If rating is None, return 5 empty stars.
        if rating is None: return ['far fa-star'] * 5
        # Try to convert the rating to a float.
        try: rating_f = float(rating)
        # If conversion fails (e.g., non-numeric input), return 5 empty stars.
        except (ValueError, TypeError): return ['far fa-star'] * 5
        # If rating is negative, return 5 empty stars (treat as invalid).
        if rating_f < 0: return ['far fa-star'] * 5
        # Clamp the rating between 0 and 5.
        rating_f = max(0, min(5, rating_f))
        # Calculate the number of full stars using floor division.
        full = math.floor(rating_f)
        # Calculate if a half star is needed (if decimal part is >= 0.5).
        half = 1 if (rating_f - full) >= 0.5 else 0
        # Calculate the number of empty stars needed to reach 5 total.
        empty = 5 - full - half
        # Create the list of star classes: full, then half, then empty.
        stars = ['fas fa-star'] * full + ['fas fa-star-half-alt'] * half + ['far fa-star'] * empty
        # Ensure the list has exactly 5 elements (safeguard against calculation errors).
        while len(stars) < 5: stars.append('far fa-star')
        # Return the first 5 elements of the list (another safeguard).
        return stars[:5]
    # Return a dictionary mapping the function name 'get_stars' to the actual function.
    # This makes `get_stars(some_rating)` usable in Jinja templates.
    return dict(get_stars=get_stars)

# --- Helper Function: Get Doctor Availability (Specific Doctor) ---
# Function to retrieve availability data specifically for one doctor ID.
def get_doctor_availability_from_supabase(doctor_id):
     """Fetches and parses availability for a single doctor ID from Supabase."""
     # Print debug message indicating which doctor's availability is being fetched.
     print(f"DEBUG (Helper): Fetching availability for Dr {doctor_id}")
     # Try block to handle potential Supabase errors.
     try:
          # Query the 'doctors' table.
          # Select only the 'availability' column.
          # Filter where 'id' matches the provided doctor_id.
          # `maybe_single()` expects 0 or 1 results; returns None if 0, dict if 1. Avoids error on not found.
          response = supabase.table('doctors').select('availability').eq('id', doctor_id).maybe_single().execute()
          # Check if data was returned and the 'availability' field exists and is not None.
          if response.data and response.data.get('availability') is not None:
               # Parse the fetched availability data using the helper function.
               availability_data = parse_availability(response.data['availability'], doctor_id)
               # Print debug message confirming successful fetching and parsing.
               print(f"DEBUG (Helper): Dr {doctor_id} - Availability found and parsed.")
               # Return the parsed availability dictionary.
               return availability_data
          # If no data or availability field found.
          else:
               # Print a warning message.
               print(f"WARN (Helper): Dr {doctor_id} - No availability data found.")
               # Return an empty dictionary.
               return {}
     # Catch any exceptions during the Supabase query or parsing.
     except Exception as e:
          # Print an error message including the doctor ID.
          print(f"ERROR: Supabase helper error for Dr {doctor_id}:");
          # Print the full traceback for debugging.
          traceback.print_exc()
          # Return an empty dictionary indicating failure.
          return {}


# --- Flask Routes ---

# --- Route: Home Page ---
# Decorator maps the root URL ('/') to this function for GET requests (default).
@app.route('/')
# Function to handle requests to the home page.
def home():
    # Print separator and message indicating the route is being loaded.
    print("\n--- Loading '/' Home Route ---")
    # Fetch the current list of doctors (includes ratings) using the helper function.
    doctors_data = get_current_doctors_data()
    # Initialize a dictionary to hold various statistics for the site.
    stats = {
        'doctor_count': len(doctors_data),      # Number of doctors loaded.
        'specialty_count': 0,                   # Placeholder for unique specialty count.
        'total_bookings': 0,                    # Placeholder for total bookings ever made.
        'total_active_bookings': 0,             # Placeholder for non-cancelled bookings.
        'review_count': 0                       # Placeholder for total approved site reviews.
    }
    # Initialize empty lists for filter options and site reviews.
    specialties = []; governorates = []; facility_types = []; plcs = []; site_reviews = []

    # Check if any doctor data was successfully loaded.
    if doctors_data:
        # Try block to safely process doctor data for filters.
        try:
            # Create a set of unique specializations from doctors data (filtering out None/empty).
            # Convert to list and sort alphabetically.
            unique_specs = sorted(list({d.get('specialization') for d in doctors_data if d.get('specialization')}))
            # Create a set of unique governorates. Sort alphabetically.
            unique_govs = sorted(list({d.get('governorate') for d in doctors_data if d.get('governorate')}))
            # Create a set of unique facility types. Sort alphabetically.
            unique_fac_types = sorted(list({d.get('facility_type') for d in doctors_data if d.get('facility_type')}))
            # Create a set of unique PLCs (clinic names). Sort alphabetically.
            unique_plcs = sorted(list({d.get('plc') for d in doctors_data if d.get('plc')}))
            # Update the stats dictionary with the count of unique specialties.
            stats['specialty_count'] = len(unique_specs)
            # Assign the unique lists to the variables used by the template.
            specialties = unique_specs; governorates = unique_govs; facility_types = unique_fac_types; plcs = unique_plcs
        # Catch any exception during the processing of doctor data for filters.
        except Exception as e:
            # Print a warning if there's an error creating filter lists.
            print(f"Warn: Error processing doctors_data for filters: {e}")

    # --- Fetch Counts & Site Reviews from Supabase ---
    # Try block to handle potential errors during Supabase queries for stats and reviews.
    try:
        # Query 'bookings' table to count non-cancelled bookings.
        # `count='exact'` requests only the count, not the full rows.
        # `neq('status', 'Cancelled')` filters out cancelled bookings.
        response_active = supabase.table('bookings').select('id', count='exact').neq('status', 'Cancelled').execute()
        # Update stats with the active booking count (if the 'count' attribute exists). Default to 0.
        stats['total_active_bookings'] = response_active.count if hasattr(response_active, 'count') else 0

        # Query 'bookings' table to count ALL bookings (including cancelled).
        response_all = supabase.table('bookings').select('id', count='exact').execute()
        # Update stats with the total booking count. Default to 0.
        stats['total_bookings'] = response_all.count if hasattr(response_all, 'count') else 0

        # Query 'site_reviews' table for recent, approved reviews.
        response_site_reviews = supabase.table('site_reviews').select(
            'reviewer_name, rating, comment, created_at' # Specify columns needed.
            ).eq('is_approved', 1).order(              # Filter for approved reviews.
                'created_at', desc=True                 # Order by creation date, newest first.
            ).limit(3).execute()                        # Limit to the 3 most recent reviews.

        # Check if the site reviews query returned data.
        if response_site_reviews.data:
             # Assign the fetched review data to the site_reviews list.
             site_reviews = response_site_reviews.data
             # Fetch the TOTAL count of approved site reviews for the stats section.
             count_response = supabase.table('site_reviews').select('id', count='exact').eq('is_approved', 1).execute()
             # Update stats with the total approved site review count. Default to 0.
             stats['review_count'] = count_response.count if hasattr(count_response, 'count') else 0
             # Print debug message about fetched reviews.
             print(f"DEBUG: Fetched {len(site_reviews)} recent site reviews (Total approved: {stats['review_count']}).")
        # If no approved site reviews were found.
        else:
             # Print debug message indicating no reviews found.
             print("DEBUG: No approved site reviews found.")
             # Check if there was an error object in the response (even if data is empty).
             if hasattr(response_site_reviews, 'error') and response_site_reviews.error:
                   # Print details about the fetch error.
                   print(f"DEBUG: Site reviews fetch error detail: {response_site_reviews.error}")
                   # Add a flash message for the user about the error.
                   flash('Error fetching site reviews.', 'error')

    # Catch any exception during the stats/site review fetching process.
    except Exception as e:
        # Print error message.
        print(f"ERROR: Exception while fetching stats/site reviews for home:")
        # Print the full traceback.
        traceback.print_exc()
        # Add a flash message indicating failure to load stats/reviews.
        flash('Could not load current statistics or site reviews.', 'warning')

    # Render the 'index.html' template, passing all collected data.
    return render_template(
        'index.html',                           # The template file to render.
        doctors=doctors_data,                   # Pass the list of doctors.
        stats=stats,                            # Pass the dictionary of statistics.
        specialties=specialties,                # Pass the list of unique specialties.
        governorates=governorates,              # Pass the list of unique governorates.
        facility_types=facility_types,          # Pass the list of unique facility types.
        plcs=plcs,                              # Pass the list of unique clinic names.
        site_reviews=site_reviews               # Pass the list of recent site reviews.
    )

# --- Route: Submit Site Review ---
# Decorator maps '/submit-site-review' URL to this function, only for POST requests.
@app.route('/submit-site-review', methods=['POST'])
# Function to handle the submission of the site-wide review form.
def submit_site_review():
    # Get reviewer's name from form data, remove leading/trailing whitespace, default to empty string.
    reviewer_name = request.form.get('reviewer_name', '').strip()
    # Get the rating value (string) from form data.
    rating_str = request.form.get('rating')
    # Get the comment from form data, remove whitespace, default to empty string.
    comment = request.form.get('comment', '').strip()

    # Initialize an empty list to store validation errors.
    errors = []
    # Initialize rating variable to None.
    rating = None
    # Check if reviewer name is empty.
    if not reviewer_name:
        # Add error message if name is missing.
        errors.append('Your name is required.')
    # Try to validate the rating.
    try:
        # Convert rating string to an integer.
        rating = int(rating_str)
        # Check if the integer rating is outside the valid range (1-5).
        if not (1 <= rating <= 5):
            # Add error message if rating is invalid.
            errors.append('Valid rating (1-5 stars) required.')
    # Catch exceptions if rating_str is not a valid integer or is None/missing.
    except (ValueError, TypeError):
        # Add error message if rating conversion failed.
        errors.append('Valid rating (1-5 stars) required.')

    # Check if any validation errors occurred.
    if errors:
        # If errors exist, flash each error message to the user.
        for error in errors: flash(f'⛔ {error}', 'error')
        # Redirect the user back to the home page, specifically to the review form section using URL fragment.
        return redirect(url_for('home') + '#site-review-form-section')

    # If validation passed, try to insert the review into the database.
    try:
        # Create a dictionary payload for the Supabase insert operation.
        insert_payload = {
            'reviewer_name': reviewer_name, # User's name.
            'rating': rating,               # Validated rating (integer).
            'comment': comment,             # User's comment.
            'is_approved': 1                # Default to approved (1 means true/approved). Change to 0 for moderation.
        }
        # Execute the insert operation on the 'site_reviews' table with the payload.
        response = supabase.table('site_reviews').insert(insert_payload).execute()

        # Check if the insert operation returned data (usually indicates success).
        if response.data:
             # Log success message to console.
             print(f"Site review added by {reviewer_name} (Supabase).")
             # Flash a success message to the user.
             flash('✅ Thank you for your feedback!', 'success')
        # If insert did not return data or an error occurred.
        else:
            # Set a default error message.
            error_message = "Could not save review due to an unexpected issue."
            # Check if the response object has an 'error' attribute and it's not None.
            if hasattr(response, 'error') and response.error:
                # Construct a more specific error message using the Supabase error details.
                error_message = f"Could not save review: {response.error.get('message', 'Unknown DB error')}"
                # Log the detailed error from Supabase.
                print(f"ERROR: Supabase site review insert failed: {response.error}")
            # If no specific error object, log the generic failure.
            else:
                 print(f"Warn: Supabase site review insert for {reviewer_name} returned no data or unexpected structure. Response: {response}")
            # Flash the determined error message to the user.
            flash(f'⛔ {error_message}', 'error')

    # Catch any other unexpected exceptions during the process.
    except Exception as e:
        # Log the exception details.
        print(f"Error submitting site review to Supabase:")
        traceback.print_exc()
        # Try to get a specific message from the exception, otherwise use string representation.
        error_detail = getattr(e, 'message', str(e))
        # Flash a database error message to the user.
        flash(f'⛔ Database error submitting your feedback: {error_detail}', 'error')

    # Redirect the user back to the home page, specifically to the site reviews display section.
    return redirect(url_for('home') + '#site-reviews-section')


# --- Route: Submit Doctor Review ---
# Decorator maps '/submit-review' URL to this function, only for POST requests.
@app.route('/submit-review', methods=['POST'])
# Function to handle the submission of a review for a specific doctor.
def submit_review():
    # Print separator and message indicating route entry.
    print("\n--- Received POST to /submit-review ---")
    # Get the doctor's ID (string) from the form data.
    doctor_id_str = request.form.get('doctor_id')
    # Get the reviewer's name, strip whitespace, default to empty string.
    reviewer_name = request.form.get('reviewer_name', '').strip()
    # Get the reviewer's phone number, strip whitespace, default to empty string.
    reviewer_phone = request.form.get('reviewer_phone', '').strip()
    # Get the rating (string) from the form data.
    rating_str = request.form.get('rating')
    # Get the comment, strip whitespace, default to empty string.
    comment = request.form.get('comment', '').strip()

    # Print the received form data for debugging.
    print(f"DEBUG: Form Data - doctor_id='{doctor_id_str}', name='{reviewer_name}', phone='{reviewer_phone}', rating='{rating_str}'")

    # --- Basic Validation ---
    # Initialize empty list for errors, and None for parsed values.
    errors = []; doctor_id = None; rating = None
    # Try to convert doctor ID string to an integer.
    try: doctor_id = int(doctor_id_str)
    # Catch exceptions if conversion fails (e.g., not a number, or missing).
    except (ValueError, TypeError): errors.append('Invalid Doctor ID.')
    # Check if reviewer name is empty.
    if not reviewer_name: errors.append('Your name is required.')
    # Check if reviewer phone is empty.
    if not reviewer_phone: errors.append('Your phone number is required.')
    # Check if phone number contains only digits and has a length between 9 and 15.
    if not reviewer_phone.isdigit() or not (9 <= len(reviewer_phone) <= 15): errors.append('Valid phone number (9-15 digits) required.')
    # Try to validate the rating.
    try:
        # Convert rating string to integer.
        rating = int(rating_str)
        # Assert that the rating is between 1 and 5 (inclusive). Will raise AssertionError if false.
        assert 1 <= rating <= 5
    # Catch exceptions if not an integer, missing, or outside the 1-5 range.
    except (ValueError, TypeError, AssertionError): errors.append('Valid rating (1-5 stars) required.')

    # Check if any validation errors occurred.
    if errors:
        # Log the validation errors for debugging.
        print(f"DEBUG: Review Validation Errors: {errors}")
        # Flash each error message to the user.
        for error in errors: flash(f'⛔ {error}', 'error')
        # Determine the redirect URL: back to the booking page if doctor_id is known, otherwise to home.
        redirect_url = url_for('booking_page', doctor_id=doctor_id) if doctor_id else url_for('home')
        # Redirect the user back, ideally using the referrer header, or the determined redirect_url as fallback.
        return redirect(request.referrer or redirect_url)
    # --- End Validation ---

    # Start a try block for the main logic involving database checks and insertion.
    try:
        # Print debug message indicating the start of DB checks.
        print(f"DEBUG: Attempting review checks for Dr {doctor_id}, Reviewer {reviewer_name}/{reviewer_phone}")

        # *** CHECK 1: Has this person already reviewed this doctor? (Using TWO queries as OR isn't directly used here) ***
        # Print debug message for Check 1.
        print("DEBUG: Check 1 - Existing review?")
        # Initialize flag for existing review to False.
        review_exists = False
        # Start a nested try block for this specific database check.
        try:
            # Query 1a: Check if a review exists for this doctor_id matching the reviewer_name.
            # `select('id', count='exact')` efficiently checks existence without fetching full rows.
            res_name = supabase.table('reviews').select('id', count='exact') \
                .eq('doctor_id', doctor_id) \
                .eq('reviewer_name', reviewer_name) \
                .limit(1).execute() # Limit 1 as we only need to know if at least one exists.
            # Check if the query was successful and returned a count greater than 0.
            if hasattr(res_name, 'count') and res_name.count > 0:
                # If found by name, set the flag to True.
                review_exists = True

            # Query 1b: Only check by phone if no review was found by name.
            if not review_exists:
                 # Query 'reviews' table checking by doctor_id and reviewer_phone.
                 res_phone = supabase.table('reviews').select('id', count='exact') \
                     .eq('doctor_id', doctor_id) \
                     .eq('reviewer_phone', reviewer_phone) \
                     .limit(1).execute()
                 # Check if the phone query found a review.
                 if hasattr(res_phone, 'count') and res_phone.count > 0:
                     # If found by phone, set the flag to True.
                     review_exists = True

            # Print debug summary of Check 1 results. Checks if 'res_phone' exists locally before accessing count.
            print(f"DEBUG: Check 1 Response (Name Check: {res_name.count if hasattr(res_name, 'count') else 'ERR'}, Phone Check: {res_phone.count if 'res_phone' in locals() and hasattr(res_phone, 'count') else 'N/A'}) - Exists: {review_exists}")

        # Catch any exception during the existing review database checks.
        except Exception as check1_err:
            # Log the error and print traceback.
            print(f"ERROR: Exception during DB Check 1 (existing review): {check1_err}"); traceback.print_exc()
            # Flash an error message to the user.
            flash(f'⛔ Error checking existing reviews: {getattr(check1_err, "message", str(check1_err))}.', 'error')
            # Redirect back to the doctor's booking page.
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # If Check 1 determined a review already exists.
        if review_exists:
             # Flash an error message indicating a duplicate review attempt.
             flash('⛔ You have already reviewed this doctor using this name or phone number.', 'error')
             # Redirect back to the doctor's booking page.
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- END CHECK 1 ---

        # *** CHECK 2: Does a non-cancelled booking exist for this reviewer/doctor pair? (Find latest, uses TWO queries) ***
        # Print debug message for Check 2.
        print("DEBUG: Check 2 - Finding latest relevant booking...")
        # Initialize variable to store the latest relevant booking found.
        latest_booking = None
        # Start nested try block for the booking check queries.
        try:
            # Query 2a: Find the latest non-cancelled booking by doctor_id and patient_name.
            # Select booking date and time.
            bk_name_res = supabase.table('bookings') \
                .select('booking_date, booking_time') \
                .eq('doctor_id', doctor_id) \
                .eq('patient_name', reviewer_name) \
                .neq('status', 'Cancelled') \
                .order('booking_date', desc=True).order('booking_time', desc=True) \
                .limit(1).execute() # Limit 1 to get only the most recent.

            # Query 2b: Find the latest non-cancelled booking by doctor_id and patient_phone.
            bk_phone_res = supabase.table('bookings') \
                 .select('booking_date, booking_time') \
                 .eq('doctor_id', doctor_id) \
                 .eq('patient_phone', reviewer_phone) \
                 .neq('status', 'Cancelled') \
                 .order('booking_date', desc=True).order('booking_time', desc=True) \
                 .limit(1).execute()

            # Extract the first result if data exists for the name query, otherwise None.
            booking_by_name = bk_name_res.data[0] if bk_name_res.data else None
            # Extract the first result if data exists for the phone query, otherwise None.
            booking_by_phone = bk_phone_res.data[0] if bk_phone_res.data else None
            # Print debug messages showing the results found (or None).
            print(f"DEBUG: Latest booking by Name: {booking_by_name}")
            print(f"DEBUG: Latest booking by Phone: {booking_by_phone}")

            # Determine which booking is truly the latest if both name and phone found matches.
            if booking_by_name and booking_by_phone:
                 # Combine date and start time (taking only HH:MM part) into strings for comparison.
                 name_dt_str = f"{booking_by_name.get('booking_date')} {booking_by_name.get('booking_time', '').split('-')[0].strip()}"
                 phone_dt_str = f"{booking_by_phone.get('booking_date')} {booking_by_phone.get('booking_time', '').split('-')[0].strip()}"
                 # Try to parse these strings into datetime objects.
                 try:
                    # Parse name booking date/time.
                    name_dt = datetime.strptime(name_dt_str, '%Y-%m-%d %H:%M')
                    # Parse phone booking date/time.
                    phone_dt = datetime.strptime(phone_dt_str, '%Y-%m-%d %H:%M')
                    # Assign the later booking (or name booking if equal) to latest_booking.
                    latest_booking = booking_by_name if name_dt >= phone_dt else booking_by_phone
                 # Handle potential errors if time format is unexpected during parsing.
                 except ValueError:
                    # Default to the name booking if comparison parsing fails.
                    latest_booking = booking_by_name
            # If only a booking by name was found.
            elif booking_by_name:
                 # Assign it as the latest booking.
                 latest_booking = booking_by_name
            # If only a booking by phone was found.
            elif booking_by_phone:
                 # Assign it as the latest booking.
                 latest_booking = booking_by_phone
            # Else: latest_booking remains None if neither query found a match.

        # Catch exceptions during the latest booking check queries.
        except Exception as check2_err:
             # Log the error and print traceback.
             print(f"ERROR: Exception during DB Check 2 (latest booking): {check2_err}"); traceback.print_exc()
             # Flash error message to the user.
             flash(f'⛔ Error finding your booking: {getattr(check2_err, "message", str(check2_err))}.', 'error')
             # Redirect back to the booking page.
             return redirect(url_for('booking_page', doctor_id=doctor_id))

        # If no relevant non-cancelled booking was found after both checks.
        if not latest_booking:
             # Flash error message explaining a booking is required to review.
             flash('⛔ No non-cancelled booking found matching your name/phone for this doctor. Book first to review.', 'error')
             # Redirect back to the booking page.
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # Print the booking details that will be used for the time check.
        print(f"DEBUG: Using latest booking: {latest_booking}")
        # --- END CHECK 2 ---

        # *** CHECK 3: Has the appointment time already passed? ***
        # Print debug message for Check 3.
        print("DEBUG: Check 3 - Checking appointment time...")
        # Start a nested try block for parsing the booking time.
        try:
            # Get the booking date string from the found booking.
            booking_date_str = latest_booking.get('booking_date')
            # Get the booking time slot string (e.g., "HH:MM - HH:MM").
            booking_time_slot = latest_booking.get('booking_time')
            # Validate that necessary date/time parts exist and format seems correct. Raise ValueError if not.
            if not booking_date_str or not booking_time_slot or '-' not in booking_time_slot: raise ValueError("Invalid format")
            # Extract the start time part (HH:MM) from the slot string.
            booking_start_time_str = booking_time_slot.split('-')[0].strip()
            # Combine date and start time strings and parse into a datetime object.
            appointment_start_dt = datetime.strptime(f"{booking_date_str} {booking_start_time_str}", '%Y-%m-%d %H:%M')
            # Get the current date and time.
            now_dt = datetime.now()
            # Print comparison values for debugging.
            print(f"DEBUG: Comparing Now ({now_dt}) vs Appointment Start ({appointment_start_dt})")
            # Check if the current time is before the appointment start time.
            if now_dt < appointment_start_dt:
                # Format the appointment time nicely for the flash message.
                time_fmt = appointment_start_dt.strftime('%I:%M %p on %b %d, %Y')
                # Flash error message stating review is too early.
                flash(f'⛔ Cannot submit review until after your appointment starts ({time_fmt}).', 'error')
                # Redirect back to the booking page.
                return redirect(url_for('booking_page', doctor_id=doctor_id))
            # If current time is at or after the appointment start time.
            print("DEBUG: Appointment time passed.")
        # Catch exceptions during parsing or if keys are missing from latest_booking dict.
        except (ValueError, IndexError, TypeError, KeyError) as e:
             # Log the parsing error and print traceback.
             print(f"ERROR: Parsing latest booking time failed: {e}"); traceback.print_exc()
             # Flash a generic error message about time verification failure.
             flash('⛔ Could not verify appointment time. Contact support.', 'error')
             # Redirect back to the booking page.
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- END CHECK 3 ---

        # --- If all checks passed, Insert the Doctor Review ---
        # Print debug message indicating checks are complete.
        print("DEBUG: All review checks passed. Attempting insert...")
        # Prepare the data payload for the Supabase insert operation.
        insert_data = {
            'doctor_id': doctor_id,             # The doctor being reviewed.
            'reviewer_name': reviewer_name,     # Reviewer's name.
            'reviewer_phone': reviewer_phone,   # Reviewer's phone.
            'rating': rating,                   # The validated rating (1-5 integer).
            'comment': comment,                 # The review comment.
            'is_approved': 1                    # Set to 1 (approved) by default. Change to 0 for manual moderation queue.
        }
        # Print the data being sent to Supabase for debugging.
        print(f"DEBUG: Insert Review Data Payload: {insert_data}")
        # Execute the insert command on the 'reviews' table.
        insert_response = supabase.table('reviews').insert(insert_data).execute()
        # Print the response from Supabase after the insert attempt.
        print(f"DEBUG: Insert Review Response: {insert_response}")

        # Check if the insert response contains data (usually indicates success).
        if insert_response.data:
             # Flash a success message to the user.
             flash('✅ Thank you! Your review has been submitted.', 'success')
             # Log success message to the console.
             print(f"Doctor review added for Dr {doctor_id} by {reviewer_name}.")
        # Handle insert failure (no data returned or error object present).
        else:
             # Set a default failure message.
             error_message = "Failed to submit review (database issue)."
             # Try to extract specific error details from the response object.
             error_info = getattr(insert_response, 'error', None)
             # If an error object exists.
             if error_info:
                # Extract code, message, and details from the error object if available.
                error_code = getattr(error_info, 'code', None)
                error_msg = getattr(error_info, 'message', 'Unknown DB Error')
                error_details = getattr(error_info, 'details', '')
                # Log the detailed error information.
                print(f"ERROR: Supabase review insert failed: Code={error_code} Msg={error_msg} Details={error_details}")
                # Check for specific PostgreSQL error code 23505 (unique constraint violation).
                if error_code == '23505':
                    # Provide a more specific message if it's likely a duplicate entry constraint.
                    error_message = f"Review submission failed: Possible duplicate entry detected."
                # Otherwise, use the error message provided by Supabase.
                else: error_message = f"Review submission failed: {error_msg}"
             # If no specific error object, log a warning about the response structure.
             else: print(f"WARN: Supabase review insert no data. Response: {insert_response}")
             # Flash the determined error message to the user.
             flash(f'⛔ {error_message}', 'error')

    # Catch any unexpected exceptions in the main try block (outside specific checks).
    except Exception as e:
        # Log the error, including the doctor ID if available.
        print(f"ERROR submitting doctor review (Outer Catch) (Dr {doctor_id}):")
        # Print the full traceback.
        traceback.print_exc()
        # Flash a generic server error message to the user, including exception details if possible.
        flash(f'⛔ Server error submitting review: {getattr(e, "message", str(e))}.', 'error')

    # Print a message indicating the end of the submit_review request processing.
    print("--- /submit-review finished ---")
    # Redirect the user back to the booking page for the doctor they were reviewing.
    return redirect(url_for('booking_page', doctor_id=doctor_id))
# --- END OF REVISED submit_review ---

# --- Route: Doctor Booking Page ---
# Decorator maps '/booking/<integer:doctor_id>' URL to this function. It captures the ID.
@app.route('/booking/<int:doctor_id>')
# Function to display the booking page for a specific doctor.
def booking_page(doctor_id):
    # Print separator and message indicating the route is loading with the specific doctor ID.
    print(f"\n--- Loading Booking Page for Doctor ID: {doctor_id} ---")
    # Initialize variables to hold doctor data, reviews, and availability.
    doctor = None
    reviews = []
    doctor_availability_data = {} # Default to an empty dictionary.

    # --- Fetch Doctor Details directly from Supabase ---
    # Start a try block to handle potential errors fetching doctor data.
    try:
        # Print debug message.
        print("DEBUG: Fetching doctor details...")
        # Query the 'doctors' table, selecting all columns ('*').
        # Filter where 'id' equals the provided doctor_id.
        # `maybe_single()` returns the doctor dict if found, or None if not found (without error).
        doc_response = supabase.table('doctors').select('*').eq('id', doctor_id).maybe_single().execute()
        # Assign the found doctor data (or None) to the doctor variable.
        doctor = doc_response.data

        # Check if a doctor was actually found.
        if doctor:
             # Print debug message confirming the doctor was found.
             print(f"DEBUG: Doctor {doctor_id} found. Processing details...")
             # --- Availability Handling (Use Helper) ---
             # Parse the doctor's availability using the helper function. Passes the doctor_id for logging.
             doctor_availability_data = parse_availability(doctor.get('availability'), doctor_id)
             # Update the 'availability' key in the doctor dictionary with the *parsed* data (ensures it's a dict).
             doctor['availability'] = doctor_availability_data
             # Print the parsed availability data for debugging.
             print(f"DEBUG: Parsed availability for Dr {doctor_id}: {doctor_availability_data}")

             # --- Rating Calculation ---
             # Print debug message indicating rating calculation is starting.
             print("DEBUG: Calculating doctor rating...")
             # Query the 'reviews' table for ratings specific to this doctor.
             # Select only the 'rating' column.
             # Filter by 'doctor_id' and ensure reviews are approved ('is_approved' == 1).
             individual_ratings_response = supabase.table('reviews').select('rating').eq('doctor_id', doctor_id).eq('is_approved', 1).execute()
             # Check if the ratings query returned any data.
             if individual_ratings_response.data:
                 # Use a list comprehension to extract valid ratings.
                 # Checks if 'rating' key exists, is a number (int or float), and is between 1 and 5.
                 valid_ratings = [r['rating'] for r in individual_ratings_response.data if r.get('rating') is not None and isinstance(r.get('rating'), (int, float)) and 1 <= r.get('rating') <= 5]
                 # Count the number of valid ratings.
                 count = len(valid_ratings)
                 # Sum the valid ratings.
                 total_rating = sum(valid_ratings)
                 # Assign the count to the doctor's 'review_count'.
                 doctor['review_count'] = count
                 # Calculate the average rating if count > 0, round to 1 decimal place. Otherwise, set to 0.0.
                 doctor['average_rating'] = round(total_rating / count, 1) if count > 0 else 0.0
             # If no ratings were found for this doctor.
             else:
                 # Set review count and average rating to 0.
                 doctor['review_count'] = 0
                 doctor['average_rating'] = 0.0
             # Print the calculated rating and count for debugging.
             print(f"DEBUG: Rating calculated - Avg: {doctor.get('average_rating', 'N/A')}, Count: {doctor.get('review_count', 'N/A')}")

             # Fetch recent approved reviews for display on the page.
             # Print debug message.
             print(f"DEBUG: Fetching recent reviews for doctor {doctor_id}...")
             # Query the 'reviews' table again for display purposes.
             reviews_response = supabase.table('reviews').select(
                 'reviewer_name, rating, comment, created_at' # Select columns needed for display.
                 ).eq('doctor_id', doctor_id).eq('is_approved', 1).order( # Filter by doctor and approval status.
                     'created_at', desc=True                               # Order by newest first.
                 ).limit(10).execute()                                     # Limit to the latest 10 reviews.
             # Assign the fetched review data to the 'reviews' list (or an empty list if none found).
             reviews = reviews_response.data or []
             # Print the number of reviews fetched for display.
             print(f"DEBUG: Fetched {len(reviews)} reviews for display.")

        # If the initial query for the doctor returned None (doctor not found).
        else:
            # Log an error message.
            print(f"ERROR: Doctor with ID {doctor_id} not found.")
            # Flash an error message to the user.
            flash(f'⛔ Doctor with ID {doctor_id} not found.', 'error')
            # Redirect the user back to the home page.
            return redirect(url_for('home'))

    # Catch any exceptions during the database queries or data processing for the booking page.
    except Exception as e:
        # Log the error message and traceback.
        print(f"ERROR fetching booking page data for Dr {doctor_id}:"); traceback.print_exc()
        # Flash an error message to the user, including exception details if possible.
        flash(f'⛔ Error loading doctor details: {getattr(e, "message", str(e))}', 'error')
        # Redirect the user back to the home page.
        return redirect(url_for('home'))

    # Serialize the Python dictionary containing the doctor's availability schedule into a JSON string.
    # This is necessary to pass it safely into JavaScript code within the HTML template.
    doctor_availability_schedule_for_js = json.dumps(doctor_availability_data)
    # Print a debug message showing the type of data being passed (should be dict before dumps).
    print(f"DEBUG: Passing availability to booking.html (type: {type(doctor_availability_data)})") # Note: this prints type *before* json.dumps

    # Create a Flask response object by rendering the 'booking.html' template.
    # Pass the doctor object, doctor ID, parsed availability (as Python dict), and reviews list.
    # Note: The JSON string `doctor_availability_schedule_for_js` should be used within a <script> tag in booking.html,
    # likely assigning it to a JS variable like `var schedule = JSON.parse('{{ doctor_availability_schedule_for_js|safe }}');`
    # Or better yet, pass the original `doctor_availability_data` and let Jinja handle JSON conversion within the script tag:
    # `var schedule = {{ doctor_availability|tojson|safe }};`
    # Passing `doctor_availability_data` directly as `doctor_availability` is correct for use with `tojson` filter.
    response = make_response(render_template(
        'booking.html', doctor=doctor, doctor_id=doctor_id,
        doctor_availability=doctor_availability_data, # Pass the python dict here
        reviews=reviews
    ))
    # Set HTTP headers to prevent caching of this dynamic booking page.
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate' # HTTP 1.1.
    response.headers['Pragma'] = 'no-cache' # HTTP 1.0.
    response.headers['Expires'] = '0' # Proxies.
    # Print message indicating the end of the booking page loading process.
    print("--- Finished loading Booking Page data ---")
    # Return the constructed response object to the browser.
    return response

# --- Route: Center/Clinic Details Page ---
# Decorator maps '/center/<path:plc_name>' URL. 'path' allows slashes in the name.
@app.route('/center/<path:plc_name>')
# Function to display details for a specific clinic/center based on its name (PLC).
def center_details(plc_name):
    # Check if a plc_name was provided in the URL.
    if not plc_name:
        # If no name, flash an error and redirect home.
        flash('No clinic name provided.', 'error'); return redirect(url_for('home'))
    # Print separator and message indicating route load with the clinic name.
    print(f"--- Loading Center Details for: {plc_name} ---")
    # Initialize lists/dicts to hold data for this clinic.
    plc_doctors = []    # List of doctors at this PLC.
    plc_info = {}       # Dictionary for general info about the PLC.
    # Start try block for database operations.
    try:
        # Query 'doctors' table, selecting all columns ('*').
        # Filter where the 'plc' column exactly matches the provided plc_name.
        response = supabase.table('doctors').select('*').eq('plc', plc_name).execute()
        # Get the list of doctor data from the response.
        plc_doctors = response.data
        # Check if any doctors were found for this PLC name.
        if not plc_doctors:
             # If no doctors found, flash an informational message and redirect home.
             flash(f'Details not found for clinic/center "{plc_name}".', 'info')
             return redirect(url_for('home'))
        # --- Calculate Ratings for each doctor at this PLC ---
        # Iterate through the list of doctors found at this PLC.
        for doc in plc_doctors:
             # Get the doctor's ID.
             doc_id = doc.get('id')
             # If doctor ID is missing, set rating info to 0 and continue to next doctor.
             if not doc_id:
                 doc['review_count'] = 0; doc['average_rating'] = 0.0; continue
             # Query 'reviews' table to get the count of approved reviews for this doctor_id.
             rating_res = supabase.table('reviews').select('rating', count='exact').eq('doctor_id', doc_id).eq('is_approved', 1).execute()
             # Assign the count to the doctor's dictionary. Default to 0 if count attribute missing.
             doc['review_count'] = rating_res.count if hasattr(rating_res, 'count') else 0
             # Check if there are any reviews for this doctor.
             if doc['review_count'] > 0:
                  # If reviews exist, fetch the actual rating values to calculate the average.
                  avg_res = supabase.table('reviews').select('rating').eq('doctor_id', doc_id).eq('is_approved', 1).execute()
                  # Check if the query returned rating data.
                  if avg_res.data:
                      # Extract valid numerical ratings between 1 and 5.
                      valid_ratings = [r['rating'] for r in avg_res.data if r.get('rating') is not None and isinstance(r.get('rating'), (int, float)) and 1 <= r.get('rating') <= 5]
                      # Calculate average if valid ratings exist, otherwise 0.0. Round to 1 decimal.
                      doc['average_rating'] = round(sum(valid_ratings) / len(valid_ratings), 1) if valid_ratings else 0.0
                  # If fetching ratings failed or returned no data (shouldn't happen if count > 0, but defensive).
                  else: doc['average_rating'] = 0.0
             # If review_count was 0.
             else: doc['average_rating'] = 0.0
        # --- Gather PLC Information ---
        # Get the data of the first doctor in the list (assuming all doctors at a PLC share some basic info).
        first_doc = plc_doctors[0]
        # Create a sorted list of unique (governorate, province) tuples for all doctors at this PLC.
        # Filters out entries where both are None/empty.
        unique_locations = sorted(list({ (d.get('governorate', 'N/A'), d.get('province', 'N/A')) for d in plc_doctors if d.get('governorate') or d.get('province')}))
        # Populate the plc_info dictionary.
        plc_info = {
            'name': plc_name, # The name of the PLC from the URL.
            'facility_type': first_doc.get('facility_type', 'Clinic/Center'), # Get type from first doc, default if missing.
            'locations': unique_locations # Assign the list of unique locations.
        }
        # Generate a 'slug' for the PLC name to use in image paths.
        # Converts to lowercase, replaces spaces with underscores, removes some special chars.
        plc_slug = plc_name.lower().replace(' ', '_').replace('&', 'and').replace('.', '').replace("'", '')
        # Construct the expected path for the PLC's photo based on the generated slug.
        plc_info['photo_path_jpg'] = f'/static/plc_photos/{plc_slug}.jpg'
    # Catch any exceptions during database queries or data processing for the center details.
    except Exception as e:
        # Log the error, including the PLC name.
        print(f"ERROR: Supabase error fetching center '{plc_name}':"); traceback.print_exc()
        # Flash a generic error message to the user.
        flash('⛔ Error loading center details.', 'error')
        # Redirect back to the home page.
        return redirect(url_for('home'))
    # Render the 'center_details.html' template, passing PLC info and the list of doctors at that PLC.
    return render_template('center_details.html', plc=plc_info, doctors=plc_doctors)


# --- API Route: Get Nearest Available Slot ---
# Decorator maps '/get-nearest-available/<integer:doctor_id>' URL to this API endpoint.
@app.route('/get-nearest-available/<int:doctor_id>')
# Function to find the soonest available (unbooked) slot for a given doctor.
def get_nearest_available(doctor_id):
    # Print debug message indicating API call with doctor ID.
    print(f"DEBUG: API call /get-nearest-available/ for Dr {doctor_id}")
    # Fetch the doctor's availability schedule using the helper function.
    doctor_availability = get_doctor_availability_from_supabase(doctor_id)
    # Check if the availability schedule was successfully loaded and is not empty.
    if not doctor_availability:
        # If no schedule found, return a JSON response indicating failure and a 404 status code.
        return jsonify({'success': False, 'message': 'Doctor schedule is currently unavailable.'}), 404
    # Get today's date object.
    today_date = date.today()
    # Get the current time object.
    now_time = datetime.now().time()
    # Print current date and time for debugging context.
    print(f"DEBUG: Current date: {today_date}, time: {now_time}")
    # Start a try block for the logic of finding the nearest slot.
    try:
        # Loop through the next 90 days (including today).
        for i in range(90):
            # Calculate the date being checked in this iteration.
            current_check_date = today_date + timedelta(days=i)
            # Format the check date as 'YYYY-MM-DD'.
            date_str = current_check_date.strftime('%Y-%m-%d')
            # Get the name of the day (e.g., 'Monday').
            day_name = current_check_date.strftime('%A')
            # Get the list of generally available slots for this day name from the schedule. Default to empty list.
            general_slots_raw = doctor_availability.get(day_name, [])
            # Ensure the fetched slots data is actually a list before proceeding.
            if not isinstance(general_slots_raw, list): continue # Skip if format is wrong.
            # Filter and sort the raw slots: keep only valid strings ("HH:MM - HH:MM", not "unavailable").
            general_slots = sorted([s for s in general_slots_raw if isinstance(s, str) and '-' in s and ':' in s and s.strip().lower() != "unavailable"])
            # If no valid general slots exist for this day, continue to the next day.
            if not general_slots: continue
            # Query Supabase 'bookings' table to find times already booked for this doctor on this specific date.
            response_booked = supabase.table('bookings').select('booking_time').eq('doctor_id', doctor_id).eq('booking_date', date_str).neq('status', 'Cancelled').execute()
            # Create a set of booked time slots for efficient lookup. If no bookings, create an empty set.
            booked_times = {row['booking_time'] for row in response_booked.data} if response_booked.data else set()
            # Iterate through the sorted, generally available slots for the day.
            for slot in general_slots:
                # Check if this generally available slot is NOT in the set of booked times.
                if slot not in booked_times:
                    # Initialize variable for the slot's start time.
                    slot_start_time = None
                    # Try to parse the start time (HH:MM) from the slot string.
                    try:
                        slot_start_str = slot.split('-')[0].strip(); slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                    # Handle errors if parsing fails (e.g., unexpected format).
                    except (ValueError, IndexError) as time_parse_err:
                        print(f"ERROR: Parse near slot '{slot}': {time_parse_err}. Skipping."); continue # Log error and skip this slot.
                    # Check if the current check date is today.
                    if current_check_date == today_date:
                        # If it's today, check if the slot's start time is in the future compared to now.
                        if slot_start_time > now_time:
                            # If found the first future slot for today, return success with date and time.
                            print(f"SUCCESS: Found nearest (Today): {date_str} {slot}"); return jsonify({'success': True, 'date': date_str, 'time': slot})
                    # If the current check date is a future date.
                    else:
                        # Any available slot on a future date is the nearest, return success.
                        print(f"SUCCESS: Found nearest (Future): {date_str} {slot}"); return jsonify({'success': True, 'date': date_str, 'time': slot})
        # If the loop completes without finding any available slot within 90 days.
        print(f"INFO: Loop finished. No slots found near for Dr {doctor_id}.")
        # Return a JSON response indicating no slots found soon, with a 404 status code.
        return jsonify({'success': False, 'message': 'No available slots found soon.'}), 404
    # Catch any unexpected exceptions during the slot finding logic.
    except Exception as e:
        # Log the error, including doctor ID.
        print(f"ERROR in get_nearest_available logic for Dr {doctor_id}:"); traceback.print_exc()
        # Return a JSON response indicating a server error, with a 500 status code.
        return jsonify({'success': False, 'message': f'Internal server error searching.'}), 500

# --- API Route: Get Available Slots for a Specific Date ---
# Decorator maps '/get-available-slots/<integer:doctor_id>/<string:date_str>' URL.
@app.route('/get-available-slots/<int:doctor_id>/<string:date_str>')
# Function to return a list of available (unbooked) time slots for a specific doctor on a specific date.
def get_available_slots(doctor_id, date_str):
    # Print debug message indicating API call with doctor ID and date.
    print(f"DEBUG: API call /get-available-slots/ Dr {doctor_id} on {date_str}")
    # Try to parse the input date string into a date object.
    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        # Get the name of the day (e.g., 'Monday') from the parsed date.
        day_name = booking_date.strftime('%A')
    # Handle error if the date string is not in the expected 'YYYY-MM-DD' format.
    except ValueError:
        print(f"ERROR: Invalid date format: {date_str}"); return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400 # Return 400 Bad Request.
    # Fetch the doctor's availability schedule using the helper function.
    doctor_availability = get_doctor_availability_from_supabase(doctor_id)
    # Check if a schedule was found.
    if not doctor_availability:
        print(f"WARN: No schedule found Dr {doctor_id} date {date_str}"); return jsonify([]) # Return empty list if no schedule.
    # Get the list of generally available slots for the specified day name. Default to empty list.
    general_slots_raw = doctor_availability.get(day_name, [])
    # Ensure the fetched schedule data for the day is a list.
    if not isinstance(general_slots_raw, list):
        print(f"WARN: Schedule not list {day_name}"); return jsonify([]) # Return empty list if format is wrong.
    # Filter and sort the raw slots: keep only valid strings ("HH:MM - HH:MM", not "unavailable").
    general_slots = sorted([ s for s in general_slots_raw if isinstance(s, str) and '-' in s and ':' in s and s.strip().lower() != "unavailable"])
    # Check if any general slots exist for this day after filtering.
    if not general_slots:
        print(f"DEBUG: No general slots {day_name}"); return jsonify([]) # Return empty list if none exist.
    # Try block for querying booked slots.
    try:
        # Query Supabase 'bookings' table for slots already booked for this doctor on this date.
        response_booked = supabase.table('bookings').select('booking_time').eq('doctor_id', doctor_id).eq('booking_date', date_str).neq('status', 'Cancelled').execute()
        # Create a set of booked time slot strings for efficient lookup.
        booked_times = {row['booking_time'] for row in response_booked.data} if response_booked.data else set()
        # Filter the general slots, keeping only those NOT present in the booked_times set.
        available_slots = [slot for slot in general_slots if slot not in booked_times]
        # Check if the requested date is today's date.
        if booking_date == date.today():
             # If it's today, filter out slots that have already passed.
             # Get the current time.
             now_time = datetime.now().time()
             # Initialize an empty list to hold future slots.
             future_slots = []
             # Iterate through the currently available slots for today.
             for slot in available_slots:
                # Try to parse the start time from the slot string.
                try:
                    slot_start_str = slot.split('-')[0].strip(); slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                # Handle potential parsing errors.
                except (ValueError, IndexError) as e:
                    print(f"ERROR: Parse slot '{slot}' today filter: {e}. Skipping."); continue # Log and skip this slot.
                # Check if the slot's start time is later than the current time.
                if slot_start_time > now_time:
                    # If it is, add it to the list of future slots.
                    future_slots.append(slot)
             # Replace the available_slots list with the filtered list containing only future slots.
             available_slots = future_slots
        # Print debug message showing the final list of available slots being returned.
        print(f"DEBUG: Returning {len(available_slots)} slots for {date_str}: {available_slots}")
        # Return the list of available slot strings as a JSON response.
        return jsonify(available_slots)
    # Catch exceptions during the Supabase query for booked times.
    except Exception as e:
        # Log the error, including doctor ID and date.
        print(f"ERROR: Supabase fetch booked times Dr {doctor_id} on {date_str}:"); traceback.print_exc()
        # Return a JSON error response with a 500 status code.
        return jsonify({'error': 'Database error fetching times.'}), 500

# --- Route: Confirm Booking ---
# Decorator maps '/confirm-booking' URL to this function, handling only POST requests.
@app.route('/confirm-booking', methods=['POST'])
# Function to handle the booking confirmation logic.
def confirm_booking():
    # Print separator and message indicating route entry.
    print("\n--- Received POST to /confirm-booking ---")
    # --- Get Data from the POST request form ---
    # Get doctor ID string.
    doctor_id_str = request.form.get('doctor_id')
    # Get patient name, strip whitespace, default to empty string.
    patient_name = request.form.get('patient_name', '').strip()
    # Get patient phone, strip whitespace, default to empty string.
    patient_phone = request.form.get('patient_phone', '').strip()
    # Get booking date string (expected YYYY-MM-DD).
    booking_date = request.form.get('booking_date')
    # Get booking time slot string (expected HH:MM - HH:MM).
    booking_time = request.form.get('booking_time')
    # Get optional notes, strip whitespace, default to empty string.
    notes = request.form.get('notes', '').strip()
    # Get browser fingerprint (likely from a client-side JS library).
    fingerprint = request.form.get('fingerprint')
    # Get a device ID potentially stored in a cookie.
    cookie_id = request.cookies.get('device_id')
    # Get the IP address of the client making the request.
    ip_address = request.remote_addr

    # Print the received form data for debugging.
    print(f"DEBUG: Form Data - DrID: {doctor_id_str}, Name: {patient_name}, Phone: {patient_phone}, Date: {booking_date}, Time: {booking_time}")

    # --- Basic Input Validation ---
    # Initialize list for validation errors.
    errors = []
    # Initialize variables for parsed values.
    doctor_id = None
    booking_date_obj = None
    slot_start_time = None

    # Validate Doctor ID.
    if not doctor_id_str or not doctor_id_str.isdigit():
        errors.append('Invalid Doctor ID.')
    else:
        # Convert valid doctor ID string to integer.
        doctor_id = int(doctor_id_str)
    # Validate Patient Name.
    if not patient_name: errors.append('Patient name is required.')
    # Validate Patient Phone.
    if not patient_phone: errors.append('Patient phone is required.')
    # Check if phone contains only digits and has length between 9 and 15.
    if not patient_phone.isdigit() or not (9 <= len(patient_phone) <= 15): errors.append('Valid phone number (9-15 digits) required.')
    # Validate Booking Date presence.
    if not booking_date: errors.append('Booking date is required.')
    # Validate Booking Time presence.
    if not booking_time: errors.append('Booking time slot is required.')

    # Validate Date Format and Past Date/Time (only if no previous errors).
    if not errors:
        # Try parsing the date and time.
        try:
            # Parse the booking date string into a date object.
            booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
            # Check if the selected date is in the past.
            if booking_date_obj < date.today():
                errors.append('Cannot book an appointment on a past date.')
            # Check if booking_time string seems valid (contains '-' and ':').
            if booking_time and '-' in booking_time and ':' in booking_time:
                 # Extract the start time part (HH:MM).
                 slot_start_str = booking_time.split('-')[0].strip()
                 # Parse the start time string into a time object.
                 slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                 # Check if the booking is for today AND the time slot has already passed.
                 if booking_date_obj == date.today() and slot_start_time <= datetime.now().time():
                     errors.append('Cannot book a time slot that has passed today.')
            # If booking_time format check failed.
            else: errors.append('Invalid booking time format.')
        # Catch error if date/time string format is incorrect.
        except ValueError: errors.append('Invalid date or time format.')

    # Check if any validation errors occurred during basic checks.
    if errors:
        # Log the validation errors.
        print(f"DEBUG: Validation Errors on Confirm: {errors}")
        # Flash each error message to the user.
        for error in errors: flash(f'⛔ {error}', 'error')
        # Determine redirect URL: back to booking page if doctor_id known, else home.
        redir_url = url_for('booking_page', doctor_id=doctor_id) if doctor_id else url_for('home')
        # Redirect back to the previous page (referrer) or the determined URL.
        return redirect(request.referrer or redir_url)
    # --- End Basic Validation ---

    # --- Slot Availability & Doctor Name Validation (against current schedule) ---
    # Initialize variable to store the fetched doctor's name.
    fetched_doctor_name = None
    # Initialize flag to track if the selected slot is valid according to the schedule.
    is_slot_valid = False
    # Start try block for fetching doctor schedule and validating the slot.
    try:
        # Print debug message indicating start of slot validation.
        print(f"DEBUG: Validating Slot Availability for Dr {doctor_id} on {booking_date} at {booking_time}")
        # Fetch the doctor's current availability schedule and name from the database.
        doc_response = supabase.table('doctors').select('availability, name').eq('id', doctor_id).maybe_single().execute()
        # Check if the doctor was found.
        if not doc_response.data:
            flash(f'⛔ Doctor {doctor_id} not found.', 'error'); return redirect(url_for('home'))
        # Get the doctor's name from the response data, default to 'Doctor' if missing.
        fetched_doctor_name = doc_response.data.get('name', 'Doctor')
        # Parse the fetched availability data using the helper function.
        current_schedule = parse_availability(doc_response.data.get('availability'), doctor_id)
        # Get the name of the day for the selected booking date (e.g., 'Monday').
        selected_day_name = booking_date_obj.strftime('%A')
        # Get the list of scheduled slots for that day from the parsed schedule. Default to empty list.
        day_schedule = current_schedule.get(selected_day_name, [])
        # Ensure the day's schedule is actually a list. Raise TypeError if not.
        if not isinstance(day_schedule, list): raise TypeError("Schedule format error")
        # Create a set of valid time slot strings from the day's schedule for efficient lookup.
        valid_slots = {s for s in day_schedule if isinstance(s, str) and '-' in s and ':' in s and s.strip().lower() != 'unavailable'}
        # Check if the requested booking_time exists in the set of valid slots for that day.
        if booking_time in valid_slots:
            is_slot_valid = True; print("DEBUG: Slot is currently valid in schedule.")
        # If the selected time slot is not in the valid list for that day.
        else:
            flash('⛔ Selected time slot is not valid or available. Please refresh.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
    # Catch any exceptions during the slot validation process (DB error, parsing error).
    except Exception as e:
        print(f"ERROR: Slot validation error: {e}"); traceback.print_exc(); flash(f'⛔ Server error validating slot.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
    # If the is_slot_valid flag is still False after the check (shouldn't happen if redirect didn't occur, but defensive).
    if not is_slot_valid:
        flash('⛔ Slot validation failed.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
    # --- End Slot Validation ---

    # --- Booking Logic and Business Rule Checks ---
    # Start try block for the core booking checks and insertion logic.
    try:
        # *** NEW CHECK 1: 10-Day Cooldown for SAME Doctor ***
        # Print debug message for Check 1, indicating check parameters.
        print(f"DEBUG: CHECK 1 (10-Day Cooldown) - Checking recent bookings for Dr {doctor_id} by Phone:{patient_phone} OR Name:{patient_name}")
        # Calculate the date 10 days before the requested booking date.
        ten_days_ago = booking_date_obj - timedelta(days=10)
        # Initialize variable to store the date of the most recent conflicting booking.
        most_recent_booking_date = None
        # Start nested try block for the cooldown database queries.
        try:
            # Check 1a: Look for recent bookings by phone number first.
            res_phone = supabase.table('bookings') \
                .select('booking_date') \
                .eq('doctor_id', doctor_id) \
                .eq('patient_phone', patient_phone) \
                .gte('booking_date', ten_days_ago.strftime('%Y-%m-%d')) \
                .lt('booking_date', booking_date_obj.strftime('%Y-%m-%d')) \
                .order('booking_date', desc=True).limit(1).execute()

            # If a recent booking was found by phone.
            if res_phone.data:
                # Store its booking date.
                most_recent_booking_date = res_phone.data[0]['booking_date']
            # If no recent booking found by phone.
            else:
                 # Check 1b: Look for recent bookings by patient name.
                 res_name = supabase.table('bookings') \
                    .select('booking_date') \
                    .eq('doctor_id', doctor_id) \
                    .eq('patient_name', patient_name) \
                    .gte('booking_date', ten_days_ago.strftime('%Y-%m-%d')) \
                    .lt('booking_date', booking_date_obj.strftime('%Y-%m-%d')) \
                    .order('booking_date', desc=True).limit(1).execute()
                 # If a recent booking was found by name.
                 if res_name.data:
                    # Store its booking date.
                    most_recent_booking_date = res_name.data[0]['booking_date']

            # If a recent booking was found by either phone or name.
            if most_recent_booking_date:
                 # Log the conflict found.
                 print(f"DEBUG: Found recent booking on {most_recent_booking_date} for Dr {doctor_id}")
                 # Flash an error message to the user explaining the 10-day rule.
                 flash(f'⛔ You have a recent booking with Dr. {fetched_doctor_name} on {most_recent_booking_date}. Please wait at least 10 days between bookings with the same doctor.', 'error')
                 # Redirect back to the booking page.
                 return redirect(url_for('booking_page', doctor_id=doctor_id))
            # If no recent booking found within the 10-day window.
            else:
                 # Log that the cooldown check passed.
                 print("DEBUG: CHECK 1 (10-Day Cooldown) PASSED.")

        # Catch exceptions specifically during the cooldown check database queries.
        except Exception as cooldown_check_err:
            # Log the error and traceback.
            print(f"ERROR checking 10-day cooldown: {cooldown_check_err}"); traceback.print_exc()
            # Flash a generic error message to the user.
            flash('⛔ Error checking booking history. Please try again.', 'error')
            # Redirect back to the booking page.
            return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- END CHECK 1 ---

        # *** CORRECTED CHECK 2: Daily Limit (Max 1 Booking Total Across ALL Doctors) ***
        # Print debug message for Check 2, indicating check parameters.
        print(f"DEBUG: CHECK 2 (Daily Limit) - Checking total bookings for Phone:{patient_phone} OR Name:{patient_name} on {booking_date}")
        # Initialize count of bookings for this patient on the target date.
        total_bookings_on_day = 0
        # Start nested try block for the daily limit database queries.
        try:
            # Use a set to store unique booking IDs found, preventing double counting if name/phone match same booking.
            booked_ids_on_day = set()

            # Query 2a: Check by phone for any non-cancelled bookings on the target date (across all doctors).
            res_phone_daily = supabase.table('bookings') \
                 .select('id') \
                 .eq('patient_phone', patient_phone) \
                 .eq('booking_date', booking_date) \
                 .neq('status', 'Cancelled') \
                 .execute()
            # If bookings found by phone.
            if res_phone_daily.data:
                # Add the IDs of these bookings to the set.
                for booking in res_phone_daily.data: booked_ids_on_day.add(booking['id'])

            # Query 2b: Check by name for any non-cancelled bookings on the target date (across all doctors).
            res_name_daily = supabase.table('bookings') \
                 .select('id') \
                 .eq('patient_name', patient_name) \
                 .eq('booking_date', booking_date) \
                 .neq('status', 'Cancelled') \
                 .execute()
            # If bookings found by name.
            if res_name_daily.data:
                 # Add the IDs of these bookings to the set (duplicates are automatically handled by set).
                 for booking in res_name_daily.data: booked_ids_on_day.add(booking['id'])

            # Calculate the total number of unique bookings found for this patient on this day.
            total_bookings_on_day = len(booked_ids_on_day)
            # Log the count found.
            print(f"DEBUG: Found {total_bookings_on_day} existing unique non-cancelled bookings for this patient on {booking_date}")

            # --- Check if the count is 1 or more (violates the max 1 per day rule) ---
            if total_bookings_on_day >= 1:
                 # --- Flash the updated error message explaining the rule ---
                 flash(f'⛔ You already have a booking scheduled for {booking_date}. You can only book one appointment per day across all doctors.', 'error')
                 # Redirect back to the booking page.
                 return redirect(url_for('booking_page', doctor_id=doctor_id))
            # If the patient has 0 existing bookings on this day.
            else:
                # Log that the daily limit check passed.
                print("DEBUG: CHECK 2 (Daily Limit of 1) PASSED.")

        # Catch exceptions specifically during the daily limit check database queries.
        except Exception as daily_limit_err:
             # Log the error and traceback.
             print(f"ERROR checking daily booking limit: {daily_limit_err}"); traceback.print_exc()
             # Flash a generic error message to the user.
             flash('⛔ Error checking your daily booking limit. Please try again.', 'error')
             # Redirect back to the booking page.
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- END CORRECTED CHECK 2 ---

        # *** CHECK 3: Slot already booked? (Race condition check) ***
        # Print debug message for Check 3, checking specific slot.
        print(f"DEBUG: CHECK 3 (Race Condition) - Is slot {booking_time} on {booking_date} for Dr {doctor_id} booked?")
        # Query 'bookings' table specifically for this doctor, date, and time slot, excluding cancelled ones.
        # Use `count='exact'` for efficiency.
        check_slot_response = supabase.table('bookings').select('id', count='exact') \
            .eq('doctor_id', doctor_id) \
            .eq('booking_date', booking_date) \
            .eq('booking_time', booking_time) \
            .neq('status', 'Cancelled') \
            .execute()
        # Print the response from the slot check query for debugging.
        print(f"DEBUG: Check 3 Resp: {check_slot_response}")
        # Check if the response count is greater than 0 (meaning the slot is already taken).
        if hasattr(check_slot_response, 'count') and check_slot_response.count > 0:
             # Flash error message indicating the slot was just taken.
             flash('⛔ Sorry, that specific time slot was just booked. Please select another.', 'error')
             # Redirect back to the booking page.
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # If the slot count is 0 (slot is available).
        else:
            # Log that the race condition check passed.
            print("DEBUG: CHECK 3 (Race Condition) PASSED.")
        # --- END CHECK 3 ---

        # *** CHECK 4: Patient SAME DAY/SAME DOCTOR conflict? (Redundant but safe check using TWO queries) ***
        # This check is somewhat redundant due to Check 1 (10-day cooldown) and Check 2 (daily total limit),
        # but acts as an explicit final safeguard against booking the same doctor twice on the same day
        # (e.g., if they used slightly different name/phone variations missed by earlier checks).
        # Print debug message for Check 4.
        print(f"DEBUG: CHECK 4 (Same Dr/Day Check) - Patient {patient_name}/{patient_phone} on {booking_date}?")
        # Start nested try block for Check 4 queries.
        try:
            # Use a set to store unique booking IDs found for this patient/doctor/day combination.
            booked_ids_same_dr_day = set()
            # Query 4a: Check by phone for non-cancelled bookings with this doctor on this date.
            res_phone_sdd = supabase.table('bookings').select('id').eq('doctor_id', doctor_id).eq('patient_phone', patient_phone).eq('booking_date', booking_date).neq('status', 'Cancelled').execute()
            # If results found, add their IDs to the set.
            if res_phone_sdd.data: booked_ids_same_dr_day.update(b['id'] for b in res_phone_sdd.data)
            # Query 4b: Check by name for non-cancelled bookings with this doctor on this date.
            res_name_sdd = supabase.table('bookings').select('id').eq('doctor_id', doctor_id).eq('patient_name', patient_name).eq('booking_date', booking_date).neq('status', 'Cancelled').execute()
            # If results found, add their IDs to the set (duplicates ignored by set).
            if res_name_sdd.data: booked_ids_same_dr_day.update(b['id'] for b in res_name_sdd.data)

            # Check if the set contains any booking IDs (meaning a conflict was found).
            if len(booked_ids_same_dr_day) > 0:
                # Log that Check 4 failed (conflict found).
                print(f"DEBUG: CHECK 4 FAILED - Explicit conflict found ({len(booked_ids_same_dr_day)} existing).")
                # Flash an informational message (info level, as previous checks might have caught this as error).
                flash(f'ℹ️ You already have a booking with Dr. {fetched_doctor_name} on {booking_date}. Only one booking per day with the same doctor allowed.', 'info')
                # Redirect back to the booking page.
                return redirect(url_for('booking_page', doctor_id=doctor_id))
            # If the set is empty (no conflict found by this specific check).
            else:
                 # Log that Check 4 passed.
                 print("DEBUG: CHECK 4 (Same Dr/Day Check) PASSED.")

        # Catch exceptions specifically during the Check 4 database queries.
        except Exception as check4_err:
             # Log the error and traceback.
             print(f"ERROR during Check 4 (Same Dr/Day): {check4_err}"); traceback.print_exc()
             # Flash a generic error message.
             flash('⛔ Error checking for same-day bookings with this doctor.', 'error')
             # Redirect back to the booking page.
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- END CHECK 4 ---

        # --- If all checks passed, Insert the Booking ---
        # Log message indicating all checks passed and booking insert is proceeding.
        print("DEBUG: All checks passed! Proceeding to insert booking.")
        # Prepare the dictionary containing data for the new booking row.
        insert_data = {
            'doctor_id': doctor_id,             # Foreign key to doctors table.
            'doctor_name': fetched_doctor_name, # Store doctor name for convenience (denormalization).
            'patient_name': patient_name,       # Patient's name.
            'patient_phone': patient_phone,     # Patient's phone.
            'booking_date': booking_date,       # Date of the appointment (YYYY-MM-DD string).
            'booking_time': booking_time,       # Time slot of the appointment (HH:MM - HH:MM string).
            'notes': notes,                     # Optional patient notes.
            'status': 'Pending',                # Initial status of the booking.
            'ip_address': ip_address,           # Record the client's IP address.
            'cookie_id': cookie_id,             # Record the device ID cookie (if available).
            'fingerprint': fingerprint          # Record the browser fingerprint (if available).
        }
        # Create a 'clean' version of the insert data, removing any keys with None values (Supabase might handle this, but explicit is safer).
        insert_data_clean = {k: v for k, v in insert_data.items() if v is not None}
        # Print the final payload being sent to Supabase for debugging.
        print(f"DEBUG: Booking insert payload: {insert_data_clean}")
        # Execute the insert operation on the 'bookings' table.
        response_insert = supabase.table('bookings').insert(insert_data_clean).execute()
        # Print the response received from Supabase after the insert attempt.
        print(f"DEBUG: Booking insert response: {response_insert}")

        # --- Handle Insert Response ---
        # Check if the insert was successful: response has data, it's a list, not empty, and the first item has an 'id'.
        if response_insert.data and isinstance(response_insert.data, list) and len(response_insert.data) > 0 and 'id' in response_insert.data[0]:
            # Extract the newly created booking ID from the response.
            booking_id = response_insert.data[0]['id']
            # Log success message with the new booking ID.
            print(f"SUCCESS: Booking confirmed (Supabase): ID {booking_id}")
            # Flash a success message to the user.
            flash('✅ Booking confirmed successfully!', 'success')
            # Redirect the user to the confirmation page, passing necessary details as query parameters.
            return redirect(url_for('confirmation', booking_id=booking_id, doctor_name=fetched_doctor_name, patient_name=patient_name, booking_date=booking_date, booking_time=booking_time))
        # Handle insertion failure (e.g., database error, constraint violation after checks passed - race condition edge case).
        else:
            # Set a default error message.
            error_message = "Booking failed due to an unexpected database issue."
            # Initialize variables to hold potential error details.
            error_info = None; error_dict = {};
            # Try to get the error object from the response.
            if hasattr(response_insert, 'error'): error_info = response_insert.error;
            # Try to convert the error object/info into a dictionary for easier access.
            if hasattr(error_info, '__dict__'): error_dict = error_info.__dict__
            elif isinstance(error_info, dict): error_dict = error_info
            # Extract error code, message, and details from the error dictionary.
            error_code = error_dict.get('code'); error_msg = error_dict.get('message', 'Unknown DB Error'); error_details = error_dict.get('details', '')
            # Log the detailed error information.
            print(f"ERROR: Supabase insert failed: Code={error_code}, Msg={error_msg}, Details={error_details}")
            # Check for specific PostgreSQL error code 23505 (unique constraint violation), potentially due to race condition missed by Check 3.
            if error_code == '23505': error_message = "Booking failed: This time slot may have just been taken."
            # If a specific error code was found, include it in the message.
            elif error_code: error_message = f"Booking failed: [{error_code}] {error_msg}"
            # Otherwise, use the message from the error object.
            else: error_message = f"Booking failed: {error_msg}"
            # Flash the determined error message to the user.
            flash(f'⛔ {error_message}', 'error')
            # Redirect back to the booking page for the specific doctor.
            return redirect(url_for('booking_page', doctor_id=doctor_id))

    # Catch any other unhandled exceptions that occur within the main '/confirm-booking' logic.
    except Exception as e:
        # Log the error.
        print(f"Outer ERROR: Unhandled Exception in /confirm-booking:")
        # Print the full traceback.
        traceback.print_exc()
        # Flash a generic server error message to the user.
        flash(f'⛔ A server error occurred: {getattr(e, "message", str(e))}.', 'error')
        # Redirect back to the booking page if doctor_id is known, otherwise redirect to the home page.
        # Checks if 'doctor_id' variable was successfully defined earlier in the route.
        return redirect(url_for('booking_page', doctor_id=doctor_id) if 'doctor_id' in locals() and doctor_id else url_for('home'))

# --- END OF FULLY REVISED /confirm-booking ROUTE ---

# --- Route: Booking Confirmation Page ---
# Decorator maps the '/confirmation' URL to this function.
@app.route('/confirmation')
# Function to display the booking confirmation page.
def confirmation():
    # Retrieve booking details passed as query parameters from the redirect in `confirm_booking`.
    booking_id = request.args.get('booking_id')       # Get the booking ID.
    doctor_name = request.args.get('doctor_name')     # Get the doctor's name.
    patient_name = request.args.get('patient_name')   # Get the patient's name.
    booking_date = request.args.get('booking_date')   # Get the booking date.
    booking_time = request.args.get('booking_time')   # Get the booking time slot.
    # Print message indicating confirmation page load with the booking ID.
    print(f"--- Loading Confirmation Page ID: {booking_id} ---")
    # Check if all the expected query parameters were received.
    if not all([booking_id, doctor_name, patient_name, booking_date, booking_time]):
        # If any detail is missing, log a warning.
        print("WARN: Missing conf details.")
        # Flash a warning message to the user.
        flash('Invalid confirmation link.', 'warning')
        # Redirect the user to the home page.
        return redirect(url_for('home'))
    # Render the 'confirmation.html' template, passing the retrieved details to be displayed.
    return render_template('confirmation.html',
                           booking_id=booking_id, doctor_name=doctor_name,
                           patient_name=patient_name, booking_date=booking_date,
                           booking_time=booking_time)


# --- Route: Cancel (Delete) Booking ---
# Decorator maps '/delete-booking/<integer:booking_id>' URL, handling only POST requests.
@app.route('/delete-booking/<int:booking_id>', methods=['POST'])
# Function to handle the cancellation of a booking.
def delete_booking(booking_id):
    # Print separator and message indicating booking cancellation attempt with ID.
    print(f"--- Attempting Cancel Booking ID: {booking_id} ---")
    # Get information from the form about where the cancel request originated (for redirect).
    source = request.form.get('source', 'unknown') # e.g., 'patient_dashboard', 'doctor_dashboard', 'confirmation_page'.
    # Get patient identifier (name/phone) if cancelling from patient dashboard.
    patient_identifier = request.form.get('patient_identifier')
    # Get doctor ID string if cancelling from doctor dashboard.
    doctor_id_str = request.form.get('doctor_id')
    # Log the source information received.
    print(f"Source: {source}, Patient ID: {patient_identifier}, Dr ID: {doctor_id_str}")
    # Determine the default redirect URL (home page).
    redirect_url = url_for('home')
    # Set specific redirect URL if cancelling from the patient dashboard.
    if source == 'patient_dashboard' and patient_identifier:
        redirect_url = url_for('patient_dashboard', patient_identifier=patient_identifier)
    # Set specific redirect URL if cancelling from the doctor dashboard. Check if doctor ID is valid int.
    elif source == 'doctor_dashboard' and doctor_id_str and doctor_id_str.isdigit():
        redirect_url = url_for('doctor_dashboard', doctor_id=int(doctor_id_str))
    # Explicitly redirect home if cancelling from the confirmation page (or if source unknown).
    elif source == 'confirmation_page':
        redirect_url = url_for('home')
    # Start try block for the database update operation.
    try:
        # Execute an update on the 'bookings' table.
        # Set the 'status' column to 'Cancelled'.
        # Filter for the specific 'id' matching the booking_id.
        # Add an additional filter: only update if the current 'status' is 'Pending'.
        # This prevents cancelling already completed or already cancelled bookings.
        response = supabase.table('bookings').update({'status': 'Cancelled'}).eq('id', booking_id).eq('status', 'Pending').execute()
        # Print the Supabase response for debugging.
        print(f"DEBUG: Cancel response ID {booking_id}: {response}")
        # Check if the update response indicates data was changed (usually means success).
        if response.data and len(response.data) > 0:
            # Flash a success message.
            flash('✅ Booking cancelled.', 'success');
            # Log success message.
            print(f"Booking {booking_id} status -> Cancelled.")
        # If the update didn't change any data (likely because status wasn't 'Pending').
        else:
            # Query the booking's current status to provide a more informative message.
            status_response = supabase.table('bookings').select('status').eq('id', booking_id).maybe_single().execute()
            # If the status query was successful and found the booking.
            if status_response.data:
                # Get the current status.
                current_status = status_response.data['status']
                # Flash an informational message explaining why cancellation failed.
                flash(f'ℹ️ Cannot cancel booking (Status: {current_status}).', 'info')
                # Log a warning message.
                print(f"WARN: Cancel failed {booking_id}, status was {current_status}")
            # If the status query didn't find the booking (it might have been deleted elsewhere).
            else:
                # Flash an error message: booking not found.
                flash('⛔ Booking not found.', 'error')
                # Log a warning.
                print(f"WARN: Cancel non-existent ID {booking_id}")
    # Catch any exceptions during the database update or status check.
    except Exception as e:
        # Log the error and print traceback.
        print(f"ERROR cancelling {booking_id}:"); traceback.print_exc()
        # Flash a database error message to the user.
        flash(f'⛔ DB error cancelling: {getattr(e, "message", str(e))}', 'error')
    # Print the determined redirect URL for debugging.
    print(f"Redirecting after cancel attempt: {redirect_url}")
    # Redirect the user to the appropriate page based on the source.
    return redirect(redirect_url)

# --- Route: Doctor Login Page ---
# Decorator maps '/doctor-login' URL to this function, handling both GET (display form) and POST (process login).
@app.route('/doctor-login', methods=['GET', 'POST'])
# Function to handle doctor login attempts.
def doctor_login():
    # Check if the request method is POST (form submission).
    if request.method == 'POST':
        # Get doctor name from form, strip whitespace, default empty.
        doctor_name = request.form.get('doctorName', '').strip()
        # Get doctor ID from form, strip whitespace, default empty.
        doctor_id_str = request.form.get('doctorId', '').strip()
        # Validate that both name and ID are provided, and ID is numeric.
        if not doctor_name or not doctor_id_str or not doctor_id_str.isdigit():
            # If validation fails, flash error and redirect back to login form.
            flash('⛔ Enter Name & numeric ID.', 'error'); return redirect(url_for('doctor_login'))
        # Convert valid doctor ID string to integer.
        doctor_id = int(doctor_id_str)
        # Start try block for database query.
        try:
             # Query 'doctors' table. Select ID and Name.
             # Filter by exact 'id'.
             # Filter by 'name' using case-insensitive 'ilike' match (contains the provided name).
             # `maybe_single()` expects 0 or 1 result.
             response = supabase.table('doctors').select('id, name').eq('id', doctor_id).ilike('name', f'%{doctor_name}%').maybe_single().execute()
             # Get the doctor data (dict) or None from the response.
             doctor = response.data;
             # Print debug log showing the query response.
             print(f"DEBUG: Dr login check response ID {doctor_id} Name '{doctor_name}': {response}")
        # Catch exceptions during the Supabase query.
        except Exception as e:
             # Log the error and traceback.
             print(f"ERROR: Supabase Dr login check {doctor_id}/{doctor_name}:"); traceback.print_exc();
             # Flash a database error message.
             flash(f'⛔ DB error: {getattr(e, "message", str(e))}', 'error');
             # Redirect back to login form.
             return redirect(url_for('doctor_login'))
        # Check if the query found a matching doctor.
        if doctor:
             # Get the actual name from the database response.
             db_doctor_name = doctor.get('name', 'Doctor');
             # Log successful login.
             print(f"SUCCESS: Dr login: ID {doctor_id}, Name '{db_doctor_name}'");
             # Flash a welcome message.
             flash(f'✅ Welcome Dr. {db_doctor_name}!', 'success');
             # Redirect to the doctor's dashboard, passing their ID.
             return redirect(url_for('doctor_dashboard', doctor_id=doctor_id))
        # If no matching doctor was found.
        else:
             # Log failed login attempt.
             print(f"FAIL: Dr login: ID {doctor_id}, Name '{doctor_name}'");
             # Flash an invalid credentials error message.
             flash('⛔ Invalid Dr Name/ID.', 'error');
             # Redirect back to login form.
             return redirect(url_for('doctor_login'))
    # If request method is GET, just render the login form template.
    return render_template('doctor_login.html')

# --- Route: Doctor Dashboard Page ---
# Decorator maps '/doctor-dashboard/<integer:doctor_id>' URL. Requires a doctor ID.
@app.route('/doctor-dashboard/<int:doctor_id>')
# Function to display the dashboard for a logged-in doctor.
def doctor_dashboard(doctor_id):
    # Print separator and message indicating dashboard load with doctor ID.
    print(f"--- Loading Dr Dashboard ID: {doctor_id} ---")
    # Initialize variables to hold doctor info, bookings, stats, etc.
    doctor = None; bookings_rows = []; stats = defaultdict(int); appts_per_day = defaultdict(int); unique_patients = set()
    # Start try block for database queries.
    try:
        # Fetch the doctor's basic info (ID, Name) to confirm existence and display name.
        doc_response = supabase.table('doctors').select('id, name').eq('id', doctor_id).maybe_single().execute()
        # Get the doctor data (dict) or None.
        doctor = doc_response.data
        # If doctor not found by ID.
        if not doctor:
            # Log error.
            print(f"ERROR: Dr ID {doctor_id} not found.");
            # Flash error message.
            flash("⛔ Doctor not found.", "error");
            # Redirect to the doctor login page.
            return redirect(url_for('doctor_login'))
        # Log confirmation that doctor was found.
        print(f"DEBUG: Found Dr. {doctor.get('name')}")
        # Fetch all non-cancelled bookings associated with this doctor ID.
        bookings_response = supabase.table('bookings').select(
            'id, patient_name, patient_phone, booking_date, booking_time, notes, status' # Select needed columns.
            ).eq('doctor_id', doctor_id).neq( # Filter by doctor ID.
                'status', 'Cancelled'         # Exclude cancelled bookings.
            ).order(                          # Order results:
                'booking_date', desc=True     # Newest date first.
            ).order(
                'booking_time', desc=True     # Newest time first within each date.
            ).execute()
        # Assign the fetched booking data (list of dicts) or an empty list if none found.
        bookings_rows = bookings_response.data or [];
        # Log the number of bookings fetched.
        print(f"DEBUG: Fetched {len(bookings_rows)} bookings.")

        # --- Statistics Calculation ---
        # Get today's date and format it.
        today = date.today(); today_str = today.strftime('%Y-%m-%d');
        # Calculate dates for weekly and monthly stats boundaries.
        week_later = today + timedelta(days=7); month_start = today.replace(day=1)
        # Initialize total listed count.
        stats['total_bookings_listed'] = len(bookings_rows)
        # Iterate through each fetched booking to calculate various stats.
        for b in bookings_rows:
             # Get status and create a patient identifier (phone preferred, fallback to name).
             status = b.get('status'); p_id = b.get('patient_phone') or b.get('patient_name', '').strip()
             # Try parsing the booking date string.
             try: dt_str = b.get('booking_date'); booking_date_obj = datetime.strptime(dt_str, '%Y-%m-%d').date() if dt_str else None
             # Handle potential parsing errors or missing dates.
             except (ValueError, TypeError): print(f"Warn: Invalid date {dt_str} bk ID {b.get('id')}"); continue # Skip stat calculation for this booking.
             # If date couldn't be parsed, skip.
             if not booking_date_obj: continue
             # Increment counts based on status and date comparison.
             if status == 'Pending':
                 if booking_date_obj >= today: stats['pending_upcoming_count'] += 1 # Pending today or later.
                 if booking_date_obj == today: stats['today_pending_count'] += 1   # Pending specifically today.
             elif status == 'Completed': stats['completed_total_count'] += 1     # Total completed ever.
             if booking_date_obj == today: stats['all_today_count'] += 1           # All non-cancelled today.
             if today <= booking_date_obj < week_later: stats['all_next_7_days_count'] += 1 # All non-cancelled in next 7 days.
             # Count appointments per day for the chart.
             appts_per_day[booking_date_obj.strftime('%Y-%m-%d')] += 1
             # Collect unique patient identifiers (case-insensitive) for appointments this month.
             if booking_date_obj >= month_start and p_id: unique_patients.add(p_id.lower())
        # Count the number of unique patients this month.
        stats['unique_patients_this_month'] = len(unique_patients)
        # Print the calculated stats dictionary for debugging.
        print(f"DEBUG: Stats: {dict(stats)}")
        # --- End Stats ---

    # Catch any exceptions during database queries or stats calculation.
    except Exception as e:
        # Log the error and traceback.
        print(f"ERROR loading Dr Dashboard {doctor_id}:"); traceback.print_exc();
        # Flash an error message to the user.
        flash(f'⛔ Error loading data: {getattr(e, "message", str(e))}', 'error');
        # Render the dashboard template even on error, passing minimal data to avoid breaking the template.
        # Pass doctor ID and a default name if doctor object failed to load. Provide empty/default structures.
        return render_template('doctor_dashboard.html',
                               doctor=doctor or {'id': doctor_id, 'name':'N/A'},
                               doctor_id=doctor_id, bookings_by_month={},
                               stats={'total_bookings_listed': 0},
                               chart_config_daily={'labels': [], 'data': []})

    # --- Chart Preparation (Next 7 Days) ---
    # Initialize lists for chart labels (dates) and data (counts).
    chart_labels=[]; chart_data=[]
    # Loop through the next 7 days (0 to 6).
    for i in range(7):
        # Calculate the date for this day.
        d = today + timedelta(days=i);
        # Format the date as 'YYYY-MM-DD' for lookup in appts_per_day.
        d_str = d.strftime('%Y-%m-%d');
        # Append the formatted date (e.g., "Mon, Aug 15") to the labels list.
        chart_labels.append(d.strftime('%a, %b %d'));
        # Append the appointment count for that day (or 0 if not found) to the data list.
        chart_data.append(appts_per_day.get(d_str, 0))
    # Create the chart configuration dictionary for passing to the template (used by Chart.js).
    chart_config = {'labels': chart_labels, 'data': chart_data};
    # Print the chart configuration for debugging.
    print(f"DEBUG: Chart: {chart_config}")

    # --- Group Bookings by Month and Day for Display ---
    # Use defaultdict to easily group bookings. Outer key: Month-Year string, Inner key: Date string. Value: List of bookings.
    bookings_by_month = defaultdict(lambda: defaultdict(list))
    # Iterate through the fetched booking rows.
    for b in bookings_rows:
        # Start try block for parsing and grouping each booking.
        try:
            # Check if booking_date exists.
            if b.get('booking_date'):
                # Parse the date string into a date object.
                booking_date_obj = datetime.strptime(b['booking_date'], '%Y-%m-%d').date()
                # Create the month-year key (e.g., "August 2024").
                m_key = booking_date_obj.strftime('%B %Y');
                # Create the day key (YYYY-MM-DD string).
                d_key = b['booking_date'];
                # Append the current booking dictionary to the list for that specific month and day.
                bookings_by_month[m_key][d_key].append(b)
            # If booking date is missing.
            else: print(f"Warn: Skip grouping bk ID {b.get('id')} missing date.")
        # Catch errors during date parsing or dictionary access.
        except (ValueError, TypeError, KeyError) as e: print(f"Warn: Grouping error bk id {b.get('id')} date '{b.get('booking_date')}': {e}")
    # Sort the month keys chronologically (newest first). Uses strptime to convert "Month Year" back to sortable date.
    sorted_months = sorted(bookings_by_month.keys(), key=lambda my: datetime.strptime(my, '%B %Y'), reverse=True)
    # Create the final grouped dictionary, ensuring days within each month are also sorted (newest first).
    final_grouped = { m: dict(sorted(bookings_by_month[m].items(), reverse=True)) for m in sorted_months }
    # --- End Grouping ---

    # Render the doctor dashboard template, passing all processed data.
    return render_template('doctor_dashboard.html',
                           doctor=doctor,                     # Doctor's info {id, name}.
                           doctor_id=doctor_id,               # Doctor's ID.
                           bookings_by_month=final_grouped,   # Bookings grouped by month, then day.
                           stats=dict(stats),                 # Dictionary of calculated statistics.
                           chart_config_daily=chart_config)   # Configuration data for the daily chart.

# --- Route: Update All Notes (Doctor Dashboard) ---
# Decorator maps '/update-all-notes' URL, handling only POST requests.
@app.route('/update-all-notes', methods=['POST'])
# Function to handle batch updates of booking notes from the doctor dashboard.
def update_all_notes():
    # Print separator and message indicating route entry.
    print("--- POST /update-all-notes ---")
    # Check if the request content type is JSON.
    if not request.is_json:
        print("ERROR: Not JSON"); return jsonify({'success': False, 'message': 'Request must be JSON.'}), 400 # Return 400 Bad Request.
    # Parse the incoming JSON data from the request body.
    data = request.get_json()
    # Get the 'updates' list from the JSON data. Default to an empty list if missing.
    updates = data.get('updates', [])
    # Print the received updates list for debugging.
    print(f"DEBUG: Updates data: {updates}")
    # Check if 'updates' is actually a list.
    if not isinstance(updates, list):
        print("ERROR: Not list"); return jsonify({'success': False, 'message': "Invalid format: 'updates' list missing."}), 400 # Return 400 Bad Request.
    # Initialize counters and lists for tracking update status.
    updated = 0; failed_ids = []; messages = []
    # Iterate through each update item in the received list.
    for u in updates:
         # Get the booking ID and notes from the update item dictionary.
         bid = u.get('bookingId'); notes = u.get('notes', '')
         # Validate that booking ID is provided (as int or string digit) and notes is a string.
         if isinstance(bid, (int, str)) and str(bid).isdigit() and isinstance(notes, str):
              # Convert booking ID to integer.
              bid_int = int(bid)
              # Start try block for the database update operation for this single note.
              try:
                   # Execute an update on the 'bookings' table.
                   # Set the 'notes' column to the new notes (stripped of whitespace).
                   # Filter where 'id' matches the booking ID.
                   response = supabase.table('bookings').update({'notes': notes.strip()}).eq('id', bid_int).execute()
                   # Print the Supabase response for debugging.
                   print(f"DEBUG: Update notes response ID {bid_int}: {response}")
                   # Check if the update response indicates data was changed (success).
                   if response.data and len(response.data) > 0:
                       updated += 1; print(f"SUCCESS: Note update {bid_int}.")
                   # If update affected 0 rows (or returned no data).
                   else:
                       # Add the ID to the failed list.
                       failed_ids.append(bid_int)
                       # Check if the booking ID actually exists to provide better feedback.
                       check = supabase.table('bookings').select('id', count='exact').eq('id', bid_int).execute()
                       # Construct an appropriate warning message.
                       msg = f"Note update failed: Booking {bid_int} not found." if hasattr(check,'count') and check.count==0 else f"Note update failed {bid_int} (no rows affected)."
                       # Log the warning and add the message to the messages list.
                       print(f"WARN: {msg} Resp: {response}"); messages.append(msg)
              # Catch exceptions during the database update for this specific booking ID.
              except Exception as e:
                   # Log the error and traceback.
                   print(f"ERROR updating note {bid_int}:"); traceback.print_exc();
                   # Add the ID to the failed list.
                   failed_ids.append(bid_int);
                   # Add a generic server error message for this ID to the messages list.
                   messages.append(f"Server error updating note {bid_int}.")
         # If the data format for an update item was invalid (bad ID or notes type).
         else:
              # Get the invalid ID for logging/reporting purposes.
              invalid_id = u.get('bookingId', 'Unknown');
              # Log the error.
              print(f"ERROR: Invalid data {invalid_id}");
              # Add the invalid ID to the failed list.
              failed_ids.append(invalid_id);
              # Add an invalid data message to the messages list.
              messages.append(f"Invalid data format received (ID: {invalid_id}).")
    # Print a summary of the batch update operation.
    print(f"--- Notes update done. Attempted: {len(updates)}. Succeeded: {updated}. Failed: {len(failed_ids)}. ---")
    # Construct the final message for the flash notification.
    final_msg = f"{updated} note(s) saved.";
    # Set the default flash category to 'info'.
    flash_cat = 'info'
    # If there were any failures.
    if failed_ids:
        # Create a truncated string of failed IDs for the message.
        fid_str = ', '.join(map(str, failed_ids[:5]))+('...' if len(failed_ids)>5 else '');
        # Append failure information to the message.
        final_msg += f" {len(failed_ids)} failed (e.g., IDs: {fid_str}). See console logs for details.";
        # Set flash category to 'warning'.
        flash_cat = 'warning'
    # If some were updated and there were no failures.
    if updated > 0 and not failed_ids:
        # Set flash category to 'success'.
        flash_cat = 'success'
    # Flash the final summary message to the user.
    flash(final_msg, flash_cat)
    # Return a JSON response summarizing the outcome of the batch operation.
    return jsonify({'success': not failed_ids, # Overall success is true only if no failures occurred.
                    'message': final_msg,      # The same message flashed to the user.
                    'updated_count': updated,  # Number of successful updates.
                    'failed_count': len(failed_ids)}) # Number of failures.

# --- Route: Mark Booking as Completed ---
# Decorator maps '/mark-complete/<integer:booking_id>' URL, handling only POST requests.
@app.route('/mark-complete/<int:booking_id>', methods=['POST'])
# Function to handle marking a booking status as 'Completed'.
def mark_complete(booking_id):
    # Print separator and message indicating route entry with booking ID.
    print(f"--- POST /mark-complete ID: {booking_id} ---")
    # Start try block for the database update.
    try:
        # Execute an update on the 'bookings' table.
        # Set the 'status' column to 'Completed'.
        # Filter for the specific 'id'.
        # Add condition: only update if the current 'status' is 'Pending'.
        response = supabase.table('bookings').update({'status': 'Completed'}).eq('id', booking_id).eq('status', 'Pending').execute()
        # Print the Supabase response for debugging.
        print(f"DEBUG: Mark complete resp ID {booking_id}: {response}")
        # Check if the update response indicates data was changed (success).
        if response.data and len(response.data) > 0:
            # Log success.
            print(f"SUCCESS: Mark complete {booking_id}.");
            # Return success JSON response.
            return jsonify({'success': True, 'message': 'Marked completed.'})
        # If the update didn't change any rows (likely status wasn't 'Pending').
        else:
             # Query the current status of the booking to give specific feedback.
             status_resp = supabase.table('bookings').select('status').eq('id', booking_id).maybe_single().execute()
             # If the status query found the booking.
             if status_resp.data:
                 # Get the current status.
                 status = status_resp.data['status'];
                 # Construct message explaining why it failed.
                 msg = f'Cannot mark complete. Status is already "{status}".';
                 # Log the failure reason.
                 print(f"FAIL: Mark complete {booking_id} - current status '{status}'");
                 # Return failure JSON response with 409 Conflict status code.
                 return jsonify({'success': False, 'message': msg}), 409
             # If the status query didn't find the booking ID.
             else:
                 # Log failure: booking not found.
                 print(f"FAIL: Mark complete {booking_id}: Not found.");
                 # Return failure JSON response with 404 Not Found status code.
                 return jsonify({'success': False, 'message': 'Booking not found.'}), 404
    # Catch any exceptions during the database update or status check.
    except Exception as e:
        # Log the error and traceback.
        print(f"ERROR mark complete {booking_id}:"); traceback.print_exc();
        # Get error message from exception.
        error = getattr(e, 'message', str(e));
        # Return failure JSON response with 500 Internal Server Error status code.
        return jsonify({'success': False, 'message': f'DB error: {error}'}), 500

# --- Route: Patient Login Page ---
# Decorator maps '/patient-login' URL, handling both GET (show form) and POST (process login).
@app.route('/patient-login', methods=['GET', 'POST'])
# Function to handle patient login attempts.
def patient_login():
    # Check if the request method is POST (form submission).
    if request.method == 'POST':
        # Get the patient identifier (name or phone) from the form, strip whitespace, default empty.
        patient_identifier = request.form.get('patientIdentifier', '').strip()
        # Print message indicating login attempt with the identifier.
        print(f"--- Attempting Patient Login ID: '{patient_identifier}' ---")
        # Check if the identifier is empty.
        if not patient_identifier:
            # Flash error message if identifier is missing.
            flash('⛔ Please enter your Name or Phone Number.', 'error')
            # Redirect back to the patient login form.
            return redirect(url_for('patient_login'))

        # Initialize flag to track if a booking exists for this identifier.
        booking_exists = False
        # Start try block for database queries.
        try:
            # Print debug message indicating start of DB check.
            print(f"DEBUG: Patient login check for '{patient_identifier}'")
            # This uses two separate queries because Supabase Python client might not easily support `OR` conditions across `ilike` and `eq` directly in one query builder chain.

            # Query 1: Check by patient name using case-insensitive 'ilike'.
            # Use count='exact' for efficiency.
            # Exclude cancelled bookings. Limit to 1 (we just need existence).
            name_res = supabase.table('bookings').select('id', count='exact') \
                .ilike('patient_name', f'%{patient_identifier}%') \
                .neq('status', 'Cancelled') \
                .limit(1).execute()
            # If the name query found at least one booking.
            if hasattr(name_res, 'count') and name_res.count > 0:
                 # Set the flag to True.
                 booking_exists = True

            # Query 2: Check by exact patient phone number ONLY IF not found by name.
            phone_res = None # Define before use in print statement.
            if not booking_exists:
                # Check using exact match 'eq' for the phone number.
                phone_res = supabase.table('bookings').select('id', count='exact') \
                     .eq('patient_phone', patient_identifier) \
                     .neq('status', 'Cancelled') \
                     .limit(1).execute()
                # If the phone query found at least one booking.
                if hasattr(phone_res, 'count') and phone_res.count > 0:
                     # Set the flag to True.
                     booking_exists = True

            # Print debug summary of the two queries' results.
            print(f"DEBUG: Patient Login Check - Name Count: {name_res.count if hasattr(name_res, 'count') else 'ERR'}, Phone Count: {phone_res.count if phone_res and hasattr(phone_res, 'count') else 'N/A'} -> Exists: {booking_exists}")

        # Catch exceptions during the database queries.
        except Exception as e:
            # Log the error and traceback.
            print(f"ERROR: Supabase patient login check '{patient_identifier}':"); traceback.print_exc()
            # Flash a database error message.
            flash(f'⛔ Database error during login: {getattr(e, "message", str(e))}.', 'error')
            # Redirect back to the patient login form.
            return redirect(url_for('patient_login'))

        # Check if either query found an existing booking.
        if booking_exists:
            # Log successful "login" (access grant).
            print(f"SUCCESS: Patient login '{patient_identifier}'.")
            # Redirect to the patient dashboard, passing the identifier.
            return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
        # If no active booking was found for the identifier.
        else:
            # Log failed login attempt.
            print(f"FAIL: Patient login '{patient_identifier}'. No active booking found.")
            # Flash error message indicating no matching bookings found.
            flash('⛔ No active bookings found matching that Name or Phone Number.', 'error')
            # Redirect back to the patient login form.
            return redirect(url_for('patient_login'))

    # If request method is GET, render the patient login form template.
    return render_template('patient_login.html')
# --- END OF REVISED patient_login ---

# --- Route: Patient Dashboard Page ---
# Decorator maps '/patient-dashboard/<path:patient_identifier>' URL. 'path' allows name/phone which might contain characters interpreted differently otherwise.
@app.route('/patient-dashboard/<path:patient_identifier>')
# Function to display the dashboard for a given patient identifier (name or phone).
def patient_dashboard(patient_identifier):
    # Print separator and message indicating dashboard load with identifier.
    print(f"--- Loading Patient Dashboard ID: '{patient_identifier}' ---")
    # Basic check: ensure identifier is provided and not just whitespace.
    if not patient_identifier or not patient_identifier.strip():
        # Flash error and redirect to login if identifier is missing.
        flash('⛔ Patient identifier missing.', 'error'); return redirect(url_for('patient_login'))

    # Use a dictionary to store booking data, using booking ID as key. This automatically handles duplicates
    # if both name and phone queries return the same booking row.
    combined_bookings_data = {}
    # Flag to indicate if a database error occurred during fetching.
    db_error = False
    # Set a default display name to the identifier itself, may be updated from booking data.
    actual_patient_name = patient_identifier # Default

    # Start try block for database queries.
    try:
        # Log the identifier being used to fetch bookings.
        print(f"DEBUG: Fetching bookings for '{patient_identifier}'")
        # Define the columns needed from the 'bookings' table.
        select_columns = 'id, doctor_id, doctor_name, patient_name, patient_phone, booking_date, booking_time, status, notes'

        # Query 1: Fetch by name using case-insensitive 'ilike'.
        name_query = supabase.table('bookings').select(select_columns) \
            .ilike('patient_name', f'%{patient_identifier}%') \
            .neq('status', 'Cancelled') \
            .order('booking_date', desc=True).order('booking_time', desc=True) # Order doesn't matter much here as we re-sort later.
        # Execute the name query.
        name_response = name_query.execute()
        # Log how many results were found by name.
        print(f"DEBUG: Fetch by Name Response count: {len(name_response.data) if name_response.data else 0}")
        # If data was found by name query.
        if name_response.data:
            # Iterate through the results.
            for booking in name_response.data:
                 # Use booking ID as key to add/update the entry in the combined dictionary.
                 if 'id' in booking: combined_bookings_data[booking['id']] = booking

        # Query 2: Fetch by exact phone number match.
        phone_query = supabase.table('bookings').select(select_columns) \
             .eq('patient_phone', patient_identifier) \
             .neq('status', 'Cancelled') \
             .order('booking_date', desc=True).order('booking_time', desc=True)
        # Execute the phone query.
        phone_response = phone_query.execute()
        # Log how many results were found by phone.
        print(f"DEBUG: Fetch by Phone Response count: {len(phone_response.data) if phone_response.data else 0}")
        # If data was found by phone query.
        if phone_response.data:
             # Iterate through the results.
             for booking in phone_response.data:
                  # Add/update the entry in the combined dictionary using booking ID as key.
                  if 'id' in booking: combined_bookings_data[booking['id']] = booking

        # Convert the values (booking dictionaries) from the combined dictionary back into a list.
        # Sort the final combined list properly by date and then time, newest first.
        bookings_data = sorted(combined_bookings_data.values(),
                               key=lambda b: (b.get('booking_date', '0000-00-00'), b.get('booking_time', '00:00')), # Use get with defaults for sorting robustness
                               reverse=True)
        # Log the total number of unique bookings found.
        print(f"DEBUG: Total unique bookings found: {len(bookings_data)}")

        # Initialize the list to hold final processed bookings with 'is_deletable' flag.
        processed_bookings = []
        # Check if any bookings were found for this identifier.
        if bookings_data:
             # --- Get display name ---
             # Get the actual patient name from the most recent booking (first item in the sorted list).
             # Fallback to the original identifier if 'patient_name' is missing. Strip whitespace.
             actual_patient_name = bookings_data[0].get('patient_name', patient_identifier).strip()
             # Log the name that will be displayed on the dashboard.
             print(f"DEBUG: Displaying as '{actual_patient_name}'.")

             # --- Determine if bookings are deletable ---
             # Get the current time once for comparison.
             now = datetime.now()
             # Iterate through the sorted list of unique bookings.
             for booking in bookings_data:
                 # Default the 'is_deletable' flag to False.
                 booking['is_deletable'] = False
                 # Check if the booking status is 'Pending'. Only pending bookings can potentially be deleted.
                 if booking.get('status') == 'Pending':
                      # Start nested try block for parsing date/time of this booking.
                      try:
                           # Get date string and time slot string.
                           date_str = booking.get('booking_date'); time_slot = booking.get('booking_time', '');
                           # Check if date and time slot seem valid.
                           if date_str and time_slot and '-' in time_slot and ':' in time_slot:
                                # Extract the start time (HH:MM).
                                start_time_str = time_slot.split('-')[0].strip()
                                # Combine date and start time, parse into a datetime object.
                                appointment_dt = datetime.strptime(f"{date_str} {start_time_str}", '%Y-%m-%d %H:%M')
                                # Check if the appointment datetime is in the future compared to now.
                                if appointment_dt > now:
                                    # If it's a pending appointment in the future, mark it as deletable.
                                    booking['is_deletable'] = True
                           #else: # Optional: log if format seems invalid for delete check.
                           #    print(f"Warn: Invalid date/time format for delete check on Booking ID {booking.get('id')}")
                      # Catch any errors during parsing or dictionary access for the delete check.
                      except (ValueError, IndexError, TypeError, KeyError) as e:
                           # Log the warning if parsing fails for a specific booking.
                           print(f"Warn: Error parsing date/time for delete check on Booking ID {booking.get('id')}: {e}")
                 # Append the booking dictionary (with the potentially updated 'is_deletable' flag) to the final list.
                 processed_bookings.append(booking)
        # If no bookings were found for the identifier after both queries.
        else:
             # Check if identifier was actually provided (it passed the initial check).
             if patient_identifier.strip():
                 # Flash an informational message that no bookings were found.
                 flash('ℹ️ No active bookings found for this identifier.', 'info');
                 # Log this information.
                 print(f"INFO: No active bookings found for '{patient_identifier}'")

    # Catch any exceptions during the database queries or processing for the patient dashboard.
    except Exception as e:
        # Log the error and traceback.
        print(f"ERROR: Supabase loading Patient Dashboard '{patient_identifier}':"); traceback.print_exc()
        # Flash a database error message to the user.
        flash(f'⛔ Database error loading your bookings: {getattr(e, "message", str(e))}', 'error');
        # Set the database error flag to True.
        db_error = True
        # `processed_bookings` will remain empty or partially filled if error occurred mid-loop.

    # Render the 'patient_dashboard.html' template.
    return render_template('patient_dashboard.html',
                           bookings=processed_bookings,          # Pass the list of processed bookings (with is_deletable).
                           patient_identifier=patient_identifier, # Pass the original identifier used.
                           patient_display_name=actual_patient_name, # Pass the name determined from bookings (or identifier).
                           error=db_error)                      # Pass the database error flag (template might use this).
# --- END OF REVISED patient_dashboard ---


# --- Main Execution Block ---
# Standard Python check: ensures the code inside only runs when the script is executed directly (not imported as a module).
if __name__ == '__main__':
    # Get the port number from the environment variable 'PORT'. Default to 5003 if not set. Convert to integer.
    port = int(os.environ.get("PORT", 5003))
    # Get the Flask debug mode setting from environment variable 'FLASK_DEBUG'.
    # Default to "False", convert to lowercase, check if it's exactly "true". Results in a boolean.
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    # Print startup information.
    print(f"--- Starting Flask Application ---")
    # Print whether running in Debug or Production mode.
    print(f"Mode: {'Debug' if debug_mode else 'Production'}")
    # Print the URL where the application will be accessible locally. 0.0.0.0 makes it accessible on the network.
    print(f"URL: http://0.0.0.0:{port}")
    # Print the beginning of the Supabase URL for confirmation (avoid printing the full sensitive key).
    print(f"Supabase URL: {supabase_url[:20]}...") # Print prefix only for security/brevity.
    # Run the Flask development server.
    # `debug=debug_mode` enables/disables Flask's debugger and auto-reloader based on the environment variable.
    # `port=port` sets the port to listen on.
    # `host='0.0.0.0'` makes the server accessible from other devices on the network, not just localhost.
    app.run(debug=debug_mode, port=port, host='0.0.0.0')

# --- END OF FILE app.py ---