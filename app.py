# --- START OF FILE app.py ---

from flask import (
    Flask, render_template, json, request, redirect, url_for,
    send_from_directory, flash, jsonify, make_response
)
# REMOVED: import sqlite3 # No longer needed
from flask_login import LoginManager, UserMixin, current_user # Assuming you might use login later
import os
from datetime import datetime, timedelta, date, time # Added time for comparison
import uuid
from collections import defaultdict # Helpful for aggregation
# REMOVED: import json # Supabase client handles JSON serialization/deserialization if column type is JSON/JSONB, but we need it for dumps
import math # For ceiling function for stars
import traceback # Added for detailed error logging

# --- Supabase & Environment Setup ---
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file (must contain SUPABASE_URL, SUPABASE_KEY, FLASK_SECRET_KEY)
load_dotenv()

# Initialize Supabase Client
supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in the .env file")
else:
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Supabase client initialized.")
    except Exception as init_err:
        print(f"FATAL: Failed to initialize Supabase client: {init_err}")
        traceback.print_exc() # Print full traceback for init error
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


# --- Robust Availability Parsing Helper ---
def parse_availability(raw_availability, doctor_id_for_log="Unknown"):
    """Safely parses availability data, expecting dict or JSON string, returns dict."""
    if isinstance(raw_availability, dict):
        # print(f"DEBUG (parse_availability): Dr {doctor_id_for_log} - Availability is already a dict.")
        return raw_availability
    elif isinstance(raw_availability, str):
        try:
            parsed_avail = json.loads(raw_availability)
            if isinstance(parsed_avail, dict):
                 # print(f"WARN (parse_availability): Dr {doctor_id_for_log} - Parsed availability string to dict. Recommend DB column type JSON/JSONB.")
                 return parsed_avail
            else:
                 print(f"ERROR (parse_availability): Dr {doctor_id_for_log} - Parsed availability string is not a dict ({type(parsed_avail)}). Returning empty.")
                 return {}
        except json.JSONDecodeError:
            print(f"ERROR (parse_availability): Dr {doctor_id_for_log} - Failed to parse availability JSON string: '{raw_availability[:100]}...'. Returning empty.")
            return {}
    else:
         # print(f"WARN (parse_availability): Dr {doctor_id_for_log} - Availability is not dict or string (type: {type(raw_availability)}). Returning empty.")
         return {}


# --- Load doctors data FROM SUPABASE (includes ratings calculation) ---
def load_doctors_from_db():
    """Fetches doctors from Supabase, parses availability, and calculates average rating."""
    print("Loading doctors data from Supabase...")
    doctors_list = []
    try:
        response_docs = supabase.table('doctors').select('*').order('name', desc=False).execute()

        if not response_docs.data:
            print("Warn: No doctors found in Supabase 'doctors' table.")
            return []

        doctors_list = response_docs.data

        # Initialize ratings/counts and parse availability
        for doc in doctors_list:
            doc_id = doc.get('id', 'Unknown')
            doc['availability'] = parse_availability(doc.get('availability'), doc_id) # Use helper
            doc['average_rating'] = 0.0
            doc['review_count'] = 0

        # Fetch ALL approved reviews to calculate ratings efficiently
        response_reviews = supabase.table('reviews').select('doctor_id, rating').eq('is_approved', 1).execute()

        if response_reviews.data:
             ratings_agg = defaultdict(lambda: {'total': 0, 'count': 0})
             for review in response_reviews.data:
                  if review.get('rating') is not None and review.get('doctor_id') is not None: # Ensure doctor_id exists
                    try:
                        rating_val = float(review['rating'])
                        if 1 <= rating_val <= 5:
                           ratings_agg[review['doctor_id']]['total'] += rating_val
                           ratings_agg[review['doctor_id']]['count'] += 1
                    except (ValueError, TypeError):
                        print(f"Warn: Non-numeric rating '{review['rating']}' for doctor {review['doctor_id']} ignored.")

             # Apply aggregated ratings
             for doc in doctors_list:
                doc_id = doc.get('id')
                if doc_id and doc_id in ratings_agg:
                    agg_data = ratings_agg[doc_id]
                    doc['review_count'] = agg_data['count']
                    if agg_data['count'] > 0:
                         doc['average_rating'] = round(agg_data['total'] / agg_data['count'], 1)
                # No need for else, already initialized to 0

        print(f"Loaded {len(doctors_list)} doctors from Supabase with rating info.")
        return doctors_list

    except Exception as e:
        print(f"CRITICAL: Supabase error loading doctors data:")
        traceback.print_exc()
        flash(f'Error loading doctor data from Supabase: {getattr(e, "message", str(e))}', 'error')
        return []

# --- Function to get current doctors_data (replace global variable access) ---
def get_current_doctors_data():
    """ Central function to retrieve doctor data, potentially with caching later """
    return load_doctors_from_db()


# --- Jinja Helper Function for Stars (Unchanged) ---
@app.context_processor
def utility_processor():
    def get_stars(rating):
        if rating is None: return ['far fa-star'] * 5
        try: rating_f = float(rating)
        except (ValueError, TypeError): return ['far fa-star'] * 5
        if rating_f < 0: return ['far fa-star'] * 5
        rating_f = max(0, min(5, rating_f))
        full = math.floor(rating_f); half = 1 if (rating_f - full) >= 0.5 else 0; empty = 5 - full - half
        stars = ['fas fa-star'] * full + ['fas fa-star-half-alt'] * half + ['far fa-star'] * empty
        while len(stars) < 5: stars.append('far fa-star')
        return stars[:5]
    return dict(get_stars=get_stars)

# --- Routes ---
@app.route('/')
def home():
    print("\n--- Loading '/' Home Route ---")
    doctors_data = get_current_doctors_data() # Fetch current data
    stats = { 'doctor_count': len(doctors_data), 'specialty_count': 0, 'total_bookings': 0, 'total_active_bookings': 0, 'review_count': 0 }
    specialties = []; governorates = []; facility_types = []; plcs = []; site_reviews = []

    if doctors_data:
        try:
            unique_specs = sorted(list({d.get('specialization') for d in doctors_data if d.get('specialization')}))
            unique_govs = sorted(list({d.get('governorate') for d in doctors_data if d.get('governorate')}))
            unique_fac_types = sorted(list({d.get('facility_type') for d in doctors_data if d.get('facility_type')}))
            unique_plcs = sorted(list({d.get('plc') for d in doctors_data if d.get('plc')}))
            stats['specialty_count'] = len(unique_specs)
            specialties = unique_specs; governorates = unique_govs; facility_types = unique_fac_types; plcs = unique_plcs
        except Exception as e: print(f"Warn: Error processing doctors_data for filters: {e}")

    # --- Fetch Counts & Site Reviews from Supabase ---
    try:
        response_active = supabase.table('bookings').select('id', count='exact').neq('status', 'Cancelled').execute()
        stats['total_active_bookings'] = response_active.count if hasattr(response_active, 'count') else 0

        response_all = supabase.table('bookings').select('id', count='exact').execute()
        stats['total_bookings'] = response_all.count if hasattr(response_all, 'count') else 0

        # Fetch APPROVED site reviews
        response_site_reviews = supabase.table('site_reviews').select(
            'reviewer_name, rating, comment, created_at' # Ensure these columns exist
            ).eq('is_approved', 1).order('created_at', desc=True).limit(3).execute()

        if response_site_reviews.data:
             site_reviews = response_site_reviews.data
             # Get total count of approved site reviews for stats
             count_response = supabase.table('site_reviews').select('id', count='exact').eq('is_approved', 1).execute()
             stats['review_count'] = count_response.count if hasattr(count_response, 'count') else 0
             print(f"DEBUG: Fetched {len(site_reviews)} recent site reviews (Total approved: {stats['review_count']}).")
        else:
             print("DEBUG: No approved site reviews found.")
             if hasattr(response_site_reviews, 'error') and response_site_reviews.error:
                   print(f"DEBUG: Site reviews fetch error detail: {response_site_reviews.error}")
                   flash('Error fetching site reviews.', 'error')

    except Exception as e:
        print(f"ERROR: Exception while fetching stats/site reviews for home:")
        traceback.print_exc()
        flash('Could not load current statistics or site reviews.', 'warning')

    return render_template(
        'index.html',
        doctors=doctors_data,
        stats=stats,
        specialties=specialties, governorates=governorates, facility_types=facility_types, plcs=plcs,
        site_reviews=site_reviews
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
        insert_payload = {
            'reviewer_name': reviewer_name,
            'rating': rating,
            'comment': comment,
            'is_approved': 1 # Default to approved
        }
        response = supabase.table('site_reviews').insert(insert_payload).execute()

        if response.data:
             print(f"Site review added by {reviewer_name} (Supabase).")
             flash('✅ Thank you for your feedback!', 'success')
        else:
            error_message = "Could not save review due to an unexpected issue."
            if hasattr(response, 'error') and response.error:
                error_message = f"Could not save review: {response.error.get('message', 'Unknown DB error')}"
                print(f"ERROR: Supabase site review insert failed: {response.error}")
            else:
                 print(f"Warn: Supabase site review insert for {reviewer_name} returned no data or unexpected structure. Response: {response}")
            flash(f'⛔ {error_message}', 'error')

    except Exception as e:
        print(f"Error submitting site review to Supabase:")
        traceback.print_exc()
        error_detail = getattr(e, 'message', str(e))
        flash(f'⛔ Database error submitting your feedback: {error_detail}', 'error')

    return redirect(url_for('home') + '#site-reviews-section')


# --- DOCTOR Review Submission Route (REVISED with 2-query workaround) ---
@app.route('/submit-review', methods=['POST'])
def submit_review():
    print("\n--- Received POST to /submit-review ---")
    doctor_id_str = request.form.get('doctor_id')
    reviewer_name = request.form.get('reviewer_name', '').strip()
    reviewer_phone = request.form.get('reviewer_phone', '').strip()
    rating_str = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    print(f"DEBUG: Form Data - doctor_id='{doctor_id_str}', name='{reviewer_name}', phone='{reviewer_phone}', rating='{rating_str}'")

    # --- Basic Validation (same as before) ---
    errors = []; doctor_id = None; rating = None
    try: doctor_id = int(doctor_id_str)
    except (ValueError, TypeError): errors.append('Invalid Doctor ID.')
    if not reviewer_name: errors.append('Your name is required.')
    if not reviewer_phone: errors.append('Your phone number is required.')
    if not reviewer_phone.isdigit() or not (9 <= len(reviewer_phone) <= 15): errors.append('Valid phone number (9-15 digits) required.')
    try: rating = int(rating_str); assert 1 <= rating <= 5
    except (ValueError, TypeError, AssertionError): errors.append('Valid rating (1-5 stars) required.')

    if errors:
        print(f"DEBUG: Review Validation Errors: {errors}")
        for error in errors: flash(f'⛔ {error}', 'error')
        redirect_url = url_for('booking_page', doctor_id=doctor_id) if doctor_id else url_for('home')
        return redirect(request.referrer or redirect_url)
    # --- End Validation ---

    try:
        print(f"DEBUG: Attempting review checks for Dr {doctor_id}, Reviewer {reviewer_name}/{reviewer_phone}")

        # *** CHECK 1: Already reviewed? (Using TWO queries) ***
        print("DEBUG: Check 1 - Existing review?")
        review_exists = False
        try:
            # Query 1a: Check by name
            res_name = supabase.table('reviews').select('id', count='exact') \
                .eq('doctor_id', doctor_id) \
                .eq('reviewer_name', reviewer_name) \
                .limit(1).execute()
            if hasattr(res_name, 'count') and res_name.count > 0: review_exists = True

            # Query 1b: Check by phone IF not found by name
            if not review_exists:
                 res_phone = supabase.table('reviews').select('id', count='exact') \
                     .eq('doctor_id', doctor_id) \
                     .eq('reviewer_phone', reviewer_phone) \
                     .limit(1).execute()
                 if hasattr(res_phone, 'count') and res_phone.count > 0: review_exists = True

            print(f"DEBUG: Check 1 Response (Name Check: {res_name.count if hasattr(res_name, 'count') else 'ERR'}, Phone Check: {res_phone.count if 'res_phone' in locals() and hasattr(res_phone, 'count') else 'N/A'}) - Exists: {review_exists}")

        except Exception as check1_err:
            print(f"ERROR: Exception during DB Check 1 (existing review): {check1_err}"); traceback.print_exc()
            flash(f'⛔ Error checking existing reviews: {getattr(check1_err, "message", str(check1_err))}.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        if review_exists:
             flash('⛔ You have already reviewed this doctor using this name or phone number.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- END CHECK 1 ---

        # *** CHECK 2: Latest booking (Using TWO queries) ***
        print("DEBUG: Check 2 - Finding latest relevant booking...")
        latest_booking = None
        try:
            # Query 2a: Find latest by name
            bk_name_res = supabase.table('bookings') \
                .select('booking_date, booking_time') \
                .eq('doctor_id', doctor_id) \
                .eq('patient_name', reviewer_name) \
                .neq('status', 'Cancelled') \
                .order('booking_date', desc=True).order('booking_time', desc=True) \
                .limit(1).execute()

            # Query 2b: Find latest by phone
            bk_phone_res = supabase.table('bookings') \
                 .select('booking_date, booking_time') \
                 .eq('doctor_id', doctor_id) \
                 .eq('patient_phone', reviewer_phone) \
                 .neq('status', 'Cancelled') \
                 .order('booking_date', desc=True).order('booking_time', desc=True) \
                 .limit(1).execute()

            booking_by_name = bk_name_res.data[0] if bk_name_res.data else None
            booking_by_phone = bk_phone_res.data[0] if bk_phone_res.data else None
            print(f"DEBUG: Latest booking by Name: {booking_by_name}")
            print(f"DEBUG: Latest booking by Phone: {booking_by_phone}")

            # Determine the actual latest booking between the two matches (if any)
            if booking_by_name and booking_by_phone:
                 # Compare dates and times to find the truly latest one
                 name_dt_str = f"{booking_by_name.get('booking_date')} {booking_by_name.get('booking_time', '').split('-')[0].strip()}"
                 phone_dt_str = f"{booking_by_phone.get('booking_date')} {booking_by_phone.get('booking_time', '').split('-')[0].strip()}"
                 try:
                    name_dt = datetime.strptime(name_dt_str, '%Y-%m-%d %H:%M')
                    phone_dt = datetime.strptime(phone_dt_str, '%Y-%m-%d %H:%M')
                    latest_booking = booking_by_name if name_dt >= phone_dt else booking_by_phone
                 except ValueError: # Handle parsing error if time format is weird
                    latest_booking = booking_by_name # Default to name booking if comparison fails
            elif booking_by_name:
                 latest_booking = booking_by_name
            elif booking_by_phone:
                 latest_booking = booking_by_phone

        except Exception as check2_err:
             print(f"ERROR: Exception during DB Check 2 (latest booking): {check2_err}"); traceback.print_exc()
             flash(f'⛔ Error finding your booking: {getattr(check2_err, "message", str(check2_err))}.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))

        if not latest_booking:
             flash('⛔ No non-cancelled booking found matching your name/phone for this doctor. Book first to review.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        print(f"DEBUG: Using latest booking: {latest_booking}")
        # --- END CHECK 2 ---

        # *** CHECK 3: Appointment time passed? (Same as before) ***
        print("DEBUG: Check 3 - Checking appointment time...")
        try:
            booking_date_str = latest_booking.get('booking_date')
            booking_time_slot = latest_booking.get('booking_time')
            if not booking_date_str or not booking_time_slot or '-' not in booking_time_slot: raise ValueError("Invalid format")
            booking_start_time_str = booking_time_slot.split('-')[0].strip()
            appointment_start_dt = datetime.strptime(f"{booking_date_str} {booking_start_time_str}", '%Y-%m-%d %H:%M')
            now_dt = datetime.now()
            print(f"DEBUG: Comparing Now ({now_dt}) vs Appointment Start ({appointment_start_dt})")
            if now_dt < appointment_start_dt:
                time_fmt = appointment_start_dt.strftime('%I:%M %p on %b %d, %Y')
                flash(f'⛔ Cannot submit review until after your appointment starts ({time_fmt}).', 'error')
                return redirect(url_for('booking_page', doctor_id=doctor_id))
            print("DEBUG: Appointment time passed.")
        except (ValueError, IndexError, TypeError, KeyError) as e:
             print(f"ERROR: Parsing latest booking time failed: {e}"); traceback.print_exc()
             flash('⛔ Could not verify appointment time. Contact support.', 'error')
             return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- END CHECK 3 ---

        # --- If all checks passed, Insert the DOCTOR review (Same as before) ---
        print("DEBUG: All review checks passed. Attempting insert...")
        insert_data = {
            'doctor_id': doctor_id, 'reviewer_name': reviewer_name, 'reviewer_phone': reviewer_phone,
            'rating': rating, 'comment': comment, 'is_approved': 1 # Or 0 for moderation
        }
        print(f"DEBUG: Insert Review Data Payload: {insert_data}")
        insert_response = supabase.table('reviews').insert(insert_data).execute()
        print(f"DEBUG: Insert Review Response: {insert_response}")

        if insert_response.data:
             flash('✅ Thank you! Your review has been submitted.', 'success')
             print(f"Doctor review added for Dr {doctor_id} by {reviewer_name}.")
        else: # Handle insert failure
             error_message = "Failed to submit review (database issue)."
             # Extract specific error if possible (similar to confirm_booking error handling)
             error_info = getattr(insert_response, 'error', None)
             if error_info:
                error_code = getattr(error_info, 'code', None)
                error_msg = getattr(error_info, 'message', 'Unknown DB Error')
                error_details = getattr(error_info, 'details', '')
                print(f"ERROR: Supabase review insert failed: Code={error_code} Msg={error_msg} Details={error_details}")
                # Specific constraint checks if needed (e.g., check violation for phone/name uniqueness if enforced)
                if error_code == '23505': error_message = f"Review submission failed: Possible duplicate entry detected."
                else: error_message = f"Review submission failed: {error_msg}"
             else: print(f"WARN: Supabase review insert no data. Response: {insert_response}")
             flash(f'⛔ {error_message}', 'error')

    # Outer catch block
    except Exception as e:
        print(f"ERROR submitting doctor review (Outer Catch) (Dr {doctor_id}):")
        traceback.print_exc()
        flash(f'⛔ Server error submitting review: {getattr(e, "message", str(e))}.', 'error')

    print("--- /submit-review finished ---")
    return redirect(url_for('booking_page', doctor_id=doctor_id))
# --- END OF REVISED submit_review ---

# --- /booking route (Should be OK, no direct OR calls) ---
@app.route('/booking/<int:doctor_id>')
def booking_page(doctor_id):
    # (Keep the code from the previous version, it seemed okay)
    print(f"\n--- Loading Booking Page for Doctor ID: {doctor_id} ---")
    doctor = None
    reviews = []
    doctor_availability_data = {} # Default to empty dict

    # --- Fetch Doctor Details directly from Supabase ---
    try:
        print("DEBUG: Fetching doctor details...")
        doc_response = supabase.table('doctors').select('*').eq('id', doctor_id).maybe_single().execute()
        doctor = doc_response.data

        if doctor:
             print(f"DEBUG: Doctor {doctor_id} found. Processing details...")
             # --- Availability Handling (Use Helper) ---
             doctor_availability_data = parse_availability(doctor.get('availability'), doctor_id)
             doctor['availability'] = doctor_availability_data # Ensure doctor dict has the *parsed* data
             print(f"DEBUG: Parsed availability for Dr {doctor_id}: {doctor_availability_data}")

             # --- Rating Calculation ---
             print("DEBUG: Calculating doctor rating...")
             individual_ratings_response = supabase.table('reviews').select('rating').eq('doctor_id', doctor_id).eq('is_approved', 1).execute()
             if individual_ratings_response.data:
                 valid_ratings = [r['rating'] for r in individual_ratings_response.data if r.get('rating') is not None and isinstance(r.get('rating'), (int, float)) and 1 <= r.get('rating') <= 5]
                 count = len(valid_ratings)
                 total_rating = sum(valid_ratings)
                 doctor['review_count'] = count
                 doctor['average_rating'] = round(total_rating / count, 1) if count > 0 else 0.0
             else:
                 doctor['review_count'] = 0
                 doctor['average_rating'] = 0.0
             print(f"DEBUG: Rating calculated - Avg: {doctor.get('average_rating', 'N/A')}, Count: {doctor.get('review_count', 'N/A')}")

             # Fetch recent approved reviews for display
             print(f"DEBUG: Fetching recent reviews for doctor {doctor_id}...")
             reviews_response = supabase.table('reviews').select(
                 'reviewer_name, rating, comment, created_at'
                 ).eq('doctor_id', doctor_id).eq('is_approved', 1).order(
                     'created_at', desc=True
                 ).limit(10).execute()
             reviews = reviews_response.data or []
             print(f"DEBUG: Fetched {len(reviews)} reviews for display.")

        else:
            print(f"ERROR: Doctor with ID {doctor_id} not found.")
            flash(f'⛔ Doctor with ID {doctor_id} not found.', 'error')
            return redirect(url_for('home'))

    except Exception as e:
        print(f"ERROR fetching booking page data for Dr {doctor_id}:"); traceback.print_exc()
        flash(f'⛔ Error loading doctor details: {getattr(e, "message", str(e))}', 'error')
        return redirect(url_for('home'))

    doctor_availability_schedule_for_js = json.dumps(doctor_availability_data)
    print(f"DEBUG: Passing availability to booking.html (type: {type(doctor_availability_data)})")

    response = make_response(render_template(
        'booking.html', doctor=doctor, doctor_id=doctor_id,
        doctor_availability=doctor_availability_data, reviews=reviews
    ))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'; response.headers['Expires'] = '0'
    print("--- Finished loading Booking Page data ---")
    return response

# --- Routes: center_details (Should be OK, no direct OR calls) ---
@app.route('/center/<path:plc_name>')
def center_details(plc_name):
    # (Keep the code from the previous version)
    if not plc_name: flash('No clinic name provided.', 'error'); return redirect(url_for('home'))
    print(f"--- Loading Center Details for: {plc_name} ---")
    plc_doctors = []
    plc_info = {}
    try:
        response = supabase.table('doctors').select('*').eq('plc', plc_name).execute()
        plc_doctors = response.data
        if not plc_doctors:
             flash(f'Details not found for clinic/center "{plc_name}".', 'info')
             return redirect(url_for('home'))
        # Calculate ratings
        for doc in plc_doctors:
             doc_id = doc.get('id')
             if not doc_id: doc['review_count'] = 0; doc['average_rating'] = 0.0; continue
             rating_res = supabase.table('reviews').select('rating', count='exact').eq('doctor_id', doc_id).eq('is_approved', 1).execute()
             doc['review_count'] = rating_res.count if hasattr(rating_res, 'count') else 0
             if doc['review_count'] > 0:
                  avg_res = supabase.table('reviews').select('rating').eq('doctor_id', doc_id).eq('is_approved', 1).execute()
                  if avg_res.data:
                      valid_ratings = [r['rating'] for r in avg_res.data if r.get('rating') is not None and isinstance(r.get('rating'), (int, float)) and 1 <= r.get('rating') <= 5]
                      doc['average_rating'] = round(sum(valid_ratings) / len(valid_ratings), 1) if valid_ratings else 0.0
                  else: doc['average_rating'] = 0.0
             else: doc['average_rating'] = 0.0
        # Gather PLC info
        first_doc = plc_doctors[0]
        unique_locations = sorted(list({ (d.get('governorate', 'N/A'), d.get('province', 'N/A')) for d in plc_doctors if d.get('governorate') or d.get('province')}))
        plc_info = { 'name': plc_name, 'facility_type': first_doc.get('facility_type', 'Clinic/Center'), 'locations': unique_locations }
        plc_slug = plc_name.lower().replace(' ', '_').replace('&', 'and').replace('.', '').replace("'", '')
        plc_info['photo_path_jpg'] = f'/static/plc_photos/{plc_slug}.jpg'
    except Exception as e:
        print(f"ERROR: Supabase error fetching center '{plc_name}':"); traceback.print_exc()
        flash('⛔ Error loading center details.', 'error')
        return redirect(url_for('home'))
    return render_template('center_details.html', plc=plc_info, doctors=plc_doctors)

# --- Helper Function: Get Doctor Availability --- (Should be OK)
def get_doctor_availability_from_supabase(doctor_id):
    # (Keep the code from the previous version)
     print(f"DEBUG (Helper): Fetching availability for Dr {doctor_id}")
     try:
          response = supabase.table('doctors').select('availability').eq('id', doctor_id).maybe_single().execute()
          if response.data and response.data.get('availability') is not None:
               availability_data = parse_availability(response.data['availability'], doctor_id)
               print(f"DEBUG (Helper): Dr {doctor_id} - Availability found and parsed.")
               return availability_data
          else:
               print(f"WARN (Helper): Dr {doctor_id} - No availability data found.")
               return {}
     except Exception as e:
          print(f"ERROR: Supabase helper error for Dr {doctor_id}:"); traceback.print_exc()
          return {}

# --- API Routes (get_nearest_available, get_available_slots) (Should be OK, no OR calls) ---
@app.route('/get-nearest-available/<int:doctor_id>')
def get_nearest_available(doctor_id):
    # (Keep the code from the previous version)
    print(f"DEBUG: API call /get-nearest-available/ for Dr {doctor_id}")
    doctor_availability = get_doctor_availability_from_supabase(doctor_id)
    if not doctor_availability: return jsonify({'success': False, 'message': 'Doctor schedule is currently unavailable.'}), 404
    today_date = date.today(); now_time = datetime.now().time()
    print(f"DEBUG: Current date: {today_date}, time: {now_time}")
    try:
        for i in range(90): # Look ahead
            current_check_date = today_date + timedelta(days=i)
            date_str = current_check_date.strftime('%Y-%m-%d')
            day_name = current_check_date.strftime('%A')
            general_slots_raw = doctor_availability.get(day_name, [])
            if not isinstance(general_slots_raw, list): continue
            general_slots = sorted([s for s in general_slots_raw if isinstance(s, str) and '-' in s and ':' in s and s.strip().lower() != "unavailable"])
            if not general_slots: continue
            response_booked = supabase.table('bookings').select('booking_time').eq('doctor_id', doctor_id).eq('booking_date', date_str).neq('status', 'Cancelled').execute()
            booked_times = {row['booking_time'] for row in response_booked.data} if response_booked.data else set()
            for slot in general_slots:
                if slot not in booked_times:
                    slot_start_time = None
                    try: slot_start_str = slot.split('-')[0].strip(); slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                    except (ValueError, IndexError) as time_parse_err: print(f"ERROR: Parse near slot '{slot}': {time_parse_err}. Skipping."); continue
                    if current_check_date == today_date: # Today
                        if slot_start_time > now_time: print(f"SUCCESS: Found nearest (Today): {date_str} {slot}"); return jsonify({'success': True, 'date': date_str, 'time': slot})
                    else: # Future date
                        print(f"SUCCESS: Found nearest (Future): {date_str} {slot}"); return jsonify({'success': True, 'date': date_str, 'time': slot})
        print(f"INFO: Loop finished. No slots found near for Dr {doctor_id}.")
        return jsonify({'success': False, 'message': 'No available slots found soon.'}), 404
    except Exception as e:
        print(f"ERROR in get_nearest_available logic for Dr {doctor_id}:"); traceback.print_exc()
        return jsonify({'success': False, 'message': f'Internal server error searching.'}), 500

@app.route('/get-available-slots/<int:doctor_id>/<string:date_str>')
def get_available_slots(doctor_id, date_str):
    # (Keep the code from the previous version)
    print(f"DEBUG: API call /get-available-slots/ Dr {doctor_id} on {date_str}")
    try: booking_date = datetime.strptime(date_str, '%Y-%m-%d').date(); day_name = booking_date.strftime('%A')
    except ValueError: print(f"ERROR: Invalid date format: {date_str}"); return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
    doctor_availability = get_doctor_availability_from_supabase(doctor_id)
    if not doctor_availability: print(f"WARN: No schedule found Dr {doctor_id} date {date_str}"); return jsonify([])
    general_slots_raw = doctor_availability.get(day_name, [])
    if not isinstance(general_slots_raw, list): print(f"WARN: Schedule not list {day_name}"); return jsonify([])
    general_slots = sorted([ s for s in general_slots_raw if isinstance(s, str) and '-' in s and ':' in s and s.strip().lower() != "unavailable"])
    if not general_slots: print(f"DEBUG: No general slots {day_name}"); return jsonify([])
    try:
        response_booked = supabase.table('bookings').select('booking_time').eq('doctor_id', doctor_id).eq('booking_date', date_str).neq('status', 'Cancelled').execute()
        booked_times = {row['booking_time'] for row in response_booked.data} if response_booked.data else set()
        available_slots = [slot for slot in general_slots if slot not in booked_times]
        if booking_date == date.today(): # Filter past today
             now_time = datetime.now().time()
             future_slots = []
             for slot in available_slots:
                try: slot_start_str = slot.split('-')[0].strip(); slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                except (ValueError, IndexError) as e: print(f"ERROR: Parse slot '{slot}' today filter: {e}. Skipping."); continue
                if slot_start_time > now_time: future_slots.append(slot)
             available_slots = future_slots
        print(f"DEBUG: Returning {len(available_slots)} slots for {date_str}: {available_slots}")
        return jsonify(available_slots)
    except Exception as e:
        print(f"ERROR: Supabase fetch booked times Dr {doctor_id} on {date_str}:"); traceback.print_exc()
        return jsonify({'error': 'Database error fetching times.'}), 500


# --- confirm_booking route (Already Fixed with two-query approach) ---
@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    # (Keep the CORRECTED version from the previous message using the two-query check for CHECK 2)
    print("\n--- Received POST to /confirm-booking ---")
    # --- Get Data ---
    doctor_id_str = request.form.get('doctor_id')
    patient_name = request.form.get('patient_name', '').strip()
    patient_phone = request.form.get('patient_phone', '').strip()
    booking_date = request.form.get('booking_date') # Should be YYYY-MM-DD
    booking_time = request.form.get('booking_time') # Should be HH:MM-HH:MM
    notes = request.form.get('notes', '').strip()
    fingerprint = request.form.get('fingerprint')
    cookie_id = request.cookies.get('device_id')
    ip_address = request.remote_addr
    print(f"DEBUG: Form Data - DrID: {doctor_id_str}, Name: {patient_name}, Phone: {patient_phone}, Date: {booking_date}, Time: {booking_time}, FP: {fingerprint}, IP: {ip_address}")
    # --- Basic Validation ---
    errors = []; doctor_id = None; booking_date_obj = None; slot_start_time = None
    if not doctor_id_str or not doctor_id_str.isdigit(): errors.append('Invalid Doctor ID.')
    else: doctor_id = int(doctor_id_str)
    if not patient_name: errors.append('Patient name is required.')
    if not patient_phone: errors.append('Patient phone is required.')
    if not patient_phone.isdigit() or not (9 <= len(patient_phone) <= 15): errors.append('Valid phone number (9-15 digits) required.')
    if not booking_date: errors.append('Booking date is required.')
    if not booking_time: errors.append('Booking time slot is required.')
    if not errors:
        try:
            booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
            if booking_date_obj < date.today(): errors.append('Cannot book an appointment in the past date.')
            if booking_time and '-' in booking_time and ':' in booking_time:
                 slot_start_str = booking_time.split('-')[0].strip()
                 slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                 if booking_date_obj == date.today() and slot_start_time <= datetime.now().time(): errors.append('Cannot book a time slot that has already passed today.')
            else: errors.append('Invalid booking time format selected.')
        except ValueError: errors.append('Invalid date or time format.')
    if errors:
        print(f"DEBUG: Validation Errors on Confirm: {errors}")
        for error in errors: flash(f'⛔ {error}', 'error')
        redir_url = url_for('booking_page', doctor_id=doctor_id) if doctor_id else url_for('home')
        return redirect(request.referrer or redir_url)
    # --- CRITICAL Validation: Refetch Schedule ---
    fetched_doctor_name = None; is_slot_valid = False
    try:
        print(f"DEBUG: /confirm-booking - Fetching current schedule Dr {doctor_id}")
        doc_response = supabase.table('doctors').select('availability, name').eq('id', doctor_id).maybe_single().execute()
        if not doc_response.data: flash(f'⛔ Doctor {doctor_id} not found.', 'error'); return redirect(url_for('home'))
        fetched_doctor_name = doc_response.data.get('name', 'Doctor')
        current_doctor_schedule = parse_availability(doc_response.data.get('availability'), doctor_id)
        print(f"DEBUG: /confirm-booking - Current schedule: {current_doctor_schedule}")
        selected_day_name = booking_date_obj.strftime('%A')
        day_schedule_raw = current_doctor_schedule.get(selected_day_name, [])
        if not isinstance(day_schedule_raw, list):
            print(f"ERROR: Schedule format invalid for {selected_day_name}.")
            flash('⛔ Error validating schedule format.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
        valid_general_slots = { s for s in day_schedule_raw if isinstance(s, str) and '-' in s and ':' in s and s.strip().lower() != 'unavailable'}
        print(f"DEBUG: Validating '{booking_time}' against CURRENT {selected_day_name} slots: {valid_general_slots}")
        if booking_time in valid_general_slots: is_slot_valid = True; print("DEBUG: Slot Validation PASSED.")
        else: print(f"ERROR: Slot '{booking_time}' NOT valid now."); flash('⛔ Slot no longer available/valid.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
    except Exception as e: print(f"ERROR: Exception validating availability: {e}"); traceback.print_exc(); flash(f'⛔ Server error validating slot: {getattr(e, "message", str(e))}.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
    if not is_slot_valid: print("ERROR: Slot validation check failed."); flash('⛔ Slot validation failed.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
    # --- DB Interaction ---
    try:
        # ** CHECK 1: Slot booked? **
        print(f"DEBUG: DB Check 1 - Slot booked? {booking_time} {booking_date} Dr {doctor_id}")
        check_slot_res = supabase.table('bookings').select('id', count='exact').eq('doctor_id', doctor_id).eq('booking_date', booking_date).eq('booking_time', booking_time).neq('status', 'Cancelled').execute()
        print(f"DEBUG: DB Check 1 Resp: {check_slot_res}")
        if hasattr(check_slot_res, 'count') and check_slot_res.count > 0: flash('⛔ Slot just booked.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
        # ** CHECK 2: Patient conflict? (TWO queries) **
        print(f"DEBUG: DB Check 2 - Conflict for {patient_name}/{patient_phone} on {booking_date}?")
        name_conflict = False; phone_conflict = False; existing_time = None
        try:
            check_name_res = supabase.table('bookings').select('booking_time', count='exact').eq('doctor_id', doctor_id).eq('booking_date', booking_date).neq('status', 'Cancelled').eq('patient_name', patient_name).execute()
            print(f"DEBUG: Check 2a (Name) Resp: {check_name_res}")
            if hasattr(check_name_res, 'count') and check_name_res.count > 0: name_conflict = True;
            if check_name_res.data: existing_time = check_name_res.data[0].get('booking_time')
            if not name_conflict:
                 check_phone_res = supabase.table('bookings').select('booking_time', count='exact').eq('doctor_id', doctor_id).eq('booking_date', booking_date).neq('status', 'Cancelled').eq('patient_phone', patient_phone).execute()
                 print(f"DEBUG: Check 2b (Phone) Resp: {check_phone_res}")
                 if hasattr(check_phone_res, 'count') and check_phone_res.count > 0: phone_conflict = True;
                 if check_phone_res.data and not existing_time: existing_time = check_phone_res.data[0].get('booking_time')
            if name_conflict or phone_conflict: existing_time_str = existing_time or "another time"; flash(f'ℹ️ You already have booking with Dr. {fetched_doctor_name} on {booking_date} at {existing_time_str}.', 'info'); return redirect(url_for('booking_page', doctor_id=doctor_id))
            else: print("DEBUG: DB Check 2 PASSED - No conflict.")
        except Exception as check2_err: print(f"ERROR: Exception Check 2: {check2_err}"); traceback.print_exc(); flash(f'⛔ Error checking existing bookings: {getattr(check2_err, "message", str(check2_err))}.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
        # --- Insert Booking ---
        print("DEBUG: All checks passed. Inserting...")
        insert_data = {'doctor_id': doctor_id, 'doctor_name': fetched_doctor_name, 'patient_name': patient_name, 'patient_phone': patient_phone, 'booking_date': booking_date, 'booking_time': booking_time, 'notes': notes, 'status': 'Pending', 'ip_address': ip_address, 'cookie_id': cookie_id, 'fingerprint': fingerprint}
        insert_data_clean = {k: v for k, v in insert_data.items() if v is not None}
        print(f"DEBUG: Insert payload: {insert_data_clean}")
        response_insert = supabase.table('bookings').insert(insert_data_clean).execute()
        print(f"DEBUG: Insert response: {response_insert}")
        # Handle insert response
        if response_insert.data and isinstance(response_insert.data, list) and len(response_insert.data) > 0 and 'id' in response_insert.data[0]:
            booking_id = response_insert.data[0]['id']
            print(f"SUCCESS: Booking confirmed: ID {booking_id}")
            flash('✅ Booking confirmed!', 'success')
            return redirect(url_for('confirmation', booking_id=booking_id, doctor_name=fetched_doctor_name, patient_name=patient_name, booking_date=booking_date, booking_time=booking_time))
        else: # Insert failed
            error_message = "Booking failed (database issue)."
            error_info = getattr(response_insert, 'error', None); error_dict = {};
            if hasattr(error_info, '__dict__'): error_dict = error_info.__dict__
            elif isinstance(error_info, dict): error_dict = error_info
            error_code = error_dict.get('code'); error_msg = error_dict.get('message', 'Unknown DB Error')
            print(f"ERROR: Insert failed: Code={error_code}, Msg={error_msg}, Details={error_dict.get('details')}")
            if error_code == '23505': error_message = "Booking failed: Time slot likely taken."
            elif error_code: error_message = f"Booking failed: {error_msg}"
            flash(f'⛔ {error_message}', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
    # Outer exception
    except Exception as e: print(f"Outer ERROR confirm_booking Dr {doctor_id}:"); traceback.print_exc(); flash(f'⛔ Server error: {getattr(e, "message", str(e))}.', 'error'); return redirect(url_for('booking_page', doctor_id=doctor_id))
# --- END OF /confirm-booking ---

# --- Confirmation route (Should be OK) ---
@app.route('/confirmation')
def confirmation():
    # (Keep the code from the previous version)
    booking_id = request.args.get('booking_id'); doctor_name = request.args.get('doctor_name'); patient_name = request.args.get('patient_name'); booking_date = request.args.get('booking_date'); booking_time = request.args.get('booking_time')
    print(f"--- Loading Confirmation Page ID: {booking_id} ---")
    if not all([booking_id, doctor_name, patient_name, booking_date, booking_time]): print("WARN: Missing conf details."); flash('Invalid confirmation link.', 'warning'); return redirect(url_for('home'))
    return render_template('confirmation.html', booking_id=booking_id, doctor_name=doctor_name, patient_name=patient_name, booking_date=booking_date, booking_time=booking_time)


# --- delete_booking route (Should be OK) ---
@app.route('/delete-booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    # (Keep the code from the previous version)
    print(f"--- Attempting Cancel Booking ID: {booking_id} ---")
    source = request.form.get('source', 'unknown'); patient_identifier = request.form.get('patient_identifier'); doctor_id_str = request.form.get('doctor_id')
    print(f"Source: {source}, Patient ID: {patient_identifier}, Dr ID: {doctor_id_str}")
    redirect_url = url_for('home')
    if source == 'patient_dashboard' and patient_identifier: redirect_url = url_for('patient_dashboard', patient_identifier=patient_identifier)
    elif source == 'doctor_dashboard' and doctor_id_str and doctor_id_str.isdigit(): redirect_url = url_for('doctor_dashboard', doctor_id=int(doctor_id_str))
    elif source == 'confirmation_page': redirect_url = url_for('home')
    try:
        response = supabase.table('bookings').update({'status': 'Cancelled'}).eq('id', booking_id).eq('status', 'Pending').execute()
        print(f"DEBUG: Cancel response ID {booking_id}: {response}")
        if response.data and len(response.data) > 0: flash('✅ Booking cancelled.', 'success'); print(f"Booking {booking_id} status -> Cancelled.")
        else:
            status_response = supabase.table('bookings').select('status').eq('id', booking_id).maybe_single().execute()
            if status_response.data: current_status = status_response.data['status']; flash(f'ℹ️ Cannot cancel booking (Status: {current_status}).', 'info'); print(f"WARN: Cancel failed {booking_id}, status was {current_status}")
            else: flash('⛔ Booking not found.', 'error'); print(f"WARN: Cancel non-existent ID {booking_id}")
    except Exception as e: print(f"ERROR cancelling {booking_id}:"); traceback.print_exc(); flash(f'⛔ DB error cancelling: {getattr(e, "message", str(e))}', 'error')
    print(f"Redirecting after cancel attempt: {redirect_url}"); return redirect(redirect_url)

# --- Doctor Login route (Should be OK, uses ilike not OR) ---
@app.route('/doctor-login', methods=['GET', 'POST'])
def doctor_login():
    # (Keep the code from the previous version)
    if request.method == 'POST':
        doctor_name = request.form.get('doctorName', '').strip(); doctor_id_str = request.form.get('doctorId', '').strip()
        if not doctor_name or not doctor_id_str or not doctor_id_str.isdigit(): flash('⛔ Enter Name & numeric ID.', 'error'); return redirect(url_for('doctor_login'))
        doctor_id = int(doctor_id_str)
        try:
             response = supabase.table('doctors').select('id, name').eq('id', doctor_id).ilike('name', f'%{doctor_name}%').maybe_single().execute()
             doctor = response.data; print(f"DEBUG: Dr login check response ID {doctor_id} Name '{doctor_name}': {response}")
        except Exception as e: print(f"ERROR: Supabase Dr login check {doctor_id}/{doctor_name}:"); traceback.print_exc(); flash(f'⛔ DB error: {getattr(e, "message", str(e))}', 'error'); return redirect(url_for('doctor_login'))
        if doctor: db_doctor_name = doctor.get('name', 'Doctor'); print(f"SUCCESS: Dr login: ID {doctor_id}, Name '{db_doctor_name}'"); flash(f'✅ Welcome Dr. {db_doctor_name}!', 'success'); return redirect(url_for('doctor_dashboard', doctor_id=doctor_id))
        else: print(f"FAIL: Dr login: ID {doctor_id}, Name '{doctor_name}'"); flash('⛔ Invalid Dr Name/ID.', 'error'); return redirect(url_for('doctor_login'))
    return render_template('doctor_login.html')


# --- Doctor Dashboard route (Should be OK, no direct OR calls) ---
@app.route('/doctor-dashboard/<int:doctor_id>')
def doctor_dashboard(doctor_id):
    # (Keep the code from the previous version)
    print(f"--- Loading Dr Dashboard ID: {doctor_id} ---")
    doctor = None; bookings_rows = []; stats = defaultdict(int); appts_per_day = defaultdict(int); unique_patients = set()
    try:
        doc_response = supabase.table('doctors').select('id, name').eq('id', doctor_id).maybe_single().execute()
        doctor = doc_response.data
        if not doctor: print(f"ERROR: Dr ID {doctor_id} not found."); flash("⛔ Doctor not found.", "error"); return redirect(url_for('doctor_login'))
        print(f"DEBUG: Found Dr. {doctor.get('name')}")
        bookings_response = supabase.table('bookings').select('id, patient_name, patient_phone, booking_date, booking_time, notes, status').eq('doctor_id', doctor_id).neq('status', 'Cancelled').order('booking_date', desc=True).order('booking_time', desc=True).execute()
        bookings_rows = bookings_response.data or []; print(f"DEBUG: Fetched {len(bookings_rows)} bookings.")
        # --- Stats Calc ---
        today = date.today(); today_str = today.strftime('%Y-%m-%d'); week_later = today + timedelta(days=7); month_start = today.replace(day=1)
        stats['total_bookings_listed'] = len(bookings_rows)
        for b in bookings_rows:
             status = b.get('status'); p_id = b.get('patient_phone') or b.get('patient_name', '').strip()
             try: dt_str = b.get('booking_date'); booking_date_obj = datetime.strptime(dt_str, '%Y-%m-%d').date() if dt_str else None
             except (ValueError, TypeError): print(f"Warn: Invalid date {dt_str} bk ID {b.get('id')}"); continue
             if not booking_date_obj: continue
             if status == 'Pending':
                 if booking_date_obj >= today: stats['pending_upcoming_count'] += 1
                 if booking_date_obj == today: stats['today_pending_count'] += 1
             elif status == 'Completed': stats['completed_total_count'] += 1
             if booking_date_obj == today: stats['all_today_count'] += 1
             if today <= booking_date_obj < week_later: stats['all_next_7_days_count'] += 1
             appts_per_day[booking_date_obj.strftime('%Y-%m-%d')] += 1
             if booking_date_obj >= month_start and p_id: unique_patients.add(p_id.lower())
        stats['unique_patients_this_month'] = len(unique_patients)
        print(f"DEBUG: Stats: {dict(stats)}")
        # --- End Stats ---
    except Exception as e: print(f"ERROR loading Dr Dashboard {doctor_id}:"); traceback.print_exc(); flash(f'⛔ Error loading data: {getattr(e, "message", str(e))}', 'error'); return render_template('doctor_dashboard.html', doctor=doctor or {'id': doctor_id, 'name':'N/A'}, doctor_id=doctor_id, bookings_by_month={}, stats={'total_bookings_listed': 0}, chart_config_daily={'labels': [], 'data': []})
    # --- Chart Prep ---
    chart_labels=[]; chart_data=[]
    for i in range(7): d = today + timedelta(days=i); d_str = d.strftime('%Y-%m-%d'); chart_labels.append(d.strftime('%a, %b %d')); chart_data.append(appts_per_day.get(d_str, 0))
    chart_config = {'labels': chart_labels, 'data': chart_data}; print(f"DEBUG: Chart: {chart_config}")
    # --- Group Bookings ---
    bookings_by_month = defaultdict(lambda: defaultdict(list))
    for b in bookings_rows:
        try:
            if b.get('booking_date'): booking_date_obj = datetime.strptime(b['booking_date'], '%Y-%m-%d').date(); m_key = booking_date_obj.strftime('%B %Y'); d_key = b['booking_date']; bookings_by_month[m_key][d_key].append(b)
            else: print(f"Warn: Skip grouping bk ID {b.get('id')} missing date.")
        except (ValueError, TypeError, KeyError) as e: print(f"Warn: Grouping error bk id {b.get('id')} date '{b.get('booking_date')}': {e}")
    sorted_months = sorted(bookings_by_month.keys(), key=lambda my: datetime.strptime(my, '%B %Y'), reverse=True)
    final_grouped = { m: dict(sorted(bookings_by_month[m].items(), reverse=True)) for m in sorted_months }
    # --- End Grouping ---
    return render_template('doctor_dashboard.html', doctor=doctor, doctor_id=doctor_id, bookings_by_month=final_grouped, stats=dict(stats), chart_config_daily=chart_config)


# --- Update Notes route (Should be OK) ---
@app.route('/update-all-notes', methods=['POST'])
def update_all_notes():
    # (Keep the code from the previous version)
    print("--- POST /update-all-notes ---")
    if not request.is_json: print("ERROR: Not JSON"); return jsonify({'success': False, 'message': 'Request must be JSON.'}), 400
    data = request.get_json(); updates = data.get('updates', [])
    print(f"DEBUG: Updates data: {updates}")
    if not isinstance(updates, list): print("ERROR: Not list"); return jsonify({'success': False, 'message': "Invalid format: 'updates' list missing."}), 400
    updated = 0; failed_ids = []; messages = []
    for u in updates:
         bid = u.get('bookingId'); notes = u.get('notes', '')
         if isinstance(bid, (int, str)) and str(bid).isdigit() and isinstance(notes, str):
              bid_int = int(bid)
              try:
                   response = supabase.table('bookings').update({'notes': notes.strip()}).eq('id', bid_int).execute()
                   print(f"DEBUG: Update notes response ID {bid_int}: {response}")
                   if response.data and len(response.data) > 0: updated += 1; print(f"SUCCESS: Note update {bid_int}.")
                   else:
                       failed_ids.append(bid_int)
                       check = supabase.table('bookings').select('id', count='exact').eq('id', bid_int).execute()
                       msg = f"Note update failed: Booking {bid_int} not found." if hasattr(check,'count') and check.count==0 else f"Note update failed {bid_int} (no rows)."
                       print(f"WARN: {msg} Resp: {response}"); messages.append(msg)
              except Exception as e: print(f"ERROR updating note {bid_int}:"); traceback.print_exc(); failed_ids.append(bid_int); messages.append(f"Server error note {bid_int}.")
         else: invalid_id = u.get('bookingId', 'Unknown'); print(f"ERROR: Invalid data {invalid_id}"); failed_ids.append(invalid_id); messages.append(f"Invalid data (ID: {invalid_id}).")
    print(f"--- Notes update done. Attempt: {len(updates)}. Success: {updated}. Failed: {len(failed_ids)}. ---")
    final_msg = f"{updated} note(s) saved."; flash_cat = 'info'
    if failed_ids: fid_str = ', '.join(map(str, failed_ids[:5]))+('...' if len(failed_ids)>5 else ''); final_msg += f" Failed {len(failed_ids)} (IDs: {fid_str})."; flash_cat = 'warning'
    if updated > 0 and not failed_ids: flash_cat = 'success'
    flash(final_msg, flash_cat)
    return jsonify({'success': not failed_ids, 'message': final_msg, 'updated_count': updated, 'failed_count': len(failed_ids)})

# --- Mark Complete route (Should be OK) ---
@app.route('/mark-complete/<int:booking_id>', methods=['POST'])
def mark_complete(booking_id):
    # (Keep the code from the previous version)
    print(f"--- POST /mark-complete ID: {booking_id} ---")
    try:
        response = supabase.table('bookings').update({'status': 'Completed'}).eq('id', booking_id).eq('status', 'Pending').execute()
        print(f"DEBUG: Mark complete resp ID {booking_id}: {response}")
        if response.data and len(response.data) > 0: print(f"SUCCESS: Mark complete {booking_id}."); return jsonify({'success': True, 'message': 'Marked completed.'})
        else:
             status_resp = supabase.table('bookings').select('status').eq('id', booking_id).maybe_single().execute()
             if status_resp.data: status = status_resp.data['status']; msg = f'Cannot mark complete. Status: "{status}".'; print(f"FAIL: Mark complete {booking_id} status '{status}'"); return jsonify({'success': False, 'message': msg}), 409
             else: print(f"FAIL: Mark complete {booking_id}: Not found."); return jsonify({'success': False, 'message': 'Booking not found.'}), 404
    except Exception as e: print(f"ERROR mark complete {booking_id}:"); traceback.print_exc(); error = getattr(e, 'message', str(e)); return jsonify({'success': False, 'message': f'DB error: {error}'}), 500


# --- Patient Login Route (REVISED with 2-query workaround) ---
@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        patient_identifier = request.form.get('patientIdentifier', '').strip()
        print(f"--- Attempting Patient Login ID: '{patient_identifier}' ---")
        if not patient_identifier:
            flash('⛔ Please enter your Name or Phone Number.', 'error')
            return redirect(url_for('patient_login'))

        booking_exists = False
        try:
            print(f"DEBUG: Patient login check for '{patient_identifier}'")
            # Use case-insensitive partial match for name, exact for phone

            # Query 1: Check by name (ilike)
            name_res = supabase.table('bookings').select('id', count='exact') \
                .ilike('patient_name', f'%{patient_identifier}%') \
                .neq('status', 'Cancelled') \
                .limit(1).execute()
            if hasattr(name_res, 'count') and name_res.count > 0:
                 booking_exists = True

            # Query 2: Check by phone IF not found by name
            phone_res = None # Define before use
            if not booking_exists:
                phone_res = supabase.table('bookings').select('id', count='exact') \
                     .eq('patient_phone', patient_identifier) \
                     .neq('status', 'Cancelled') \
                     .limit(1).execute()
                if hasattr(phone_res, 'count') and phone_res.count > 0:
                     booking_exists = True

            print(f"DEBUG: Patient Login Check - Name Count: {name_res.count if hasattr(name_res, 'count') else 'ERR'}, Phone Count: {phone_res.count if phone_res and hasattr(phone_res, 'count') else 'N/A'} -> Exists: {booking_exists}")

        except Exception as e:
            print(f"ERROR: Supabase patient login check '{patient_identifier}':"); traceback.print_exc()
            flash(f'⛔ Database error login: {getattr(e, "message", str(e))}.', 'error')
            return redirect(url_for('patient_login'))

        if booking_exists:
            print(f"SUCCESS: Patient login '{patient_identifier}'.")
            return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
        else:
            print(f"FAIL: Patient login '{patient_identifier}'.")
            flash('⛔ No active bookings found matching that Name/Phone.', 'error')
            return redirect(url_for('patient_login'))

    # GET request
    return render_template('patient_login.html')
# --- END OF REVISED patient_login ---


# --- Patient Dashboard Route (REVISED with 2-query workaround) ---
@app.route('/patient-dashboard/<path:patient_identifier>')
def patient_dashboard(patient_identifier):
    print(f"--- Loading Patient Dashboard ID: '{patient_identifier}' ---")
    if not patient_identifier or not patient_identifier.strip():
        flash('⛔ Patient identifier missing.', 'error'); return redirect(url_for('patient_login'))

    combined_bookings_data = {} # Use dict to handle duplicates by ID
    db_error = False
    actual_patient_name = patient_identifier # Default

    try:
        print(f"DEBUG: Fetching bookings for '{patient_identifier}'")
        select_columns = 'id, doctor_id, doctor_name, patient_name, patient_phone, booking_date, booking_time, status, notes' # Define columns

        # Query 1: Fetch by name (ilike)
        name_query = supabase.table('bookings').select(select_columns) \
            .ilike('patient_name', f'%{patient_identifier}%') \
            .neq('status', 'Cancelled') \
            .order('booking_date', desc=True).order('booking_time', desc=True)
        name_response = name_query.execute()
        print(f"DEBUG: Fetch by Name Response count: {len(name_response.data) if name_response.data else 0}")
        if name_response.data:
            for booking in name_response.data:
                 if 'id' in booking: combined_bookings_data[booking['id']] = booking

        # Query 2: Fetch by phone
        phone_query = supabase.table('bookings').select(select_columns) \
             .eq('patient_phone', patient_identifier) \
             .neq('status', 'Cancelled') \
             .order('booking_date', desc=True).order('booking_time', desc=True)
        phone_response = phone_query.execute()
        print(f"DEBUG: Fetch by Phone Response count: {len(phone_response.data) if phone_response.data else 0}")
        if phone_response.data:
             for booking in phone_response.data:
                  if 'id' in booking: combined_bookings_data[booking['id']] = booking # Add/overwrite by ID

        # Convert combined dict back to list and sort again
        bookings_data = sorted(combined_bookings_data.values(),
                               key=lambda b: (b.get('booking_date', '0000-00-00'), b.get('booking_time', '00:00')),
                               reverse=True)
        print(f"DEBUG: Total unique bookings found: {len(bookings_data)}")

        processed_bookings = [] # Final list with deletable flag
        if bookings_data:
             # Get display name from the first (most recent) booking
             actual_patient_name = bookings_data[0].get('patient_name', patient_identifier).strip()
             print(f"DEBUG: Displaying as '{actual_patient_name}'.")

             now = datetime.now()
             for booking in bookings_data:
                 booking['is_deletable'] = False # Default
                 if booking.get('status') == 'Pending':
                      try:
                           date_str = booking.get('booking_date'); time_slot = booking.get('booking_time', '');
                           if date_str and time_slot and '-' in time_slot and ':' in time_slot:
                                start_time_str = time_slot.split('-')[0].strip()
                                appointment_dt = datetime.strptime(f"{date_str} {start_time_str}", '%Y-%m-%d %H:%M')
                                if appointment_dt > now: booking['is_deletable'] = True
                           # else: print(f"Warn: Invalid format for delete check ID {booking.get('id')}")
                      except (ValueError, IndexError, TypeError, KeyError) as e: print(f"Warn: Parse error delete check ID {booking.get('id')}: {e}")
                 processed_bookings.append(booking)
        else:
             if patient_identifier.strip(): flash('ℹ️ No active bookings found for this identifier.', 'info'); print(f"INFO: No active bookings found for '{patient_identifier}'")

    except Exception as e:
        print(f"ERROR: Supabase loading Patient Dashboard '{patient_identifier}':"); traceback.print_exc()
        flash(f'⛔ Database error loading bookings: {getattr(e, "message", str(e))}', 'error'); db_error = True

    return render_template('patient_dashboard.html',
                           bookings=processed_bookings,
                           patient_identifier=patient_identifier,
                           patient_display_name=actual_patient_name,
                           error=db_error)
# --- END OF REVISED patient_dashboard ---


# --- Run Application ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003)) # Use PORT env var, default 5003
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    print(f"--- Starting Flask Application ---")
    print(f"Mode: {'Debug' if debug_mode else 'Production'}")
    print(f"URL: http://0.0.0.0:{port}")
    print(f"Supabase URL: {supabase_url[:20]}...") # Print prefix only
    app.run(debug=debug_mode, port=port, host='0.0.0.0')

# --- END OF FILE app.py ---