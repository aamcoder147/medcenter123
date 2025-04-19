# --- START OF FILE app.py ---

# --- START OF MODIFIED FILE app.py ---

from flask import (
    Flask, render_template, json, request, redirect, url_for,
    send_from_directory, flash, jsonify, make_response
)
# REMOVED: import sqlite3
from flask_login import LoginManager, UserMixin, current_user # Assuming you might use login later
import os
from datetime import datetime, timedelta, date, time # Added time for comparison
import uuid
from collections import defaultdict # Helpful for aggregation
# REMOVED: import json # Supabase client handles JSON serialization/deserialization if column type is JSON/JSONB
import math # For ceiling function for stars
import traceback # Added for detailed error logging

# --- Supabase & Environment Setup ---
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file (must contain SUPABASE_URL, SUPABASE_KEY, FLASK_SECRET_KEY)
load_dotenv()

# Initialize Supabase Client
# Credentials MUST be set in the .env file (see notes at top)
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in the .env file")
else:
    # Ensure client creation happens successfully
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")
    except Exception as init_err:
        print(f"FATAL: Failed to initialize Supabase client: {init_err}")
        # Optionally raise error again or exit depending on desired behavior
        raise init_err
# --- End Supabase Setup ---

app = Flask(__name__, static_folder='static')

# Required for flash messages and sessions (use secure key from .env)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
     print("WARNING: FLASK_SECRET_KEY not set in environment. Using default (unsafe).")
     app.secret_key = 'your_default_secret_key_1234' # Unsafe default

# --- Login Manager Setup (Keep if using authentication) ---
login_manager = LoginManager(); login_manager.init_app(app)
class User(UserMixin):
    def __init__(self, id): self.id = id
@login_manager.user_loader
def load_user(user_id):
    if user_id: return User(user_id)
    return None
# --- End Login Manager Setup ---

# --- Load doctors data FROM SUPABASE (includes ratings calculation) ---
def load_doctors_from_db():
    """Fetches doctors from Supabase, parses availability (assumed jsonb), and calculates average rating."""
    print("Loading doctors data from Supabase...")
    doctors_list = []
    try:
        # Fetch all doctors ordered by name
        response_docs = supabase.table('doctors').select('*').order('name', desc=False).execute()

        if not response_docs.data:
            print("Warn: No doctors found in Supabase 'doctors' table.")
            return []

        doctors_list = response_docs.data # Supabase returns list of dicts

        # Initialize ratings/counts
        for doc in doctors_list:
            # Availability should be directly usable if stored as JSON/JSONB in Supabase
            # No need for json.loads unless it's stored as TEXT
            if not isinstance(doc.get('availability'), dict):
                 # print(f"Warn: Availability for Dr {doc.get('id')} is not a dictionary. Setting to empty. Raw data: {doc.get('availability')}") # Too noisy maybe
                 doc['availability'] = {}
            doc['average_rating'] = 0.0
            doc['review_count'] = 0

        # Fetch ALL approved reviews to calculate ratings efficiently
        print("DEBUG: Fetching reviews with is_approved = 1 (integer)") # DEBUG
        # *** FIX 1: Use integer 1 for is_approved check ***
        response_reviews = supabase.table('reviews').select('doctor_id, rating').eq('is_approved', 1).execute() # Use 1 instead of True

        if response_reviews.data:
             print(f"DEBUG: Found {len(response_reviews.data)} approved reviews for rating calculation.") # DEBUG
             # Aggregate ratings in Python
             ratings_agg = defaultdict(lambda: {'total': 0, 'count': 0})
             for review in response_reviews.data:
                  if review.get('rating') is not None: # Ensure rating exists and is valid
                    try:
                        rating_val = float(review['rating'])
                        if 1 <= rating_val <= 5: # Validate rating range
                           ratings_agg[review['doctor_id']]['total'] += rating_val
                           ratings_agg[review['doctor_id']]['count'] += 1
                        # else: print(f"Warn: Invalid rating value {review['rating']} for doctor {review['doctor_id']} ignored.")
                    except (ValueError, TypeError):
                        print(f"Warn: Non-numeric rating {review['rating']} for doctor {review['doctor_id']} ignored.")


             # Apply aggregated ratings to doctors
             for doc in doctors_list:
                doc_id = doc.get('id') # Use .get() for safer access
                if doc_id and doc_id in ratings_agg:
                    agg_data = ratings_agg[doc_id]
                    doc['review_count'] = agg_data['count']
                    if agg_data['count'] > 0:
                         doc['average_rating'] = round(agg_data['total'] / agg_data['count'], 1)
                else:
                    # Ensure keys exist even if no ratings found
                    doc['review_count'] = 0
                    doc['average_rating'] = 0.0
        else:
             print("DEBUG: No approved reviews found in 'reviews' table.") # DEBUG

        print(f"Loaded {len(doctors_list)} doctors from Supabase with rating info.")
        return doctors_list

    except Exception as e: # Catch Supabase client errors or other exceptions
        print(f"CRITICAL: Supabase error loading doctors data:")
        traceback.print_exc() # Print full traceback
        flash(f'Error loading doctor data from Supabase: {e}', 'error')
        return [] # Return empty list on failure

# --- Function to get current doctors_data (replace global variable access) ---
def get_current_doctors_data():
    """ Central function to retrieve doctor data, potentially with caching later """
    return load_doctors_from_db()


# --- Jinja Helper Function for Stars (Unchanged) ---
@app.context_processor
def utility_processor():
    def get_stars(rating):
        if rating is None or not isinstance(rating, (int, float)) or rating < 0: return ['far fa-star'] * 5
        rating = max(0, min(5, float(rating)))
        full = math.floor(rating); half = (rating - full) >= 0.5; empty = 5 - full - (1 if half else 0)
        stars = ['fas fa-star'] * full + (['fas fa-star-half-alt'] if half else []) + ['far fa-star'] * empty
        return stars
    return dict(get_stars=get_stars)

# --- Routes ---
@app.route('/')
def home():
    print("\n--- Loading '/' Home Route ---") # DEBUG
    doctors_data = get_current_doctors_data() # Fetch current data
    stats = { 'doctor_count': len(doctors_data), 'specialty_count': 0, 'total_bookings': 0, 'total_active_bookings': 0, 'review_count': 0 } # Add review_count default
    specialties = []
    governorates = []
    facility_types = []
    plcs = []
    site_reviews = [] # Start with empty list

    if doctors_data:
        try:
            # Generate unique filter options
            unique_specs = sorted(list({d['specialization'] for d in doctors_data if d.get('specialization')}))
            unique_govs = sorted(list({d['governorate'] for d in doctors_data if d.get('governorate')}))
            unique_fac_types = sorted(list({d['facility_type'] for d in doctors_data if d.get('facility_type')}))
            unique_plcs = sorted(list({d['plc'] for d in doctors_data if d.get('plc')}))
            stats['specialty_count'] = len(unique_specs)
            specialties = unique_specs; governorates = unique_govs; facility_types = unique_fac_types; plcs = unique_plcs
        except Exception as e: print(f"Warn: Error processing doctors_data for filters: {e}")

    # --- Fetch Counts & Site Reviews from Supabase ---
    try:
        print("DEBUG: Fetching booking counts...") # DEBUG
        response_active = supabase.table('bookings').select('id', count='exact').neq('status', 'Cancelled').execute()
        stats['total_active_bookings'] = response_active.count if hasattr(response_active, 'count') else 0
        print(f"DEBUG: Active bookings count: {stats['total_active_bookings']}") # DEBUG

        response_all = supabase.table('bookings').select('id', count='exact').execute()
        stats['total_bookings'] = response_all.count if hasattr(response_all, 'count') else 0
        print(f"DEBUG: Total bookings count: {stats['total_bookings']}") # DEBUG

        print("DEBUG: Fetching site reviews with is_approved = 1 (integer)...") # DEBUG
        # *** FIX 2: Use integer 1 for is_approved check ***
        response_site_reviews = supabase.table('site_reviews').select(
            'reviewer_name, rating, comment, created_at' # Check columns exist in DB
            ).eq('is_approved', 1).order('created_at', desc=True).limit(3).execute() # Check is_approved status in DB, Use 1 instead of True

        print(f"DEBUG: Supabase response for site_reviews: {response_site_reviews}") # DEBUG: Print the raw response

        if response_site_reviews.data:
             site_reviews = response_site_reviews.data
             # Also calculate total review count for stats (can be site or doctor reviews, depending on what you mean by stats.review_count)
             # Let's assume stats.review_count is specifically for SITE reviews shown on homepage
             stats['review_count'] = len(site_reviews)
             print(f"DEBUG: Successfully fetched {len(site_reviews)} approved site reviews.") # DEBUG
        else:
             print("DEBUG: No site reviews found matching criteria (is_approved=1) or query failed silently.") # DEBUG
             # Optionally log response status or error details if available in response object
             if hasattr(response_site_reviews, 'error') and response_site_reviews.error:
                   print(f"DEBUG: Site reviews fetch error detail: {response_site_reviews.error}")
                   flash('Error fetching site reviews.', 'error')


    except Exception as e: # Catch Supabase or other errors
        print(f"ERROR: Exception while fetching stats/site reviews for home:") # DEBUG
        traceback.print_exc() # DEBUG: Print full traceback
        flash('Could not load current statistics or site reviews.', 'warning')
        # site_reviews remains []

    print(f"DEBUG: Passing to index.html -> stats: {stats}, site_reviews count: {len(site_reviews)}") # DEBUG
    return render_template(
        'index.html',
        doctors=doctors_data,
        stats=stats,
        specialties=specialties, governorates=governorates, facility_types=facility_types, plcs=plcs,
        site_reviews=site_reviews # Pass the potentially empty list
    )


# --- NEW: Submit Site Review Route ---
@app.route('/submit-site-review', methods=['POST'])
def submit_site_review():
    reviewer_name = request.form.get('reviewer_name', '').strip()
    rating_str = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    errors = []
    rating = None
    if not reviewer_name: errors.append('Your name is required.')
    try:
        rating = int(rating_str)
        if not (1 <= rating <= 5): errors.append('Valid rating (1-5 stars) required.')
    except (ValueError, TypeError): errors.append('Valid rating (1-5 stars) required.')

    if errors:
        for error in errors: flash(f'⛔ {error}', 'error')
        return redirect(url_for('home') + '#site-review-form-section')

    try:
        # Insert with is_approved=1 if you want it approved by default,
        # or rely on DB default (often 0/NULL if not set)
        # If DB default is 0/NULL, reviews won't show until manually approved in Supabase dashboard.
        # Let's assume we want them approved by default for now.
        insert_payload = {
            'reviewer_name': reviewer_name,
            'rating': rating,
            'comment': comment,
            'is_approved': 1 # Explicitly set to approved (integer 1)
        }
        print(f"DEBUG: Attempting to insert site review: {insert_payload}") # DEBUG
        response = supabase.table('site_reviews').insert(insert_payload).execute()
        print(f"DEBUG: Site review insert response: {response}") # DEBUG

        if response.data:
             print(f"Site review added by {reviewer_name} via Supabase.")
             flash('✅ Thank you for your feedback!', 'success')
        else:
            # Check for specific error messages if available
            error_message = "Could not save review due to an unexpected issue."
            if hasattr(response, 'error') and response.error:
                error_message = f"Could not save review: {response.error.get('message', 'Unknown DB error')}"
                print(f"ERROR: Supabase site review insert failed: {response.error}")
            else:
                 print(f"Warn: Supabase site review insert for {reviewer_name} returned no data. Response: {response}")
            flash(f'⛔ {error_message}', 'error')


    except Exception as e:
        print(f"Error submitting site review to Supabase:")
        traceback.print_exc() # Print full traceback
        # Try to extract more specific error from Supabase exception if possible
        error_detail = str(e)
        if hasattr(e, 'details'): error_detail = f"{e} - {e.details}"
        if hasattr(e, 'message'): error_detail = e.message
        flash(f'⛔ Database error submitting your feedback: {error_detail}', 'error')


    return redirect(url_for('home') + '#site-reviews-section')


# --- DOCTOR Review Submission Route ---
@app.route('/submit-review', methods=['POST'])
def submit_review():
    # (Code for doctor review submission - seems okay based on last interaction)
    # Add debug prints similar to submit_site_review if needed
    # ... existing code ...
    print("\n--- Received POST to /submit-review ---") # DEBUG
    doctor_id_str = request.form.get('doctor_id')
    reviewer_name = request.form.get('reviewer_name', '').strip()
    reviewer_phone = request.form.get('reviewer_phone', '').strip()
    rating_str = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    # Print received form data
    print(f"DEBUG: Form Data - doctor_id='{doctor_id_str}', name='{reviewer_name}', phone='{reviewer_phone}', rating='{rating_str}', comment='{comment[:50]}...'")

    # --- Basic Validation ---
    errors = []; doctor_id = None; rating = None
    try: doctor_id = int(doctor_id_str)
    except (ValueError, TypeError): errors.append('Invalid Doctor ID.')
    if not reviewer_name: errors.append('Your name is required.')
    if not reviewer_phone: errors.append('Your phone number is required.') # Keep required
    try:
        rating = int(rating_str)
        if not (1 <= rating <= 5): errors.append('Valid rating (1-5 stars) required.')
    except (ValueError, TypeError): errors.append('Valid rating (1-5 stars) required.')

    if errors:
        print(f"DEBUG: Validation Errors: {errors}") # DEBUG
        for error in errors: flash(f'⛔ {error}', 'error')
        redirect_url = url_for('booking_page', doctor_id=doctor_id) if doctor_id else url_for('home')
        # Use request.referrer to redirect back to the booking page
        return redirect(request.referrer or redirect_url)
    # --- End Validation ---

    try:
        print(f"DEBUG: Attempting checks for Dr {doctor_id}, Reviewer {reviewer_name}/{reviewer_phone}") # DEBUG

        # *** CHECK 1: Already reviewed? ***
        # This check does NOT consider approval status, which is probably correct.
        # We don't want multiple submissions even if the first isn't approved yet.
        print("DEBUG: Check 1 - Checking for existing review...") # DEBUG
        check_review_response = supabase.table('reviews').select('id', count='exact').eq('doctor_id', doctor_id).or_(
            f'reviewer_name.eq.{reviewer_name}', f'reviewer_phone.eq.{reviewer_phone}'
        ).limit(1).execute()
        print(f"DEBUG: Check 1 Response: {check_review_response}") # DEBUG
        if check_review_response.count > 0: # Check count attribute
             flash('⛔ You have already reviewed this doctor using this name or phone.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))

        # *** CHECK 2: Latest booking ***
        print("DEBUG: Check 2 - Checking for latest booking...") # DEBUG
        check_booking_response = supabase.table('bookings').select('booking_date, booking_time').eq(
             'doctor_id', doctor_id).or_(
             f'patient_name.eq.{reviewer_name}', f'patient_phone.eq.{reviewer_phone}' # Make sure case sensitivity is handled if needed
             ).neq('status', 'Cancelled').order('booking_date', desc=True).order(
                 'booking_time', desc=True
             ).limit(1).execute()
        print(f"DEBUG: Check 2 Response: {check_booking_response}") # DEBUG
        if not check_booking_response.data:
             flash('⛔ No booking found for you with this doctor. Book first to review.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        latest_booking = check_booking_response.data[0]
        print(f"DEBUG: Latest booking found: {latest_booking}") # DEBUG

        # *** CHECK 3: Appointment time passed? ***
        print("DEBUG: Check 3 - Checking appointment time...") # DEBUG
        try:
            booking_date_str = latest_booking['booking_date']
            booking_time_slot = latest_booking['booking_time'] # e.g., "09:00-09:20"
            booking_start_time_str = booking_time_slot.split('-')[0].strip()
            appointment_datetime_str = f"{booking_date_str} {booking_start_time_str}"
            appointment_start_dt = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M')
            now_dt = datetime.now()

            # Allow review slightly before appointment end? Add a grace period if needed
            # grace_period = timedelta(minutes=-10) # Allow review 10 mins before start? Probably not needed.
            if now_dt < appointment_start_dt: # Only allow review strictly AFTER start time
                time_fmt = appointment_start_dt.strftime('%I:%M %p on %b %d, %Y')
                flash(f'⛔ Cannot review until after your appointment starts ({time_fmt}).', 'error')
                return redirect(url_for('booking_page', doctor_id=doctor_id))
        except (ValueError, IndexError, TypeError) as e:
             print(f"Error parsing booking time for review check {latest_booking}: {e}")
             flash('⛔ Could not verify appointment time. Contact support.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))

        # --- If all checks passed, Insert the DOCTOR review ---
        print("DEBUG: All checks passed. Attempting insert...") # DEBUG
        insert_data = {
            'doctor_id': doctor_id,
            'reviewer_name': reviewer_name,
            'reviewer_phone': reviewer_phone,
            'rating': rating,
            'comment': comment,
            'is_approved': 1 # Explicitly set to approved (integer 1), or 0 if you want manual approval
        }
        print(f"DEBUG: Insert Data Payload: {insert_data}") # DEBUG

        insert_response = supabase.table('reviews').insert(insert_data).execute()

        print(f"DEBUG: Insert Response: {insert_response}") # DEBUG crucial line!

        if insert_response.data:
             flash('✅ Thank you! Your review has been submitted.', 'success')
             print(f"Doctor review added for Dr {doctor_id} by {reviewer_name}.")
        else:
            # Check for specific error messages if available
            error_message = "Failed to submit review due to an unexpected database issue."
            if hasattr(insert_response, 'error') and insert_response.error:
                error_message = f"Failed to submit review: {insert_response.error.get('message', 'Unknown DB error')}"
                print(f"ERROR: Supabase review insert failed: {insert_response.error}")
            else:
                 print(f"Warn: Supabase review insert failed or returned no data. Dr {doctor_id}, User {reviewer_name}. Response: {insert_response}")
            flash(f'⛔ {error_message}', 'error')


    except Exception as e: # Catch Supabase client errors or others
        print(f"ERROR submitting doctor review to Supabase (Dr {doctor_id}):") # DEBUG
        traceback.print_exc() # DEBUG - Prints full traceback
        # Extract specific error
        error_detail = str(e)
        if hasattr(e, 'details'): error_detail = f"{e} - {e.details}"
        if hasattr(e, 'message'): error_detail = e.message
        flash(f'⛔ Database error submitting review: {error_detail}.', 'error')

    print("--- /submit-review finished ---") # DEBUG
    return redirect(url_for('booking_page', doctor_id=doctor_id))



# --- /booking route ---
@app.route('/booking/<int:doctor_id>')
def booking_page(doctor_id):
    # (Make sure debug prints are present in this route too, as per previous suggestions)
    # ... existing /booking/<id> code ...
    print(f"\n--- Loading Booking Page for Doctor ID: {doctor_id} ---") # DEBUG
    doctor = None
    reviews = []
    # --- Fetch Doctor Details directly from Supabase ---
    try:
        print("DEBUG: Fetching doctor details...") # DEBUG
        doc_response = supabase.table('doctors').select('*').eq('id', doctor_id).maybe_single().execute()
        # print(f"DEBUG: Doctor fetch response: {doc_response}") # Might be too verbose
        doctor = doc_response.data # Returns dict directly or None if not found

        if doctor:
             print("DEBUG: Doctor found. Processing details...") # DEBUG
             if not isinstance(doctor.get('availability'), dict):
                 doctor['availability'] = {}

             # --- Rating Calculation ---
             print("DEBUG: Calculating doctor rating...") # DEBUG
             # *** FIX 3: Use integer 1 for is_approved check ***
             individual_ratings_response = supabase.table('reviews').select('rating').eq('doctor_id', doctor_id).eq('is_approved', 1).execute() # Use 1
             if individual_ratings_response.data:
                 valid_ratings = [r['rating'] for r in individual_ratings_response.data if isinstance(r.get('rating'), (int, float)) and 1 <= r.get('rating') <= 5]
                 count = len(valid_ratings)
                 total_rating = sum(valid_ratings)
                 doctor['review_count'] = count
                 doctor['average_rating'] = round(total_rating / count, 1) if count > 0 else 0.0
                 print(f"DEBUG: Rating calculated - Avg: {doctor['average_rating']}, Count: {count}") # DEBUG
             else:
                 doctor['review_count'] = 0
                 doctor['average_rating'] = 0.0
                 print("DEBUG: No approved ratings found for doctor.") # DEBUG

             # Fetch recent approved reviews for display
             print(f"DEBUG: Attempting to fetch reviews for doctor {doctor_id}...") # DEBUG
             # *** FIX 4: Use integer 1 for is_approved check ***
             reviews_response = supabase.table('reviews').select(
                 'reviewer_name, rating, comment, created_at'
                 ).eq('doctor_id', doctor_id).eq('is_approved', 1).order( # Use 1
                     'created_at', desc=True
                 ).limit(10).execute()

             print(f"DEBUG: Supabase response for DOCTOR reviews query: {reviews_response}") # DEBUG
             reviews = reviews_response.data or [] # Ensure reviews is a list
             print(f"DEBUG: Final DOCTOR 'reviews' list extracted (Count: {len(reviews)})") # DEBUG

        else:
            print(f"DEBUG: Doctor with ID {doctor_id} not found in Supabase.") # DEBUG
            flash('Doctor not found.', 'error')
            return redirect(url_for('home'))

    except Exception as e:
        print(f"ERROR fetching booking page data for {doctor_id}:") # DEBUG
        traceback.print_exc() # DEBUG
        flash(f'Error loading doctor details or reviews: {e}', 'error')
        return redirect(url_for('home')) # Redirect on error

    # --- Prepare response ---
    today_str = date.today().strftime('%Y-%m-%d')
    # Make sure availability is a dict before dumps
    doctor_availability_schedule_for_js = json.dumps(doctor.get('availability', {}))

    print(f"DEBUG: Passing to booking.html - doctor: {'Exists' if doctor else 'None'}, reviews count: {len(reviews)}") # DEBUG
    print("--- Finished loading Booking Page data ---") # DEBUG

    response = make_response(render_template(
        'booking.html', doctor=doctor, doctor_id=doctor_id, today=today_str,
        doctor_availability_schedule=doctor_availability_schedule_for_js,
        reviews=reviews # Pass the list
    ))
    # Add Cache-Control headers to prevent stale data issues
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    # ... (cookie setting logic if any) ...
    return response

# --- Routes: center_details, get_nearest_available, get_available_slots ---
# (Keep existing code - Add print/traceback if debugging needed)
# ...

@app.route('/center/<path:plc_name>')
def center_details(plc_name):
    if not plc_name: flash('No clinic name provided.', 'error'); return redirect(url_for('home'))

    plc_doctors = []
    plc_info = {}
    try:
        # Fetch doctors filtered by PLC name from Supabase
        response = supabase.table('doctors').select('*').eq('plc', plc_name).execute()
        plc_doctors = response.data

        if not plc_doctors:
             flash(f'Details not found for clinic/center "{plc_name}".', 'error')
             return redirect(url_for('home'))

        # Add rating calculation here if needed for each doctor in list
        for doc in plc_doctors:
             # *** FIX 5: Use integer 1 for is_approved check ***
             rating_res = supabase.table('reviews').select('rating', count='exact').eq('doctor_id', doc['id']).eq('is_approved', 1).execute() # Use 1
             doc['review_count'] = rating_res.count
             if rating_res.count > 0:
                  # *** FIX 6: Use integer 1 for is_approved check ***
                  avg_res = supabase.table('reviews').select('rating').eq('doctor_id', doc['id']).eq('is_approved', 1).execute() # Use 1
                  valid_ratings = [r['rating'] for r in avg_res.data if isinstance(r.get('rating'), (int, float)) and 1 <= r.get('rating') <= 5]
                  if valid_ratings: doc['average_rating'] = round(sum(valid_ratings) / len(valid_ratings), 1)
                  else: doc['average_rating'] = 0.0
             else: doc['average_rating'] = 0.0

        first_doc = plc_doctors[0]
        unique_locations = sorted(list({ (d.get('province'), d.get('governorate')) for d in plc_doctors if d.get('province') or d.get('governorate')}))
        plc_info = { 'name': plc_name, 'facility_type': first_doc.get('facility_type', 'N/A'), 'locations': unique_locations }
        plc_slug = plc_name.lower().replace(' ', '_').replace('&', 'and').replace('.', '').replace("'", '')
        plc_info['photo_path_jpg'] = f'/static/plc_photos/{plc_slug}.jpg'

    except Exception as e:
        print(f"Supabase error fetching doctors for center '{plc_name}':")
        traceback.print_exc()
        flash('Error loading center details.', 'error')
        return redirect(url_for('home'))

    return render_template('center_details.html', plc=plc_info, doctors=plc_doctors)


# --- Helper Function: Get Doctor Availability ---
def get_doctor_availability_from_supabase(doctor_id):
     """ Fetches just the availability schedule for a single doctor """
     try:
          response = supabase.table('doctors').select('availability').eq('id', doctor_id).maybe_single().execute()
          if response.data and isinstance(response.data.get('availability'), dict):
               return response.data['availability']
          else:
               # print(f"Warn: Availability not found or not a dict for doctor {doctor_id}")
               return {}
     except Exception as e:
          print(f"Supabase error fetching availability for doctor {doctor_id}: {e}")
          return {}

# --- Routes: get_nearest_available, get_available_slots, confirm_booking ---
# (Keep existing code, add tracing if problems arise here)
# ... (existing code) ...


@app.route('/get-nearest-available/<int:doctor_id>')
def get_nearest_available(doctor_id):
    # Fetch doctor's general availability schedule
    doctor_availability = get_doctor_availability_from_supabase(doctor_id)
    if not doctor_availability:
        # Specific message based on whether the fetch failed or just had no schedule
        try:
             doc_exists_res = supabase.table('doctors').select('id', count='exact').eq('id', doctor_id).execute()
             if doc_exists_res.count == 0:
                   return jsonify({'success': False, 'message': 'Doctor not found'}), 404
             else:
                  return jsonify({'success': False, 'message': 'Doctor schedule unavailable.'}), 404
        except Exception as e:
             print(f"Error checking doctor existence in get_nearest_available: {e}")
             return jsonify({'success': False, 'message': 'Database check error.'}), 500

    today_date = date.today()
    now_time = datetime.now().time()

    try:
        # Iterate through days looking for a free slot
        for i in range(90): # Look ahead 90 days
            current_check_date = today_date + timedelta(days=i)
            date_str = current_check_date.strftime('%Y-%m-%d')
            day_name = current_check_date.strftime('%A')

            general_slots_raw = doctor_availability.get(day_name, [])
            general_slots = sorted([ s for s in general_slots_raw if isinstance(s, str) and s.strip() and s.lower() != "unavailable" and '-' in s])
            if not general_slots: continue

            # Fetch booked times for this doctor ON THIS SPECIFIC DATE
            response_booked = supabase.table('bookings').select('booking_time').eq(
                'doctor_id', doctor_id).eq('booking_date', date_str).neq(
                    'status', 'Cancelled').execute()
            booked_times = {row['booking_time'] for row in response_booked.data}

            # Find the first available slot
            for slot in general_slots:
                if slot not in booked_times:
                    # Check if the slot start time is in the future for today's date
                    if current_check_date == today_date:
                        try:
                            slot_start_str = slot.split('-')[0].strip()
                            slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                            if slot_start_time > now_time:
                                return jsonify({'success': True, 'date': date_str, 'time': slot})
                        except (ValueError, IndexError):
                            print(f"Warn: Could not parse slot '{slot}' for time comparison in get_nearest_available.")
                            # Optionally allow booking if parse fails, or skip
                            # return jsonify({'success': True, 'date': date_str, 'time': slot}) # Allow booking if parse fails
                    else: # If it's a future date, any available slot is fine
                        return jsonify({'success': True, 'date': date_str, 'time': slot})


        return jsonify({'success': False, 'message': 'No available slots found soon.'}), 404

    except Exception as e:
        print(f"Error in get_nearest_available for Dr {doctor_id}:")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'An internal server error occurred: {e}'}), 500


@app.route('/get-available-slots/<int:doctor_id>/<string:date_str>')
def get_available_slots(doctor_id, date_str):
    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = booking_date.strftime('%A')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    doctor_availability = get_doctor_availability_from_supabase(doctor_id)
    if not doctor_availability:
         try:
             doc_exists_res = supabase.table('doctors').select('id', count='exact').eq('id', doctor_id).execute()
             if doc_exists_res.count == 0: return jsonify({'error': 'Doctor not found'}), 404
             else: return jsonify([]) # No schedule defined for doctor
         except Exception as e:
             print(f"Error checking doctor existence in get_available_slots: {e}")
             return jsonify({'error': 'Database check error.'}), 500

    general_slots_raw = doctor_availability.get(day_name, [])
    general_slots = sorted([ s for s in general_slots_raw if isinstance(s, str) and s.strip() and s.lower() != "unavailable" and '-' in s])
    if not general_slots: return jsonify([]) # No slots defined for this day

    try:
        # Fetch booked times
        response_booked = supabase.table('bookings').select('booking_time').eq(
            'doctor_id', doctor_id).eq('booking_date', date_str).neq('status', 'Cancelled').execute()
        booked_times = {row['booking_time'] for row in response_booked.data}

        available_slots = [slot for slot in general_slots if slot not in booked_times]

        # Filter past times if the date is today
        if booking_date == date.today():
             now_time = datetime.now().time()
             future_slots = []
             for slot in available_slots:
                try:
                    slot_start_str = slot.split('-')[0].strip()
                    slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                    if slot_start_time > now_time:
                        future_slots.append(slot)
                except (ValueError, IndexError):
                    print(f"Warn: Parse error on slot '{slot}' for today filter in get_available_slots.")
                    # Decide whether to include slots that can't be parsed for today
                    # future_slots.append(slot) # Option: Include if parsing fails
             available_slots = future_slots

        return jsonify(available_slots)

    except Exception as e:
        print(f"Supabase error fetching booked times for {doctor_id} on {date_str}:")
        traceback.print_exc()
        return jsonify([]) # Return empty on error

@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    # --- Get Data (Unchanged) ---
    doctor_id_str = request.form.get('doctor_id')
    doctor_name = request.form.get('doctor_name')
    patient_name = request.form.get('patient_name', '').strip()
    patient_phone = request.form.get('patient_phone', '').strip()
    booking_date = request.form.get('booking_date')
    booking_time = request.form.get('booking_time')
    notes = request.form.get('notes', '').strip()
    fingerprint = request.form.get('fingerprint')
    cookie_id = request.cookies.get('device_id')
    ip_address = request.remote_addr

    # --- Basic Validation ---
    if not all([doctor_id_str, patient_name, patient_phone, booking_date, booking_time]):
        flash('⛔ Ensure name, phone, date, and time are filled.', 'error')
        referrer_url = request.referrer or url_for('home')
        if doctor_id_str and doctor_id_str.isdigit():
             try: referrer_url = url_for('booking_page', doctor_id=int(doctor_id_str))
             except: pass
        return redirect(referrer_url)
    try:
        doctor_id = int(doctor_id_str)
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()

        # Time validation - compare date and time slot start
        now_dt = datetime.now()
        slot_start_time = None
        if booking_time and '-' in booking_time:
            try:
                slot_start_str = booking_time.split('-')[0].strip()
                slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                booking_start_dt = datetime.combine(booking_date_obj, slot_start_time)
            except ValueError:
                 flash('⛔ Invalid booking time format.', 'error')
                 return redirect(url_for('booking_page', doctor_id=doctor_id))
        else:
             flash('⛔ Invalid booking time format selected.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))

        if booking_start_dt < now_dt:
             flash('⛔ Cannot book an appointment in the past.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))

        selected_day_name = booking_date_obj.strftime('%A')
    except (ValueError, TypeError):
         flash('⛔ Invalid Doctor ID or Date format.', 'error')
         redir_url = url_for('booking_page', doctor_id=doctor_id) if 'doctor_id' in locals() else url_for('home')
         return redirect(request.referrer or redir_url)

    # --- Find Doctor & Validate Slot ---
    fetched_doctor_name = None # Define outside try block
    try:
         doc_response = supabase.table('doctors').select('availability, name').eq('id', doctor_id).maybe_single().execute()
         if not doc_response.data:
             flash(f'⛔ Doctor with ID {doctor_id} not found.', 'error'); return redirect(url_for('home'))
         doctor_schedule = doc_response.data.get('availability', {})
         fetched_doctor_name = doc_response.data.get('name') # Get name from DB
         if not isinstance(doctor_schedule, dict): doctor_schedule = {}

         day_schedule = doctor_schedule.get(selected_day_name, [])
         general_slots = [s for s in day_schedule if isinstance(s, str) and s.strip() and s.lower() != 'unavailable' and '-' in s]
         if booking_time not in general_slots:
             flash('⛔ Slot not valid for this doctor/date.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))

         # Validate again that the chosen slot is available for the specific time (for today)
         if booking_date_obj == date.today() and slot_start_time < datetime.now().time():
              flash('⛔ That time slot has just passed. Please select a later time.', 'error')
              return redirect(url_for('booking_page', doctor_id=doctor_id))


    except Exception as e:
         print(f"Error verifying doctor/schedule {doctor_id}:")
         traceback.print_exc()
         flash(f'⛔ Error validating doctor/slot: {e}', 'error')
         return redirect(url_for('booking_page', doctor_id=doctor_id))

    # --- Database Interaction (Supabase) ---
    try:
        # ** CHECK 1: Slot booked? **
        print(f"DEBUG: Checking if slot {booking_time} on {booking_date} for Dr {doctor_id} is already booked...") # DEBUG
        check_slot_response = supabase.table('bookings').select('id', count='exact').eq('doctor_id', doctor_id).eq('booking_date', booking_date).eq('booking_time', booking_time).neq('status', 'Cancelled').execute()
        print(f"DEBUG: Slot check response: {check_slot_response}") # DEBUG
        if check_slot_response.count > 0:
             flash('⛔ Slot just booked by someone else. Please select another time.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))

        # ** CHECK 2: Patient already booked this DATE? **
        print(f"DEBUG: Checking if patient {patient_name}/{patient_phone} already booked Dr {doctor_id} on {booking_date}...") # DEBUG
        check_patient_date_response = supabase.table('bookings').select('booking_time', count='exact').eq('doctor_id', doctor_id).eq('booking_date', booking_date).or_(f'patient_name.eq.{patient_name}', f'patient_phone.eq.{patient_phone}').neq('status', 'Cancelled').execute()
        print(f"DEBUG: Patient date check response: {check_patient_date_response}") # DEBUG
        if check_patient_date_response.count > 0:
             existing_time = check_patient_date_response.data[0]['booking_time'] if check_patient_date_response.data else "N/A"
             flash(f'ℹ️ You already have a booking with this doctor on this date at {existing_time}. Only one booking per day per doctor is allowed.', 'info'); return redirect(url_for('booking_page', doctor_id=doctor_id))

        # --- Insert the Booking ---
        print("DEBUG: Attempting to insert booking...") # DEBUG
        insert_data = { 'doctor_id': doctor_id, 'doctor_name': fetched_doctor_name or doctor_name, 'patient_name': patient_name, 'patient_phone': patient_phone, 'booking_date': booking_date, 'booking_time': booking_time, 'notes': notes, 'status': 'Pending', 'ip_address': ip_address, 'cookie_id': cookie_id, 'fingerprint': fingerprint }
        insert_data_clean = {k: v for k, v in insert_data.items() if v is not None}
        print(f"DEBUG: Booking insert payload: {insert_data_clean}") # DEBUG
        response_insert = supabase.table('bookings').insert(insert_data_clean).execute()
        print(f"DEBUG: Booking insert response: {response_insert}") # DEBUG

        if response_insert.data and len(response_insert.data) > 0 and 'id' in response_insert.data[0]:
            booking_id = response_insert.data[0]['id']
            print(f"Booking confirmed (Supabase): ID {booking_id}, Dr {doctor_id}, P {patient_name}, {booking_date} {booking_time}")
            flash('✅ Booking confirmed!', 'success')
            return redirect(url_for('confirmation', booking_id=booking_id, doctor_name=fetched_doctor_name or doctor_name, patient_name=patient_name, booking_date=booking_date, booking_time=booking_time))
        else:
            error_message = "Booking failed due to database issue."
            if hasattr(response_insert, 'error') and response_insert.error:
                error_message = f"Booking failed: {response_insert.error.get('message', 'Unknown DB error')}"
                print(f"ERROR: Supabase booking insert failed: {response_insert.error}")
            else:
                 print(f"Error: Supabase booking insert failed or returned unexpected data. Resp: {response_insert}")
            flash(f'⛔ {error_message}', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))

    except Exception as e:
        print(f"Error confirming booking via Supabase for Dr {doctor_id}:")
        traceback.print_exc()
        error_detail = str(e)
        if hasattr(e, 'details'): error_detail = f"{e} - {e.details}"
        if hasattr(e, 'message'): error_detail = e.message
        flash(f'⛔ Error confirming booking: {error_detail}.', 'error')
        return redirect(url_for('booking_page', doctor_id=doctor_id))


@app.route('/confirmation')
def confirmation():
    # (Keep existing code)
    # ...
    booking_id = request.args.get('booking_id')
    doctor_name = request.args.get('doctor_name')
    patient_name = request.args.get('patient_name')
    booking_date = request.args.get('booking_date')
    booking_time = request.args.get('booking_time')

    if not all([booking_id, doctor_name, patient_name, booking_date, booking_time]):
        flash('Invalid confirmation link or missing details.', 'error')
        return redirect(url_for('home'))

    return render_template('confirmation.html', booking_id=booking_id, doctor_name=doctor_name,
                           patient_name=patient_name, booking_date=booking_date, booking_time=booking_time)


@app.route('/get-doctor-availability/<int:doctor_id>')
def get_doctor_availability(doctor_id):
    # (Keep existing code)
    # ...
    doctor_schedule = get_doctor_availability_from_supabase(doctor_id)
    if not doctor_schedule:
         try:
             doc_exists_res = supabase.table('doctors').select('id', count='exact').eq('id', doctor_id).execute()
             if doc_exists_res.count == 0: return jsonify({'error': 'Doctor not found'}), 404
             else: return jsonify({}) # Doctor exists but has no schedule data
         except Exception as e:
             print(f"Error checking doctor existence in get_doc_availability: {e}")
             return jsonify({'error': 'DB Error'}), 500

    availability_data = defaultdict(list)
    today_dt = date.today(); end_date = today_dt + timedelta(days=120); current_date_loop = today_dt
    while current_date_loop <= end_date:
        day_name = current_date_loop.strftime('%A')
        general_slots_raw = doctor_schedule.get(day_name, [])
        # Filter out "unavailable" or empty strings, check for valid format
        valid_slots = [slot for slot in general_slots_raw if isinstance(slot, str) and slot.strip() and slot.lower() != "unavailable" and '-' in slot]

        if valid_slots: # Check if there are any valid slots for the day
             month_str = current_date_loop.strftime('%Y-%m'); day_num = current_date_loop.day
             availability_data[month_str].append(day_num)

        current_date_loop += timedelta(days=1)
    return jsonify(dict(availability_data))


@app.route('/delete-booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    # (Keep existing code)
    # ...
    source = request.form.get('source', 'unknown')
    patient_identifier = request.form.get('patient_identifier')
    doctor_id_str = request.form.get('doctor_id')
    redirect_url = url_for('home')
    if source == 'patient_dashboard' and patient_identifier: redirect_url = url_for('patient_dashboard', patient_identifier=patient_identifier)
    elif source == 'doctor_dashboard' and doctor_id_str and doctor_id_str.isdigit(): redirect_url = url_for('doctor_dashboard', doctor_id=int(doctor_id_str))
    elif source == 'confirmation_page': redirect_url = url_for('home')

    try:
        # Ensure we only cancel 'Pending' bookings
        response = supabase.table('bookings').update({'status': 'Cancelled'}).eq('id', booking_id).eq('status', 'Pending').execute()

        if response.data and len(response.data) > 0: # Check if update actually happened
            flash('✅ Booking successfully cancelled.', 'success')
            print(f"Booking {booking_id} status changed to Cancelled (Supabase).")
        else:
            # Check why it failed (not found, or already not Pending)
            status_response = supabase.table('bookings').select('status').eq('id', booking_id).maybe_single().execute()
            if status_response.data:
                current_status = status_response.data['status']
                if current_status == 'Cancelled': flash('ℹ️ Booking was already cancelled.', 'info')
                elif current_status == 'Completed': flash('ℹ️ Cannot cancel a completed booking.', 'info')
                else: flash(f'ℹ️ Cannot cancel booking (Status: {current_status}). Refresh maybe?', 'info') # Should ideally not happen if eq('status', 'Pending') worked
            else:
                flash('⛔ Booking not found.', 'error')
                print(f"Warn: Attempted to cancel non-existent booking ID {booking_id}")

    except Exception as e:
        print(f"Error cancelling booking {booking_id} via Supabase:")
        traceback.print_exc()
        error_detail = str(e)
        if hasattr(e, 'details'): error_detail = f"{e} - {e.details}"
        if hasattr(e, 'message'): error_detail = e.message
        flash(f'⛔ Database error cancelling booking: {error_detail}', 'error')
    return redirect(redirect_url)


# --- Login & Dashboard Routes ---

@app.route('/doctor-login', methods=['GET', 'POST'])
def doctor_login():
    # (Keep existing code)
    # ...
    if request.method == 'POST':
        doctor_name = request.form.get('doctorName', '').strip()
        doctor_id_str = request.form.get('doctorId', '').strip()
        if not doctor_name or not doctor_id_str or not doctor_id_str.isdigit():
             flash('⛔ Enter both Name and numeric Doctor ID.', 'error'); return redirect(url_for('doctor_login'))
        doctor_id = int(doctor_id_str)
        try:
             # Select only needed fields, ensure names match case-insensitively if needed in DB setup
             response = supabase.table('doctors').select('id, name').eq('id', doctor_id).ilike('name', doctor_name).maybe_single().execute() # Use ilike for case-insensitive name match
             doctor = response.data
        except Exception as e:
             print(f"Supabase error during doctor login check {doctor_id}/{doctor_name}: {e}")
             flash(f'Database error during login: {e}', 'error'); return redirect(url_for('doctor_login'))

        if doctor:
             # Use the exact name casing from the DB for the welcome message
             db_doctor_name = doctor.get('name', doctor_name)
             print(f"Doctor login successful (Supabase): ID {doctor_id}, Name '{db_doctor_name}'"); flash(f'✅ Welcome back, {db_doctor_name}!', 'success')
             return redirect(url_for('doctor_dashboard', doctor_id=doctor_id))
        else:
             print(f"Doctor login failed (Supabase): ID {doctor_id}, Name '{doctor_name}'"); flash('⛔ Invalid Doctor Name or ID combination.', 'error')
             return redirect(url_for('doctor_login'))
    return render_template('doctor_login.html')

@app.route('/doctor-dashboard/<int:doctor_id>')
def doctor_dashboard(doctor_id):
    # (Keep existing code - Ensure error handling is robust)
    # ...
    doctor = None; bookings_rows = []; stats = defaultdict(int); appointments_per_day_data = defaultdict(int); unique_patients_set=set()
    try:
        doc_response = supabase.table('doctors').select('id, name').eq('id', doctor_id).maybe_single().execute()
        doctor = doc_response.data
        if not doctor: flash("⛔ Doctor not found.", "error"); return redirect(url_for('doctor_login'))

        # Fetch relevant bookings (avoid fetching cancelled ones upfront)
        bookings_response = supabase.table('bookings').select(
             'id, patient_name, patient_phone, booking_date, booking_time, notes, status'
             ).eq('doctor_id', doctor_id).neq('status', 'Cancelled').order(
                 'booking_date', desc=True).order(
                     'booking_time', desc=True).execute()
        bookings_rows = bookings_response.data

        # Calculate Stats
        today_date=date.today(); today_str=today_date.strftime('%Y-%m-%d'); one_week_later=today_date + timedelta(days=7); current_month_start = today_date.replace(day=1)
        stats['total_bookings_listed'] = len(bookings_rows) # Total non-cancelled listed

        for booking in bookings_rows:
            try:
                 dt_str = booking['booking_date']; status = booking['status'];
                 # Safely parse date
                 try:
                     dt_obj = datetime.strptime(dt_str, '%Y-%m-%d').date()
                 except (ValueError, TypeError):
                     print(f"Warn: Invalid date format '{dt_str}' for booking ID {booking.get('id')}. Skipping stats.")
                     continue # Skip this booking for stats calculation

                 if status == 'Pending':
                    if dt_obj >= today_date: stats['pending_upcoming_count'] += 1
                    if dt_str == today_str: stats['today_count'] += 1 # Only count pending for today? Or all? Let's count all non-cancelled for today.
                    if today_date <= dt_obj < one_week_later: stats['next_7_days_count'] += 1 # Count pending only? Let's count all non-cancelled.

                 if status == 'Completed': stats['completed_total_count'] += 1

                 # Stats independent of status (as long as not cancelled)
                 if dt_str == today_str: stats['all_today_count'] = stats.get('all_today_count', 0) + 1 # New stat: All non-cancelled today
                 if today_date <= dt_obj < one_week_later: stats['all_next_7_days_count'] = stats.get('all_next_7_days_count', 0) + 1 # New stat: All non-cancelled next 7 days

                 appointments_per_day_data[dt_str] += 1

                 # Unique patients this month (using phone if available, else name)
                 if dt_obj >= current_month_start:
                      p_id = booking.get('patient_phone') or booking.get('patient_name')
                      if p_id: unique_patients_set.add(p_id)

            except KeyError as e: print(f"Warn: Stat calc missing key {e} in booking ID {booking.get('id')}")
            except Exception as e: print(f"Warn: General stat calc error for booking ID {booking.get('id')}: {e}")

        stats['unique_patients_this_month'] = len(unique_patients_set)

    except Exception as e:
        print(f"Error loading Doctor Dashboard {doctor_id} from Supabase:")
        traceback.print_exc()
        flash(f'⛔ Error loading dashboard data: {e}', 'error')
        # Provide default empty structures to avoid template errors
        return render_template('doctor_dashboard.html',
                               doctor=doctor or {'id': doctor_id, 'name':'N/A'},
                               doctor_id=doctor_id,
                               bookings_by_month={},
                               stats={'total_bookings_listed': 0},
                               chart_config_daily={'labels': [], 'data': []})

    # Prepare Chart Data (Appointments per day for the next 7 days)
    chart_labels=[]; chart_data=[]; chart_today=date.today()
    for i in range(7):
        d = chart_today + timedelta(days=i); d_str = d.strftime('%Y-%m-%d')
        chart_labels.append(d.strftime('%a, %b %d')); chart_data.append(appointments_per_day_data[d_str]) # Uses count calculated above

    # Group Bookings by Month and then Date
    bookings_by_month = defaultdict(lambda: defaultdict(list))
    for booking in bookings_rows:
        try:
            booking_date_obj = datetime.strptime(booking['booking_date'], '%Y-%m-%d')
            month_year_key = booking_date_obj.strftime('%B %Y'); date_key = booking['booking_date']
            bookings_by_month[month_year_key][date_key].append(booking)
        except (ValueError, TypeError, KeyError) as e: print(f"Warn: Grouping err bk id {booking.get('id')}: {e}")
    # Sort months chronologically (most recent first)
    sorted_months = sorted(bookings_by_month.keys(), key=lambda my: datetime.strptime(my, '%B %Y'), reverse=True)
    # Sort dates within each month (most recent first)
    final_grouped_bookings = { m_key: dict(sorted(bookings_by_month[m_key].items(), reverse=True)) for m_key in sorted_months }

    return render_template('doctor_dashboard.html',
                           doctor=doctor,
                           doctor_id=doctor_id,
                           bookings_by_month=final_grouped_bookings,
                           stats=dict(stats), # Convert defaultdict to dict for template
                           chart_config_daily={'labels': chart_labels, 'data': chart_data})


@app.route('/update-all-notes', methods=['POST'])
def update_all_notes():
    # (Keep existing code)
    # ...
    if not request.is_json: return jsonify({'success': False, 'message': 'Request must be JSON.'}), 400
    data = request.get_json(); updates = data.get('updates', [])
    if not isinstance(updates, list): return jsonify({'success': False, 'message': 'Invalid format.'}), 400
    updated_count = 0; failed_ids = []
    for update in updates:
         booking_id = update.get('bookingId'); notes = update.get('notes')
         # Validate bookingId is numeric-like and notes is a string
         if isinstance(booking_id, (int, str)) and str(booking_id).isdigit() and isinstance(notes, str):
              try:
                   # Use maybe_single() if you need to check if the row exists, or just execute update
                   response = supabase.table('bookings').update({'notes': notes.strip()}).eq('id', int(booking_id)).execute()
                   # Check if update was successful (Supabase returns data on success)
                   if response.data and len(response.data) > 0:
                       updated_count += 1
                   else:
                       # Check if booking ID actually exists
                       check_exists = supabase.table('bookings').select('id', count='exact').eq('id', int(booking_id)).execute()
                       if check_exists.count == 0:
                           print(f"Warning: Tried to update notes for non-existent booking ID: {booking_id}")
                           failed_ids.append(booking_id)
                       else:
                            print(f"Warning: Note update for booking {booking_id} returned no data, assumed failed.")
                            failed_ids.append(booking_id)
              except Exception as e:
                   print(f"Error updating note for booking {booking_id}: {e}"); failed_ids.append(booking_id)
         else:
             print(f"Warning: Skipping invalid note update data: {update}"); failed_ids.append(booking_id or 'Unknown') # Avoid None in list

    print(f"Notes update attempted: {len(updates)}. Successful: {updated_count}. Failed: {len(failed_ids)}.")
    success_status = not failed_ids; message = f"{updated_count} notes saved."
    if failed_ids:
        message += f" Failed for {len(failed_ids)} bookings (IDs: {', '.join(map(str, failed_ids))})."
        flash(message, 'warning')
    elif updated_count > 0:
         flash(message, 'success')
    # else: No message if nothing was updated and nothing failed? Or maybe flash info?
    #    flash("No notes were submitted for update.", 'info')

    return jsonify({'success': success_status, 'message': message})


@app.route('/mark-complete/<int:booking_id>', methods=['POST'])
def mark_complete(booking_id):
    # (Keep existing code)
    # ...
    try:
        # Update status only if it's currently 'Pending'
        response = supabase.table('bookings').update({'status': 'Completed'}).eq('id', booking_id).eq('status', 'Pending').execute()

        if response.data and len(response.data) > 0: # Check if update succeeded
             print(f"Booking ID {booking_id} marked Complete (Supabase)."); return jsonify({'success': True, 'message': 'Marked completed.'})
        else:
             # If update failed, check the current status
             status_response = supabase.table('bookings').select('status').eq('id', booking_id).maybe_single().execute()
             if status_response.data:
                  current_status = status_response.data['status']; message = f'Cannot mark complete. Status: "{current_status}".'
                  print(f"Failed mark complete {booking_id}: Status is '{current_status}'"); return jsonify({'success': False, 'message': message}), 409 # Conflict
             else:
                  print(f"Failed mark complete {booking_id}: Not found."); return jsonify({'success': False, 'message': 'Booking not found.'}), 404 # Not Found
    except Exception as e:
        print(f"Error marking booking {booking_id} complete:"); traceback.print_exc()
        error_detail = str(e)
        if hasattr(e, 'details'): error_detail = f"{e} - {e.details}"
        if hasattr(e, 'message'): error_detail = e.message
        return jsonify({'success': False, 'message': f'Database error: {error_detail}'}), 500


@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        patient_identifier = request.form.get('patientIdentifier', '').strip()
        if not patient_identifier:
            flash('⛔ Enter Name or Phone Number.', 'error')
            return redirect(url_for('patient_login'))

        booking_exists = False
        try:
            print(f"DEBUG: Patient login check for identifier: '{patient_identifier}'") # DEBUG
            # *** FIX 7: Include filtered columns in select ***
            response = supabase.table('bookings').select(
                'id, patient_name, patient_phone', # Include columns used in or_
                count='exact'
                ).or_(
                    f'ilike.patient_name.%{patient_identifier}%', # Use ilike for case-insensitive partial match if desired, or eq for exact match
                    f'patient_phone.eq.{patient_identifier}' # Phone likely needs exact match
                ).neq('status', 'Cancelled').execute()
            print(f"DEBUG: Patient login check response: {response}") # DEBUG
            booking_exists = response.count > 0

        except Exception as e:
            print(f"Supabase Error during patient login check: {e}") # Print the actual error structure
            traceback.print_exc() # Get full traceback
            error_detail = str(e)
            if hasattr(e, 'details'): error_detail = f"{e} - {e.details}"
            if hasattr(e, 'message'): error_detail = e.message
            flash(f'⛔ Database error during login: {error_detail}.', 'error')
            return redirect(url_for('patient_login'))

        if booking_exists:
            print(f"Patient login success (Supabase): Identifier '{patient_identifier}' found active booking(s).")
            # Use the identifier directly for the dashboard URL
            return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
        else:
            print(f"Patient login fail (Supabase): No active bookings found for identifier '{patient_identifier}'")
            flash('⛔ No active bookings found for that Name or Phone Number.', 'error')
            return redirect(url_for('patient_login'))

    # For GET request
    return render_template('patient_login.html')


@app.route('/patient-dashboard/<path:patient_identifier>')
def patient_dashboard(patient_identifier):
    # (Keep existing code)
    # ...
    if not patient_identifier: flash('⛔ Missing identifier.', 'error'); return redirect(url_for('patient_login'))
    processed_bookings = []; db_error = False
    actual_patient_name = patient_identifier # Default display name

    try:
        print(f"DEBUG: Fetching bookings for patient identifier: '{patient_identifier}'") # DEBUG
        # Use ilike for name matching to be robust if identifier is name
        response = supabase.table('bookings').select(
            'id, doctor_id, doctor_name, patient_name, patient_phone, booking_date, booking_time, status, notes'
            ).or_(
                f'ilike.patient_name.%{patient_identifier}%', # Case-insensitive partial name match
                f'patient_phone.eq.{patient_identifier}' # Exact phone match
            ).neq('status', 'Cancelled').order('booking_date', desc=True).order('booking_time', desc=True).execute()

        print(f"DEBUG: Patient dashboard booking fetch response: {response}") # DEBUG
        bookings_data = response.data

        if bookings_data:
             # Try to get the actual name from the first booking for display
             actual_patient_name = bookings_data[0].get('patient_name', patient_identifier)
             now = datetime.now()
             for booking in bookings_data:
                 booking['is_deletable'] = False
                 if booking.get('status') == 'Pending':
                      try:
                           date_str = booking.get('booking_date'); time_slot = booking.get('booking_time', ''); start_time_str = None
                           if time_slot and '-' in time_slot:
                               start_time_str = time_slot.split('-')[0].strip()

                           if date_str and start_time_str:
                                appointment_dt = datetime.strptime(f"{date_str} {start_time_str}", '%Y-%m-%d %H:%M')
                                # Allow deletion only if appointment is in the future
                                if appointment_dt > now:
                                    booking['is_deletable'] = True
                      except (ValueError, IndexError, TypeError, KeyError) as e:
                           print(f"Warn: Parse error calculating deletable status for booking ID {booking.get('id')}: {e}")
                 processed_bookings.append(booking)
        else:
            flash('ℹ️ No active bookings found for this identifier.', 'info')
            print(f"DEBUG: No active bookings found for identifier '{patient_identifier}'")

    except Exception as e:
        print(f"Supabase Error loading Patient Dashboard '{patient_identifier}':")
        traceback.print_exc()
        error_detail = str(e)
        if hasattr(e, 'details'): error_detail = f"{e} - {e.details}"
        if hasattr(e, 'message'): error_detail = e.message
        flash(f'⛔ Database error loading bookings: {error_detail}', 'error'); db_error = True

    return render_template('patient_dashboard.html',
                           bookings=processed_bookings,
                           patient_identifier=patient_identifier, # Keep original identifier for potential future actions
                           patient_display_name=actual_patient_name, # Use potentially fetched name for display
                           error=db_error)


# --- Run Application ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    # Set debug=True for development to see errors and auto-reload
    # Set debug=False for production deployment
    app.run(debug=True, port=port) # Use debug=True for development

# --- END OF MODIFIED FILE app.py ---
