from flask import (
    Flask, render_template, json, request, redirect, url_for,
    send_from_directory, flash, jsonify, make_response
)
import sqlite3
from flask_login import LoginManager, UserMixin, current_user # Assuming you might use login later
import os
from datetime import datetime, timedelta, date, time # Added time for comparison
import uuid
from collections import defaultdict # Helpful for aggregation
import json # Needed for handling JSON in DB
import math # For ceiling function for stars

app = Flask(__name__, static_folder='static')

# Required for flash messages and sessions (if using Flask-Login)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key_1234') # Use environment variable or secure key

# --- Login Manager Setup (Keep if using authentication) ---
# ... (Login Manager code remains the same) ...
login_manager = LoginManager(); login_manager.init_app(app)
class User(UserMixin):
    def __init__(self, id): self.id = id
@login_manager.user_loader
def load_user(user_id):
    if user_id: return User(user_id)
    return None
# --- End Login Manager Setup ---

# --- Database Initialization ---
def get_db():
    db_folder = 'database'; db_path = os.path.join(db_folder, 'bookings.db')
    try:
        conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; return conn
    except sqlite3.Error as e: print(f"DB connection error: {e}"); return None

def init_db():
    db_folder = 'database'; db_path = os.path.join(db_folder, 'bookings.db')
    if not os.path.exists(db_folder): os.makedirs(db_folder)
    conn = None
    try:
        conn = sqlite3.connect(db_path); c = conn.cursor(); print("Initializing database...")
        # --- Create Bookings Table ---
        # Ensure booking_time format is consistently stored (e.g., HH:MM-HH:MM)
        c.execute('''CREATE TABLE IF NOT EXISTS bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doctor_id INTEGER NOT NULL,
                        doctor_name TEXT,
                        patient_name TEXT NOT NULL,
                        patient_phone TEXT,
                        booking_date TEXT NOT NULL, -- YYYY-MM-DD
                        booking_time TEXT NOT NULL, -- HH:MM-HH:MM
                        notes TEXT,
                        appointment_type TEXT DEFAULT 'Consultation',
                        status TEXT DEFAULT 'Pending', -- Pending, Completed, Cancelled
                        ip_address TEXT,
                        cookie_id TEXT,
                        fingerprint TEXT,
                        user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
                    )''')
        print("Bookings table checked/created.")
        # --- Create Doctors Table ---
        c.execute('''CREATE TABLE IF NOT EXISTS doctors (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        availability1shortform TEXT,
                        province TEXT,
                        governorate TEXT,
                        facility_type TEXT,
                        rate REAL,
                        plc TEXT,
                        specialization TEXT,
                        photo TEXT,
                        description TEXT,
                        availability TEXT -- JSON stored as TEXT
                    )''')
        print("Doctors table checked/created.")
        # --- Create Doctor Reviews Table ---
        c.execute('''CREATE TABLE IF NOT EXISTS reviews (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doctor_id INTEGER NOT NULL,
                        reviewer_name TEXT NOT NULL,
                        reviewer_phone TEXT,
                        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                        comment TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_approved INTEGER DEFAULT 1, -- Assuming auto-approved for now
                        FOREIGN KEY (doctor_id) REFERENCES doctors(id)
                    )''')
        print("Doctor Reviews table checked/created.")

        # --- Create Site Reviews Table ---
        c.execute('''CREATE TABLE IF NOT EXISTS site_reviews (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        reviewer_name TEXT NOT NULL,
                        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                        comment TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_approved INTEGER DEFAULT 1
                    )''')
        print("Site Reviews table checked/created.")

        # --- Populate Doctors Table (Only if empty) ---
        c.execute("SELECT COUNT(*) FROM doctors")
        if c.fetchone()[0] == 0:
             print("Populating Doctors table..."); initial_doctors = [ {"id": 1, "name": "Dr. Aisha Khan", "availability1shortform": "Mon-Thu: 7am-8am, Sat-Sun: 8am-11am", "province": "Bagmati", "governorate": "Kathmandu", "facility_type": "Private Clinic", "rate": 4.5, "plc": "City Clinic", "specialization": "Dermatology", "photo": "/static/doctors/doctor1.jpg", "description": "Expert dermatology care.", "availability": json.dumps({"Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"],"Wednesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Thursday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Friday": ["Unavailable"],"Saturday": ["08:00-08:20", "08:20-08:40", "08:40-09:00", "09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"], "Sunday": ["08:00-08:20", "08:20-08:40", "08:40-09:00"]})}, {"id": 2, "name": "Dr. Binod Sharma", "availability1shortform": "Mon-Wed: 7am-8am, Sat: 8am-11am, Sun: 8am-9am", "province": "Gandaki", "governorate": "Kaski", "facility_type": "Hospital", "rate": 4.2, "plc": "Lakeview Hospital", "specialization": "Cardiology", "photo": "/static/doctors/doctor3.jpg", "description": "Heart health specialist.", "availability": json.dumps({"Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Wednesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Thursday": ["Unavailable"], "Friday": ["Unavailable"], "Saturday": ["08:00-08:20", "08:20-08:40", "08:40-09:00", "09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"], "Sunday": ["08:00-08:20", "08:20-08:40", "08:40-09:00"]})}, # (Include all other initial doctor data)
            {"id": 11, "name": "Dr. Sofia Anders", "availability1shortform": "Mon, Wed: 9am-11am", "province": "Bagmati", "governorate": "Kathmandu", "facility_type": "Private Clinic", "rate": 4.6, "plc": "City Clinic", "specialization": "General Physician", "photo": "/static/doctors/doctor_female_gp.jpg", "description": "Primary care provider.", "availability": json.dumps({"Monday": ["09:00-09:30", "09:30-10:00", "10:00-10:30", "10:30-11:00"], "Tuesday": ["Unavailable"], "Wednesday": ["09:00-09:30", "09:30-10:00", "10:00-10:30", "10:30-11:00"], "Thursday": ["Unavailable"], "Friday": ["Unavailable"], "Saturday": ["Unavailable"], "Sunday": ["Unavailable"]})}]
             c.executemany('INSERT INTO doctors (id, name, availability1shortform, province, governorate, facility_type, rate, plc, specialization, photo, description, availability) VALUES (:id, :name, :availability1shortform, :province, :governorate, :facility_type, :rate, :plc, :specialization, :photo, :description, :availability)', initial_doctors)
             print(f"Inserted {len(initial_doctors)} doctors.")
        else: print("Doctors table populated.")
        # --- Add Indexes ---
        c.execute("CREATE INDEX IF NOT EXISTS idx_booking_doctor_date ON bookings(doctor_id, booking_date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reviews_doctor_id ON reviews(doctor_id)")
        # --- *NEW*: Index for Site Reviews ---
        c.execute("CREATE INDEX IF NOT EXISTS idx_site_reviews_approved_created ON site_reviews(is_approved, created_at DESC)")
        # --- Indexes for review checks ---
        c.execute("CREATE INDEX IF NOT EXISTS idx_reviews_doctor_name ON reviews(doctor_id, reviewer_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reviews_doctor_phone ON reviews(doctor_id, reviewer_phone)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_patient_lookup ON bookings(doctor_id, patient_name, patient_phone, booking_date, booking_time)")
        print("Indexes checked/created.")
        conn.commit()
        print("Database initialization complete.")
    except sqlite3.Error as e: print(f"DB init error: {e}"); conn.rollback()
    finally:
         if conn: conn.close()

# --- Load doctors data FROM DATABASE (includes ratings) ---
def load_doctors_from_db():
    """Fetches doctors, parses availability, and calculates average rating."""
    conn = get_db()
    if not conn: print("CRITICAL: DB fail load_doctors_from_db."); return []
    doctors_list = []
    try:
        c = conn.cursor(); c.execute("SELECT * FROM doctors ORDER BY name ASC"); doctors_rows = c.fetchall()
        if not doctors_rows: return []
        # Initialize list with defaults
        doctors_list = []
        for row in doctors_rows:
            doctor_dict = dict(row)
            try:
                # Ensure availability is loaded as JSON or defaults to empty dict
                avail_json = doctor_dict.get('availability', '{}')
                doctor_dict['availability'] = json.loads(avail_json if avail_json else '{}')
            except (json.JSONDecodeError, TypeError) as json_err:
                print(f"Warn: Availability JSON parse error for doctor {row['id']}: {json_err}")
                doctor_dict['availability'] = {} # Default to empty if JSON is bad
            doctor_dict['average_rating'] = 0.0
            doctor_dict['review_count'] = 0
            doctors_list.append(doctor_dict)

        # Calculate ratings from doctor reviews table
        doctor_map = {doc['id']: doc for doc in doctors_list}
        # Query only approved reviews for average calculation
        c.execute('''SELECT doctor_id, AVG(rating) as avg_r, COUNT(id) as count_r
                     FROM reviews WHERE is_approved = 1 GROUP BY doctor_id''')
        rating_rows = c.fetchall()
        for rating_row in rating_rows:
            doc_id = rating_row['doctor_id']
            if doc_id in doctor_map:
                # Ensure avg_r is not None before rounding
                doctor_map[doc_id]['average_rating'] = round(rating_row['avg_r'], 1) if rating_row['avg_r'] is not None else 0.0
                doctor_map[doc_id]['review_count'] = rating_row['count_r']

        doctors_list = list(doctor_map.values()) # Update list with calculated ratings

    except sqlite3.Error as e:
        print(f"Error loading doctors data: {e}"); return []
    finally:
        if conn: conn.close()
    print(f"Loaded {len(doctors_list)} doctors with rating info.");
    return doctors_list


# --- Initialize DB and Load Global Data ---
init_db()
doctors_data = load_doctors_from_db()
if not doctors_data: print("CRITICAL WARNING: Failed to load doctor data.")

# --- Jinja Helper Function for Stars ---
@app.context_processor
def utility_processor():
    def get_stars(rating):
        if rating is None or not isinstance(rating, (int, float)) or rating < 0: return ['far fa-star'] * 5
        rating = max(0, min(5, float(rating))) # Clamp between 0 and 5
        full = math.floor(rating); half = (rating - full) >= 0.5; empty = 5 - full - (1 if half else 0)
        stars = ['fas fa-star'] * full + (['fas fa-star-half-alt'] if half else []) + ['far fa-star'] * empty
        return stars
    return dict(get_stars=get_stars)

# --- Routes ---
@app.route('/')
def home():
    stats = { 'doctor_count': len(doctors_data), 'specialty_count': 0, 'total_bookings': 0, 'total_active_bookings': 0 } # Ensure keys exist
    specialties = []
    governorates = []
    facility_types = []
    plcs = []
    site_reviews = [] # ** NEW: List for site reviews

    # --- Load Filter Options from doctors_data (Cached) ---
    if doctors_data:
        try:
            unique_specs = sorted(list({d['specialization'] for d in doctors_data if d.get('specialization')}))
            unique_govs = sorted(list({d['governorate'] for d in doctors_data if d.get('governorate')}))
            unique_fac_types = sorted(list({d['facility_type'] for d in doctors_data if d.get('facility_type')}))
            unique_plcs = sorted(list({d['plc'] for d in doctors_data if d.get('plc')}))

            stats['specialty_count'] = len(unique_specs)
            specialties = unique_specs
            governorates = unique_govs
            facility_types = unique_fac_types
            plcs = unique_plcs
        except Exception as e:
             print(f"Warn: Error processing doctor_data for filters: {e}")


    # --- Fetch Counts & Site Reviews from DB ---
    conn = get_db()
    if conn:
        c = conn.cursor()
        try:
            # Get booking counts
            c.execute("SELECT COUNT(*) FROM bookings WHERE status != 'Cancelled'");
            active_count = c.fetchone()
            stats['total_active_bookings'] = active_count[0] if active_count else 0
            c.execute("SELECT COUNT(*) FROM bookings");
            all_count = c.fetchone()
            stats['total_bookings'] = all_count[0] if all_count else 0

            # ** NEW: Fetch recent approved SITE reviews **
            c.execute("""
                SELECT reviewer_name, rating, comment, created_at
                FROM site_reviews
                WHERE is_approved = 1
                ORDER BY created_at DESC
                LIMIT 3
            """)
            site_reviews = [dict(row) for row in c.fetchall()]
            print(f"Fetched {len(site_reviews)} site reviews for homepage.")

        except sqlite3.Error as e:
            print(f"Warn: DB err reading stats/site reviews for home: {e}")
        finally:
            conn.close()
    else:
        print("Warn: DB conn fail home."); flash('Stats/filters may be outdated or incomplete.', 'info')

    return render_template(
        'index.html',
        doctors=doctors_data,
        stats=stats,
        specialties=specialties,
        governorates=governorates,
        facility_types=facility_types,
        plcs=plcs,
        site_reviews=site_reviews # ** Pass SITE reviews to template
    )

# --- NEW: Submit Site Review Route ---
@app.route('/submit-site-review', methods=['POST'])
def submit_site_review():
    reviewer_name = request.form.get('reviewer_name', '').strip()
    rating_str = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    # --- Validation ---
    errors = []
    if not reviewer_name:
        errors.append('Your name is required for the review.')
    if not rating_str or not rating_str.isdigit() or not (1 <= int(rating_str) <= 5):
        errors.append('Please select a valid rating (1-5 stars).')
    # Comment is optional

    if errors:
        for error in errors:
            flash(f'⛔ {error}', 'error')
        # Redirect back to home, perhaps trying to land near the form using an anchor
        return redirect(url_for('home') + '#site-review-form-section')

    # --- Database Insert ---
    conn = None
    try:
        conn = get_db()
        if not conn:
            flash('⛔ Database connection error. Could not save review.', 'error')
            return redirect(url_for('home') + '#site-review-form-section')
        c = conn.cursor()

        # Insert the new site review (assuming default is_approved=1)
        c.execute('''INSERT INTO site_reviews (reviewer_name, rating, comment)
                     VALUES (?, ?, ?)''',
                  (reviewer_name, int(rating_str), comment))
        conn.commit()
        print(f"Site review added by {reviewer_name}.")
        flash('✅ Thank you for your feedback!', 'success')

    except sqlite3.IntegrityError as e: # e.g., rating check constraint
        print(f"Integrity error submitting site review: {e}");
        flash('⛔ Invalid data provided for review (e.g., rating out of range).', 'error');
        if conn: conn.rollback()
    except sqlite3.Error as e:
        print(f"Database error submitting site review: {e}");
        flash('⛔ Database error submitting your feedback.', 'error');
        if conn: conn.rollback()
    except Exception as e:
        print(f"Unexpected error submitting site review: {e}");
        flash('⛔ An unexpected error occurred.', 'error');
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

    # Redirect back to the homepage, focusing on the review display area
    return redirect(url_for('home') + '#site-reviews-section')


# --- DOCTOR Review Submission Route (EDITED FOR NEW RULES) ---
@app.route('/submit-review', methods=['POST'])
def submit_review():
    doctor_id_str = request.form.get('doctor_id')
    reviewer_name = request.form.get('reviewer_name', '').strip()
    reviewer_phone = request.form.get('reviewer_phone', '').strip()
    rating_str = request.form.get('rating')
    comment = request.form.get('comment', '').strip()

    # --- Basic Validation ---
    errors = []
    doctor_id = None
    if not doctor_id_str or not doctor_id_str.isdigit():
        errors.append('Invalid Doctor ID provided.')
    else:
        doctor_id = int(doctor_id_str)

    if not reviewer_name:
        errors.append('Your name is required for the review.')
    if not reviewer_phone: # Keep phone required for robust matching
        errors.append('Your phone number is required for the review.')
    if not rating_str or not rating_str.isdigit() or not (1 <= int(rating_str) <= 5):
        errors.append('Please select a valid rating (1-5 stars).')

    if errors:
        for error in errors: flash(f'⛔ {error}', 'error')
        # Redirect back to the booking page if possible, otherwise home
        redirect_url = url_for('booking_page', doctor_id=doctor_id) if doctor_id else url_for('home')
        # Use request.referrer as a fallback if direct URL fails (e.g., error before doctor_id parsed)
        return redirect(request.referrer or redirect_url)

    # --- Database Operations and Advanced Validation ---
    conn = None
    try:
        conn = get_db()
        if not conn:
            flash('⛔ Database connection error. Please try again later.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))
        c = conn.cursor()

        # *** CHECK 1: Has this person (name OR phone) already reviewed THIS doctor? ***
        c.execute('''SELECT 1 FROM reviews
                     WHERE doctor_id = ? AND (LOWER(reviewer_name) = LOWER(?) OR reviewer_phone = ?)
                     LIMIT 1''',
                  (doctor_id, reviewer_name, reviewer_phone))
        if c.fetchone():
            flash('⛔ You have already submitted a review for this doctor using this name or phone number.', 'error')
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # *** CHECK 2: Find the LATEST relevant booking to check appointment time ***
        c.execute('''SELECT booking_date, booking_time FROM bookings
                     WHERE doctor_id = ? AND (LOWER(patient_name) = LOWER(?) OR patient_phone = ?)
                       AND status != 'Cancelled'
                     ORDER BY booking_date DESC, booking_time DESC
                     LIMIT 1''',
                  (doctor_id, reviewer_name, reviewer_phone))
        latest_booking = c.fetchone()

        if not latest_booking:
            flash('⛔ No booking found for this name or phone number with this doctor. You must book first to review.', 'error')
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # *** CHECK 3: Has the appointment time passed? ***
        try:
            booking_date_str = latest_booking['booking_date']
            booking_time_slot = latest_booking['booking_time'] # e.g., "09:00-09:20"

            # Extract start time HH:MM
            booking_start_time_str = booking_time_slot.split('-')[0].strip()

            # Combine date and start time string
            appointment_datetime_str = f"{booking_date_str} {booking_start_time_str}"

            # Parse into a datetime object
            # Use a specific format that matches your stored data (YYYY-MM-DD HH:MM)
            appointment_start_dt = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M')

            # Get current time
            now_dt = datetime.now()

            # Compare
            if now_dt < appointment_start_dt:
                appointment_time_formatted = appointment_start_dt.strftime('%I:%M %p on %b %d, %Y') # e.g., 09:00 AM on Jan 15, 2024
                flash(f'⛔ You cannot review this doctor until after your scheduled appointment time ({appointment_time_formatted}).', 'error')
                conn.close()
                return redirect(url_for('booking_page', doctor_id=doctor_id))

        except (ValueError, IndexError, TypeError) as e:
            print(f"Error parsing booking date/time for review check (Booking ID maybe relevant if available): {e}")
            flash('⛔ Could not verify appointment time due to a data format issue. Please contact support.', 'error')
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # --- If all checks passed, Insert the DOCTOR review ---
        c.execute('''INSERT INTO reviews (doctor_id, reviewer_name, reviewer_phone, rating, comment)
                     VALUES (?, ?, ?, ?, ?)''',
                  (doctor_id, reviewer_name, reviewer_phone, int(rating_str), comment))
        conn.commit()
        flash('✅ Thank you! Your review has been submitted.', 'success')

        # Refresh global doctor data as ratings might change
        global doctors_data
        doctors_data = load_doctors_from_db()
        print(f"Doctor review added for Dr {doctor_id} by {reviewer_name}. Global doctors_data refreshed.")

    except sqlite3.IntegrityError as e: # e.g., rating check constraint failure
        print(f"Integrity error submitting DR review {doctor_id}: {e}");
        flash('⛔ Invalid data provided for review (e.g., rating out of range).', 'error');
        if conn: conn.rollback()
    except sqlite3.Error as e:
        print(f"DB error submitting DR review {doctor_id}: {e}");
        flash('⛔ Database error submitting your review. Please try again.', 'error');
        if conn: conn.rollback()
    except Exception as e:
        print(f"Unexpected error submitting DR review {doctor_id}: {e}");
        flash('⛔ An unexpected error occurred while submitting your review.', 'error');
        if conn: conn.rollback()
    finally:
        if conn: conn.close() # Ensure connection is always closed

    # Redirect back to the doctor's booking page
    return redirect(url_for('booking_page', doctor_id=doctor_id))



# --- Other Routes (Booking Page, Center Details, Confirm, Dashboards etc.) ---
# These remain largely unchanged, but rely on the potentially updated 'doctors_data' global variable.

@app.route('/booking/<int:doctor_id>')
def booking_page(doctor_id):
    # Find the doctor using the globally loaded data first
    doctor = next((d for d in doctors_data if d.get('id') == doctor_id), None)

    if not doctor:
        # Fallback: Try fetching from DB directly if not found in cache
        conn_fb = get_db()
        if conn_fb:
            try:
                c_fb = conn_fb.cursor()
                c_fb.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
                doc_row = c_fb.fetchone()
                if doc_row:
                    doctor = dict(doc_row)
                    # Parse availability JSON from DB string
                    try:
                        avail_json = doctor.get('availability', '{}')
                        doctor['availability'] = json.loads(avail_json if avail_json else '{}')
                    except (json.JSONDecodeError, TypeError):
                         doctor['availability'] = {} # Default on error
                    # Fetch average rating and count for this specific doctor
                    doctor['average_rating'] = 0.0
                    doctor['review_count'] = 0
                    c_fb.execute('''SELECT AVG(rating) as avg_r, COUNT(id) as count_r
                                    FROM reviews
                                    WHERE is_approved = 1 AND doctor_id = ?''', (doctor_id,))
                    rating_row = c_fb.fetchone()
                    if rating_row:
                        doctor['average_rating'] = round(rating_row['avg_r'], 1) if rating_row['avg_r'] is not None else 0.0
                        doctor['review_count'] = rating_row['count_r']
                else:
                    flash('Doctor not found.', 'error')
                    return redirect(url_for('home'))
            except sqlite3.Error as e:
                print(f"Error fetching doctor fallback {doctor_id}: {e}")
                flash('Error loading doctor details.', 'error')
                return redirect(url_for('home'))
            finally:
                conn_fb.close()
        else:
             flash('Database connection error.', 'error')
             return redirect(url_for('home')) # DB error, redirect home

    if not doctor: # If still not found after fallback
         flash('Doctor not found.', 'error'); return redirect(url_for('home'))

    # Fetch Doctor Reviews for this specific doctor
    reviews = []
    conn_rev = get_db()
    if conn_rev:
        try:
            c_rev = conn_rev.cursor()
            # Fetch approved reviews only
            c_rev.execute("""SELECT reviewer_name, rating, comment, created_at
                             FROM reviews
                             WHERE doctor_id = ? AND is_approved = 1
                             ORDER BY created_at DESC
                             LIMIT 10""", (doctor_id,))
            reviews = [dict(row) for row in c_rev.fetchall()]
        except sqlite3.Error as e: print(f"Error fetching reviews for dr {doctor_id}: {e}")
        finally: conn_rev.close()
    else: print(f"Warn: DB conn fail fetch reviews dr {doctor_id}.")

    today_str = date.today().strftime('%Y-%m-%d')
    # Ensure availability is passed as JSON string for the template JS
    doctor_availability_schedule = json.dumps(doctor.get('availability', {}))

    response = make_response(render_template(
        'booking.html', doctor=doctor, doctor_id=doctor_id, today=today_str,
        doctor_availability_schedule=doctor_availability_schedule, reviews=reviews
    ))
    # Set cookie if not present
    if not request.cookies.get('device_id'):
        device_id = str(uuid.uuid4())
        # Set cookie attributes: secure=True (for HTTPS), httponly=True, samesite='Lax'
        response.set_cookie('device_id', device_id, max_age=30*24*60*60, httponly=True, samesite='Lax', secure=request.is_secure)
    return response


@app.route('/center/<path:plc_name>')
def center_details(plc_name):
    if not plc_name: flash('No clinic name provided.', 'error'); return redirect(url_for('home'))
    # Filter doctors based on PLC name from the global list
    plc_doctors = [doc for doc in doctors_data if doc.get('plc') == plc_name]
    if not plc_doctors: flash(f'Details not found for clinic/center "{plc_name}".', 'error'); return redirect(url_for('home'))
    # Extract PLC info from the first doctor found (assuming consistent per PLC)
    first_doc = plc_doctors[0]
    plc_info = {
        'name': plc_name,
        'facility_type': first_doc.get('facility_type', 'N/A'),
        'locations': sorted(list({ # Get unique locations (Province, Governorate)
            (d.get('province', 'N/A'), d.get('governorate', 'N/A'))
            for d in plc_doctors if d.get('province') or d.get('governorate') # Only include if at least one is present
        }))
    }
    # Generate a safe slug for image lookup
    plc_slug = plc_name.lower().replace(' ', '_').replace('&', 'and').replace('.', '').replace("'", '')
    plc_info['photo_path_jpg'] = f'/static/plc_photos/{plc_slug}.jpg'
    # Check if image exists? Optional, can be handled by 404 or placeholder in template
    return render_template('center_details.html', plc=plc_info, doctors=plc_doctors)


# --- Routes like get-nearest, get-slots, confirm-booking, confirmation, dashboards, etc. are UNCHANGED ---
@app.route('/get-nearest-available/<int:doctor_id>')
def get_nearest_available(doctor_id):
    # Find doctor in the globally loaded data
    doctor = next((d for d in doctors_data if d.get('id') == doctor_id), None)
    if not doctor:
        return jsonify({'success': False, 'message': 'Doctor not found'}), 404

    doctor_availability = doctor.get('availability', {}) # Already parsed JSON
    if not doctor_availability:
        return jsonify({'success': False, 'message': 'Doctor schedule information is currently unavailable.'}), 404

    today_date = date.today()
    conn = None
    try:
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error.'}), 500
        c = conn.cursor()

        now_time = datetime.now().time()

        # Iterate through days starting from today
        for i in range(90): # Look up to ~3 months ahead
            current_check_date = today_date + timedelta(days=i)
            date_str = current_check_date.strftime('%Y-%m-%d')
            day_name = current_check_date.strftime('%A') # Get day name (e.g., "Monday")

            # Get general slots for this day name from doctor's availability
            general_slots_raw = doctor_availability.get(day_name, [])
            # Filter and sort valid slots
            general_slots = sorted([
                slot for slot in general_slots_raw
                if isinstance(slot, str) and slot.strip() and slot.lower() != "unavailable" and '-' in slot # Assuming format HH:MM-HH:MM
            ])

            if not general_slots:
                continue # Skip if no slots defined for this day

            # Fetch times already booked for this doctor on this date
            c.execute("""
                SELECT booking_time FROM bookings
                WHERE doctor_id = ? AND booking_date = ? AND status != 'Cancelled'
            """, (doctor_id, date_str))
            booked_times = {row['booking_time'] for row in c.fetchall()}

            # Find the first available slot
            for slot in general_slots:
                if slot not in booked_times:
                    # If checking today, ensure the slot start time is in the future
                    if current_check_date == today_date:
                        try:
                            slot_start_str = slot.split('-')[0].strip() # Get HH:MM part
                            slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                            if slot_start_time > now_time:
                                return jsonify({'success': True, 'date': date_str, 'time': slot})
                        except (ValueError, IndexError): # Added IndexError for split
                            print(f"Warn: Could not parse time slot '{slot}' for comparison.")
                            continue # Skip potentially malformed slot
                    else:
                        # For future dates, any available slot is fine
                        return jsonify({'success': True, 'date': date_str, 'time': slot})

        # If loop finishes without finding a slot
        return jsonify({'success': False, 'message': 'No available appointment slots found in the near future.'}), 404

    except sqlite3.Error as db_err:
        print(f"Database Error (get_nearest_available for {doctor_id}): {db_err}")
        return jsonify({'success': False, 'message': 'A database error occurred.'}), 500
    except Exception as e:
        print(f"Unexpected Error (get_nearest_available for {doctor_id}): {e}")
        return jsonify({'success': False, 'message': 'An internal server error occurred.'}), 500
    finally:
        if conn:
            conn.close()


@app.route('/get-available-slots/<int:doctor_id>/<string:date_str>')
def get_available_slots(doctor_id, date_str):
    conn = None
    try:
        # Validate date format first
        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format provided. Use YYYY-MM-DD.'}), 400

        day_name = booking_date.strftime('%A')

        # Find the doctor in the globally loaded data
        doctor = next((d for d in doctors_data if d.get('id') == doctor_id), None)
        if not doctor:
            return jsonify({'error': 'Doctor information not found'}), 404

        doctor_availability = doctor.get('availability', {}) # Already parsed JSON
        if not doctor_availability:
            return jsonify([]) # Return empty list if no schedule defined

        # Get general slots for the specified day name
        general_slots_raw = doctor_availability.get(day_name, [])
        # Filter for valid, non-unavailable slots and sort them
        general_slots = sorted([
            slot for slot in general_slots_raw
            if isinstance(slot, str) and slot.strip() and slot.lower() != "unavailable" and '-' in slot
        ])

        if not general_slots:
            return jsonify([]) # No slots defined for this day

        # Fetch booked times for this specific date from the database
        conn = get_db()
        if not conn:
             print(f"Error: DB connection failed in get_available_slots for {doctor_id}/{date_str}")
             return jsonify({'error': 'Could not verify booked slots. Please try again later.'}), 503 # Service Unavailable

        booked_times = set()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT booking_time FROM bookings
                WHERE doctor_id = ? AND booking_date = ? AND status != 'Cancelled'
            """, (doctor_id, date_str))
            booked_times = {row['booking_time'] for row in c.fetchall()}
        except sqlite3.Error as e:
            print(f"DB error fetching booked times for {doctor_id} on {date_str}: {e}")
            return jsonify([]) # Return empty on DB error during check
        finally:
            if conn: conn.close()

        # Filter out booked times
        available_slots = [slot for slot in general_slots if slot not in booked_times]

        # Filter out past times if the date is today
        if booking_date == date.today():
             now_time = datetime.now().time()
             future_slots = []
             for slot in available_slots:
                try:
                    slot_start_str = slot.split('-')[0].strip() # Get HH:MM part
                    slot_start_time = datetime.strptime(slot_start_str, '%H:%M').time()
                    if slot_start_time > now_time:
                        future_slots.append(slot)
                except (ValueError, IndexError): # Added IndexError
                    print(f"Warn: Could not parse time slot '{slot}' for today's filtering.")
             available_slots = future_slots

        return jsonify(available_slots)

    except Exception as e:
        print(f"Unexpected Error (get_available_slots for {doctor_id}/{date_str}): {e}")
        return jsonify({'error': 'An internal server error occurred.'}), 500


@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    # --- Get Data ---
    doctor_id_str = request.form.get('doctor_id')
    doctor_name = request.form.get('doctor_name')
    patient_name = request.form.get('patient_name', '').strip() # Default to empty, then strip
    patient_phone = request.form.get('patient_phone', '').strip()
    booking_date = request.form.get('booking_date')
    booking_time = request.form.get('booking_time')
    notes = request.form.get('notes', '').strip()
    fingerprint = request.form.get('fingerprint') # Optional fingerprint
    cookie_id = request.cookies.get('device_id') # Optional cookie ID
    ip_address = request.remote_addr # Get IP address

    # --- Basic Validation ---
    if not all([doctor_id_str, doctor_name, patient_name, patient_phone, booking_date, booking_time]):
        flash('⛔ Please ensure all required fields (name, phone, date, time) are filled.', 'error')
        referrer_url = request.referrer or url_for('home')
        if doctor_id_str and doctor_id_str.isdigit():
            try: referrer_url = url_for('booking_page', doctor_id=int(doctor_id_str))
            except: pass # Ignore errors generating URL, use referrer
        return redirect(referrer_url)

    try:
        doctor_id = int(doctor_id_str)
    except ValueError:
        flash('⛔ Invalid Doctor ID.', 'error')
        return redirect(url_for('home'))

    # --- Find Doctor & Validate Slot ---
    doctor = next((d for d in doctors_data if d.get('id') == doctor_id), None)
    if not doctor:
        flash(f'⛔ Doctor with ID {doctor_id} not found.', 'error')
        return redirect(url_for('home'))

    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        if booking_date_obj < date.today():
            flash('⛔ Cannot book an appointment in the past.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))
        selected_day_name = booking_date_obj.strftime('%A')
    except ValueError:
        flash('⛔ Invalid date format submitted.', 'error')
        return redirect(url_for('booking_page', doctor_id=doctor_id))

    # Check if the selected time slot is generally valid for the doctor on that day
    doctor_schedule = doctor.get('availability', {})
    day_schedule = doctor_schedule.get(selected_day_name, [])
    # Ensure check accounts for potentially non-string items if JSON is weird
    general_slots = [s for s in day_schedule if isinstance(s, str) and s.strip() and s.lower() != 'unavailable' and '-' in s]

    if booking_time not in general_slots:
        flash('⛔ The selected time slot is not valid for this doctor on the chosen date.', 'error')
        return redirect(url_for('booking_page', doctor_id=doctor_id))

    # --- Database Interaction ---
    conn = None
    booking_id = None
    try:
        conn = get_db()
        if not conn:
            flash('⛔ Database error. Please try again later.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))
        c = conn.cursor()

        # ** CHECK 1: Is the specific slot already booked? (Atomic Check) **
        # This check prevents race conditions where two users try to book the same slot simultaneously.
        c.execute("""
            SELECT 1 FROM bookings
            WHERE doctor_id = ? AND booking_date = ? AND booking_time = ?
              AND status != 'Cancelled'
            LIMIT 1
        """, (doctor_id, booking_date, booking_time))
        if c.fetchone():
            flash('⛔ Sorry, this time slot was just booked by someone else. Please select another time.', 'error')
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # ** CHECK 2: Does this patient (name OR phone) already have a booking on this DATE? **
        c.execute("""
            SELECT id, booking_time FROM bookings
            WHERE (LOWER(patient_name) = LOWER(?) OR patient_phone = ?)
              AND doctor_id = ? AND booking_date = ? AND status != 'Cancelled'
            LIMIT 1
        """, (patient_name, patient_phone, doctor_id, booking_date))
        existing_booking_same_day = c.fetchone()
        if existing_booking_same_day:
            existing_time = existing_booking_same_day['booking_time']
            flash(f'ℹ️ You already have an appointment scheduled with this doctor on this date at {existing_time}. Only one booking per day per doctor is allowed.', 'info')
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # --- Insert the Booking ---
        c.execute("""
            INSERT INTO bookings
                (doctor_id, doctor_name, patient_name, patient_phone, booking_date, booking_time, notes, status, ip_address, cookie_id, fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doctor_id, doctor_name, patient_name, patient_phone,
            booking_date, booking_time, notes,
            'Pending', # Initial status
            ip_address, cookie_id, fingerprint # Store tracking info
            ))
        conn.commit()
        booking_id = c.lastrowid # Get the ID of the inserted row

    except sqlite3.Error as e:
        print(f"Database Error (Confirm Booking for Dr {doctor_id}): {e}")
        flash('⛔ A database error occurred while confirming your booking. Please try again.', 'error')
        if conn: conn.rollback() # Rollback on error
        return redirect(url_for('booking_page', doctor_id=doctor_id))
    except Exception as e:
        print(f"Unexpected Error (Confirm Booking for Dr {doctor_id}): {e}")
        flash('⛔ An unexpected error occurred. Please try again.', 'error')
        if conn: conn.rollback() # Rollback on error
        return redirect(url_for('booking_page', doctor_id=doctor_id))
    finally:
        if conn: conn.close() # Ensure connection is closed

    # --- Redirect to Confirmation ---
    if booking_id:
        print(f"Booking confirmed: ID {booking_id}, Dr {doctor_id}, Patient {patient_name}, Date {booking_date} {booking_time}")
        flash('✅ Booking confirmed successfully!', 'success')
        # Pass necessary details to the confirmation page via query parameters
        return redirect(url_for('confirmation',
                                booking_id=booking_id,
                                doctor_name=doctor_name,
                                patient_name=patient_name,
                                booking_date=booking_date,
                                booking_time=booking_time))
    else:
        # This case might occur if insert failed silently (less likely with error handling)
        flash('⛔ Booking could not be confirmed. Please check your details and try again.', 'error')
        return redirect(url_for('booking_page', doctor_id=doctor_id))


@app.route('/confirmation')
def confirmation():
    # Retrieve details from query parameters
    booking_id = request.args.get('booking_id')
    doctor_name = request.args.get('doctor_name')
    patient_name = request.args.get('patient_name')
    booking_date = request.args.get('booking_date')
    booking_time = request.args.get('booking_time')

    if not all([booking_id, doctor_name, patient_name, booking_date, booking_time]):
        flash('Invalid confirmation link or missing details.', 'error')
        return redirect(url_for('home'))

    # Optional: Verify booking_id exists in DB? (Adds overhead but increases security)

    return render_template(
        'confirmation.html', booking_id=booking_id, doctor_name=doctor_name,
        patient_name=patient_name, booking_date=booking_date, booking_time=booking_time
    )


@app.route('/get-doctor-availability/<int:doctor_id>')
def get_doctor_availability(doctor_id): # Primarily used by fullcalendar? (Not core date selection)
    # Find doctor in the globally loaded data
    doctor = next((d for d in doctors_data if d.get('id') == doctor_id), None)
    if not doctor:
        return jsonify({'error': 'Doctor schedule not found'}), 404

    doctor_schedule = doctor.get('availability', {}) # Already parsed JSON
    if not doctor_schedule: return jsonify({}) # Return empty if no schedule defined

    availability_data = defaultdict(list)
    today_dt = date.today()
    end_date = today_dt + timedelta(days=120) # Approx 4 months out
    current_date_loop = today_dt

    while current_date_loop <= end_date:
        day_name = current_date_loop.strftime('%A')
        general_slots_raw = doctor_schedule.get(day_name, [])
        # Check if there are any valid slots defined for this day name
        has_general_slots = any(
            isinstance(slot, str) and slot.strip() and slot.lower() != "unavailable" and '-' in slot
            for slot in general_slots_raw
        )
        if has_general_slots:
            # Could add a check here to see if *any* slots are actually free on this day
            # But for a general availability calendar, just showing days the doctor *works* is usually fine.
            month_str = current_date_loop.strftime('%Y-%m') # Key format 'YYYY-MM'
            day_num = current_date_loop.day
            availability_data[month_str].append(day_num)

        current_date_loop += timedelta(days=1)

    return jsonify(dict(availability_data)) # Convert defaultdict back to dict for JSON

@app.route('/delete-booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    conn = None
    # Determine where the request came from to redirect appropriately
    source = request.form.get('source', 'unknown') # e.g., 'patient_dashboard', 'doctor_dashboard'
    patient_identifier = request.form.get('patient_identifier') # Needed for patient dash redirect
    doctor_id_str = request.form.get('doctor_id') # Needed for doctor dash redirect
    redirect_url = url_for('home') # Default redirect

    # Set specific redirect URLs based on source
    if source == 'patient_dashboard' and patient_identifier:
         redirect_url = url_for('patient_dashboard', patient_identifier=patient_identifier)
    elif source == 'doctor_dashboard' and doctor_id_str and doctor_id_str.isdigit():
         redirect_url = url_for('doctor_dashboard', doctor_id=int(doctor_id_str))
    elif source == 'confirmation_page': # Example if deleting from confirmation
         redirect_url = url_for('home') # Or maybe a dedicated 'booking cancelled' page

    try:
        conn = get_db()
        if not conn:
            flash('⛔ Database connection error. Could not cancel booking.', 'error')
            return redirect(redirect_url)

        c = conn.cursor()
        # Attempt to change status to 'Cancelled' only if it's currently 'Pending'
        c.execute("UPDATE bookings SET status = 'Cancelled' WHERE id = ? AND status = 'Pending'", (booking_id,))
        conn.commit()

        if c.rowcount > 0:
            flash('✅ Booking successfully cancelled.', 'success')
            print(f"Booking {booking_id} status changed to Cancelled.")
        else:
            # Check the current status if no rows were updated
            c.execute('SELECT status FROM bookings WHERE id = ?', (booking_id,))
            result = c.fetchone()
            if result:
                 current_status = result['status']
                 if current_status == 'Cancelled':
                     flash('ℹ️ This booking has already been cancelled.', 'info')
                 elif current_status == 'Completed':
                     flash('ℹ️ This booking cannot be cancelled as it has already been marked completed.', 'info')
                 else:
                     # Should ideally not happen if status was Pending, implies another issue
                     flash(f'ℹ️ Booking could not be cancelled (Current status: {current_status}).', 'info')
            else:
                flash('⛔ Booking not found.', 'error') # Booking ID doesn't exist

    except sqlite3.Error as e:
        print(f"DB Error cancelling booking {booking_id}: {e}")
        flash('⛔ A database error occurred while trying to cancel the booking.', 'error')
        if conn: conn.rollback()
    except Exception as e:
        print(f"Unexpected error cancelling booking {booking_id}: {e}")
        flash('⛔ An unexpected error occurred.', 'error')
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

    return redirect(redirect_url)


# --- Login & Dashboard Routes ---

@app.route('/doctor-login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        doctor_name = request.form.get('doctorName', '').strip()
        doctor_id_str = request.form.get('doctorId', '').strip()

        # Basic validation
        if not doctor_name or not doctor_id_str:
            flash('⛔ Please enter both Doctor Name and Doctor ID.', 'error')
            return redirect(url_for('doctor_login'))
        if not doctor_id_str.isdigit():
            flash('⛔ Doctor ID must be a number.', 'error')
            return redirect(url_for('doctor_login'))

        doctor_id = int(doctor_id_str)

        # Check against the global doctors_data list
        # Case-sensitive match for name might be intended for security/specificity
        doctor = next((d for d in doctors_data if d.get('id') == doctor_id and d.get('name') == doctor_name), None)

        if doctor:
            print(f"Doctor login successful: ID {doctor_id}, Name '{doctor_name}'")
            flash(f'✅ Welcome back, {doctor_name}!', 'success')
            # Redirect to the specific doctor's dashboard
            return redirect(url_for('doctor_dashboard', doctor_id=doctor_id))
        else:
            print(f"Doctor login failed: ID {doctor_id}, Name '{doctor_name}'")
            flash('⛔ Invalid Doctor Name or ID combination. Please try again.', 'error')
            return redirect(url_for('doctor_login'))

    # If GET request, just render the login form
    return render_template('doctor_login.html')


@app.route('/doctor-dashboard/<int:doctor_id>')
def doctor_dashboard(doctor_id):
    # Verify doctor exists
    doctor = next((d for d in doctors_data if d.get('id') == doctor_id), None)
    if not doctor:
        flash("⛔ Doctor not found. Please login again.", "error")
        return redirect(url_for('doctor_login'))

    conn=None
    bookings_rows=[]
    stats=defaultdict(int) # Use defaultdict for easier counting
    appointments_per_day_data=defaultdict(int)
    unique_patients_set=set()

    try:
        conn=get_db()
        if not conn:
            flash('⛔ Database connection error. Could not load dashboard data.', 'error')
            # Render template with minimal data to avoid breaking
            return render_template('doctor_dashboard.html', doctor=doctor, doctor_id=doctor_id, bookings_by_month={}, stats={'total_bookings_listed': 0}, chart_config_daily={})

        c=conn.cursor()
        # Fetch bookings for this doctor, excluding cancelled ones, ordered reverse chronologically
        c.execute("""
            SELECT id, patient_name, patient_phone, booking_date, booking_time, notes, status
            FROM bookings
            WHERE doctor_id = ? AND status != 'Cancelled'
            ORDER BY booking_date DESC, booking_time DESC
        """, (doctor_id,))
        bookings_rows=c.fetchall() # Fetch all results

        # --- Calculate Statistics ---
        today_date=date.today()
        today_str=today_date.strftime('%Y-%m-%d')
        one_week_later = today_date + timedelta(days=7)
        current_month_start = today_date.replace(day=1) # Start of current month

        for row in bookings_rows:
            try:
                booking_dict=dict(row) # Convert row to dict for easier access
                dt_str = booking_dict['booking_date']
                status = booking_dict['status']
                dt_obj = datetime.strptime(dt_str,'%Y-%m-%d').date()

                # Increment various counters based on status and date
                if status == 'Pending' and dt_obj >= today_date:
                     stats['pending_upcoming_count'] += 1
                if dt_str == today_str:
                     stats['today_count'] += 1
                if today_date <= dt_obj < one_week_later: # includes today up to 6 days in future
                     stats['next_7_days_count'] += 1
                if status == 'Completed':
                    stats['completed_total_count'] += 1
                # Count appointments per day (for charts)
                appointments_per_day_data[dt_str] += 1

                # Count unique patients this month (using phone as primary identifier if available)
                if dt_obj >= current_month_start:
                    patient_id = booking_dict.get('patient_phone') or booking_dict.get('patient_name') # Use phone if available, else name
                    if patient_id: # Ensure we have an identifier
                        unique_patients_set.add(patient_id)

            except (ValueError, TypeError) as e:
                 # Log if a date string is invalid or status is unexpected
                 print(f"Warning: Could not process booking row ID {row.get('id')} for stats: {e}")

        # Final stat calculations
        stats['unique_patients_this_month'] = len(unique_patients_set)
        stats['total_bookings_listed'] = len(bookings_rows) # Total non-cancelled shown

    except sqlite3.Error as e:
        print(f"Database Error loading Doctor Dashboard for Dr {doctor_id}: {e}")
        flash('⛔ Database error loading booking data.', 'error')
        # Keep bookings_rows potentially empty or partially filled from before error
    finally:
        if conn: conn.close()

    # --- Prepare Chart Data (e.g., appointments for next 7 days) ---
    chart_labels=[]
    chart_data=[]
    chart_today=date.today()
    for i in range(7): # Generate labels/data for today + next 6 days
        d = chart_today + timedelta(days=i)
        d_str = d.strftime('%Y-%m-%d')
        chart_labels.append(d.strftime('%a, %b %d')) # Format: "Mon, Jan 15"
        chart_data.append(appointments_per_day_data[d_str]) # Get count for that day

    # --- Group Bookings by Month and Day for Display ---
    bookings_by_month = defaultdict(lambda: defaultdict(list)) # Nested defaultdict
    for row in bookings_rows:
        try:
            booking_dict = dict(row)
            booking_date_obj = datetime.strptime(booking_dict['booking_date'], '%Y-%m-%d')
            month_year_key = booking_date_obj.strftime('%B %Y') # e.g., "January 2024"
            date_key = booking_dict['booking_date'] # "YYYY-MM-DD"
            bookings_by_month[month_year_key][date_key].append(booking_dict)
        except (ValueError, TypeError) as e:
            print(f"Warning: Could not group booking row ID {row.get('id')} by date: {e}")

    # Sort months chronologically (most recent first)
    sorted_months = sorted(bookings_by_month.keys(), key=lambda my: datetime.strptime(my, '%B %Y'), reverse=True)
    # Create final structure with sorted months and sorted days within each month
    final_grouped_bookings = {
         month_key: dict(sorted(bookings_by_month[month_key].items(), reverse=True)) # Sort days DESC
         for month_key in sorted_months
    }

    return render_template(
        'doctor_dashboard.html',
        doctor=doctor,
        doctor_id=doctor_id,
        bookings_by_month=final_grouped_bookings, # Pass the sorted, grouped data
        stats=dict(stats), # Convert defaultdict to dict for template
        chart_config_daily={'labels': chart_labels, 'data': chart_data} # Pass chart data
    )

@app.route('/update-all-notes', methods=['POST'])
def update_all_notes():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Request must be JSON.'}), 400

    data = request.get_json()
    updates = data.get('updates', []) # Expect a list of {'bookingId': id, 'notes': text}

    if not isinstance(updates, list):
        return jsonify({'success': False, 'message': 'Invalid data format: "updates" must be a list.'}), 400

    conn = None
    updated_count = 0
    failed_ids = []
    try:
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error.'}), 500
        c = conn.cursor()

        for update in updates:
            booking_id = update.get('bookingId')
            notes = update.get('notes')

            # Basic validation for each item
            if isinstance(booking_id, (int, str)) and str(booking_id).isdigit() and isinstance(notes, str):
                try:
                    # Update notes for the given booking ID
                    c.execute("UPDATE bookings SET notes = ? WHERE id = ?", (notes.strip(), int(booking_id)))
                    # Check if the update actually changed a row (or found the row)
                    if c.rowcount >= 0: # rowcount is 0 if value is same, 1 if changed, -1 if error usually
                        updated_count += 1
                    else: # Should not happen with sqlite usually, but safety
                         failed_ids.append(booking_id)
                except sqlite3.Error as e:
                    print(f"Warning: Failed to update notes for booking ID {booking_id}: {e}")
                    failed_ids.append(booking_id)
            else:
                print(f"Warning: Skipping invalid update data: {update}")
                failed_ids.append(booking_id) # Log invalid format as failed

        conn.commit() # Commit all successful updates at once
        print(f"Notes update attempted: {len(updates)}. Successful: {updated_count}. Failed: {len(failed_ids)}.")

        success_status = not failed_ids # Overall success if no IDs failed
        message = f"{updated_count} notes saved successfully."
        if failed_ids:
            message += f" Failed to save notes for {len(failed_ids)} bookings."
            flash(message, 'warning')
        else:
            flash(message, 'success')

        return jsonify({'success': success_status, 'message': message})

    except sqlite3.Error as db_err:
        print(f"Database Error during bulk note update: {db_err}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {db_err}'}), 500
    except Exception as e:
        print(f"Unexpected Error during bulk note update: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'Internal server error: {e}'}), 500
    finally:
        if conn: conn.close()


@app.route('/mark-complete/<int:booking_id>', methods=['POST'])
def mark_complete(booking_id):
    conn=None
    try:
        conn=get_db()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error.'}), 500

        c=conn.cursor()
        # Update status to 'Completed' only if it's currently 'Pending'
        c.execute("UPDATE bookings SET status='Completed' WHERE id=? AND status='Pending'", (booking_id,))
        conn.commit()

        if c.rowcount > 0:
            # Successfully updated
            print(f"Booking ID {booking_id} marked as Completed.")
            return jsonify({'success': True, 'message': 'Appointment marked as completed.'})
        else:
            # No rows updated, check why
            c.execute("SELECT status FROM bookings WHERE id=?", (booking_id,))
            result = c.fetchone()
            if result:
                current_status = result['status']
                message = f'Appointment could not be marked complete. Current status: "{current_status}".'
                print(f"Failed to mark booking {booking_id} complete: Status is '{current_status}'")
                return jsonify({'success': False, 'message': message}), 409 # Conflict status code
            else:
                # Booking ID not found
                print(f"Failed to mark booking {booking_id} complete: Not found.")
                return jsonify({'success': False, 'message': 'Booking not found.'}), 404 # Not Found status code

    except sqlite3.Error as db_err:
        print(f"Database Error marking booking {booking_id} complete: {db_err}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {db_err}'}), 500
    except Exception as e:
        print(f"Unexpected Error marking booking {booking_id} complete: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'Internal server error: {e}'}), 500
    finally:
        if conn: conn.close()


@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        patient_identifier = request.form.get('patientIdentifier', '').strip()
        if not patient_identifier:
            flash('⛔ Please enter your Name or Phone Number used for booking.', 'error')
            return redirect(url_for('patient_login'))

        conn = None
        booking_exists = False
        try:
            conn = get_db()
            if not conn:
                flash('⛔ Database connection error. Please try again later.', 'error')
                return redirect(url_for('patient_login'))

            c = conn.cursor()
            # Check if any non-cancelled booking exists for this identifier (case-insensitive name)
            c.execute("""
                SELECT 1 FROM bookings
                WHERE (LOWER(patient_name) = LOWER(?) OR patient_phone = ?)
                  AND status != 'Cancelled'
                LIMIT 1
            """, (patient_identifier, patient_identifier))
            booking_exists = c.fetchone() is not None

        except sqlite3.Error as e:
            print(f"Database Error during patient login check: {e}")
            flash('⛔ Database error checking your bookings. Please try again.', 'error')
            return redirect(url_for('patient_login'))
        finally:
            if conn: conn.close()

        # If a booking exists, redirect to dashboard
        if booking_exists:
            print(f"Patient login successful for identifier: {patient_identifier}")
            # Pass the identifier securely (e.g., in URL for now, session later if needed)
            return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
        else:
            print(f"Patient login failed: No active bookings found for identifier: {patient_identifier}")
            flash('⛔ No active bookings found matching that Name or Phone Number.', 'error')
            return redirect(url_for('patient_login'))

    # If GET request, render the login page
    return render_template('patient_login.html')


@app.route('/patient-dashboard/<path:patient_identifier>')
def patient_dashboard(patient_identifier):
    if not patient_identifier:
        flash('⛔ Missing patient identifier. Please login again.', 'error')
        return redirect(url_for('patient_login'))

    conn=None
    bookings_rows=[]
    processed_bookings=[]
    db_error=False

    try:
        conn = get_db()
        if not conn:
            flash('⛔ Database connection error. Cannot load bookings.', 'error')
            db_error = True
        else:
            c = conn.cursor()
            # Fetch all non-cancelled bookings for this patient identifier (case-insensitive name)
            c.execute("""
                SELECT id, doctor_id, doctor_name, patient_name, patient_phone,
                       booking_date, booking_time, status, notes
                FROM bookings
                WHERE (LOWER(patient_name) = LOWER(?) OR patient_phone = ?)
                  AND status != 'Cancelled'
                ORDER BY booking_date DESC, booking_time DESC
            """, (patient_identifier, patient_identifier))
            bookings_rows = c.fetchall()

    except sqlite3.Error as e:
        print(f"Database Error loading Patient Dashboard for '{patient_identifier}': {e}")
        flash('⛔ Database error loading your bookings.', 'error')
        db_error = True
    finally:
        if conn: conn.close()

    # Process bookings to add flags like 'is_deletable'
    if not db_error and bookings_rows:
        now = datetime.now() # Get current time once
        for row in bookings_rows:
            booking_dict = dict(row)
            booking_dict['is_deletable'] = False # Default to not deletable

            if booking_dict.get('status') == 'Pending':
                try:
                    # Combine date and start time to check if it's in the future
                    date_str = booking_dict.get('booking_date')
                    time_slot = booking_dict.get('booking_time', '') # e.g., "09:00-09:30"
                    start_time_str = time_slot.split('-')[0].strip() # "09:00"

                    if date_str and start_time_str: # Ensure we have both parts
                        appointment_datetime_str = f"{date_str} {start_time_str}"
                        # Use consistent format for parsing
                        appointment_dt = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M')

                        # Allow deletion if the appointment start time is in the future
                        if appointment_dt > now:
                            booking_dict['is_deletable'] = True

                except (ValueError, IndexError, TypeError) as e:
                     # Log error if parsing fails, but don't crash the page
                     print(f"Warning: Could not parse date/time for cancellability check on booking ID {booking_dict.get('id')}: {e}")
                     # Keep is_deletable as False if parsing fails

            processed_bookings.append(booking_dict)

        if not processed_bookings: # If rows were fetched but processing failed somehow
            flash('ℹ️ No active bookings found for this identifier.', 'info')

    elif not db_error and not bookings_rows:
        flash('ℹ️ No active bookings found matching that Name or Phone Number.', 'info')


    return render_template(
        'patient_dashboard.html',
        bookings=processed_bookings, # Pass the processed list
        patient_identifier=patient_identifier,
        error=db_error # Pass error flag to template if needed
    )


# --- Run Application ---
if __name__ == '__main__':
    # Use environment variable for port, default to 5003 if not set
    port = int(os.environ.get("PORT", 5003))
    # Set debug=False for production/deployment
    # Use debug=True only for local development
    app.run(debug=True, host='0.0.0.0', port=port)