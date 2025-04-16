# Filename: app.py
from flask import (
    Flask, render_template, json, request, redirect, url_for,
    send_from_directory, flash, jsonify, make_response
)
import sqlite3
from flask_login import LoginManager, UserMixin, current_user # Assuming you might use login later
import os
from datetime import datetime, timedelta, date
import uuid
from collections import defaultdict # Helpful for aggregation
import json # Needed for handling JSON in DB

app = Flask(__name__, static_folder='static')

# Required for flash messages and sessions (if using Flask-Login)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key_123') # Use environment variable or secure key

# --- Login Manager Setup (Keep if using authentication) ---
login_manager = LoginManager()
login_manager.init_app(app)
# login_manager.login_view = 'login' # Example: redirect to login page if needed

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    # Replace with your actual user loading logic if using authentication
    if user_id:
         return User(user_id)
    return None # Important for anonymous users

# --- Database Initialization ---
def get_db():
    db_folder = 'database'
    db_path = os.path.join(db_folder, 'bookings.db')
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Return dict-like rows for easier access
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    db_folder = 'database'
    db_path = os.path.join(db_folder, 'bookings.db')
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)

    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        print("Initializing database...")

        # --- Create Bookings Table ---
        c.execute('''CREATE TABLE IF NOT EXISTS bookings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      doctor_id INTEGER NOT NULL,
                      doctor_name TEXT,
                      patient_name TEXT NOT NULL,
                      patient_phone TEXT,
                      booking_date TEXT NOT NULL,
                      booking_time TEXT NOT NULL,
                      notes TEXT,
                      appointment_type TEXT DEFAULT 'Consultation',
                      status TEXT DEFAULT 'Pending', -- Pending, Completed, Cancelled
                      ip_address TEXT,
                      cookie_id TEXT,
                      fingerprint TEXT,
                      user_id INTEGER,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY (doctor_id) REFERENCES doctors(id) -- Optional Foreign Key
                     )''')
        print("Bookings table checked/created.")

        # --- Create Doctors Table ---
        c.execute('''CREATE TABLE IF NOT EXISTS doctors
                    (id INTEGER PRIMARY KEY,
                     name TEXT NOT NULL,
                     availability1shortform TEXT,
                     province TEXT,
                     rate REAL, -- Use REAL for numbers
                     plc TEXT, -- Potentially clinic name
                     specialization TEXT,
                     photo TEXT,
                     description TEXT,
                     availability TEXT -- Store availability schedule as JSON string
                    )''')
        print("Doctors table checked/created.")

        # --- Populate Doctors Table (Only if empty) ---
        c.execute("SELECT COUNT(*) FROM doctors")
        doctor_count = c.fetchone()[0]
        if doctor_count == 0:
            print("Doctors table is empty. Populating with initial data...")
            initial_doctors = [
                 {
                    "id": 1, "name": "Dr. Aisha Khan", "availability1shortform": "Mon-Thu: 7am-8am, Sat-Sun: 8am-11am",
                    "province": "Bagmati", "rate": 4.5, "plc": "City Clinic", "specialization": "Dermatology",
                    "photo": "/static/doctors/doctor1.jpg", "description": "Expert in cosmetic and medical dermatology.",
                    "availability": json.dumps({
                        "Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"],
                        "Wednesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Thursday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"],
                        "Friday": ["Unavailable"],
                        "Saturday": ["08:00-08:20", "08:20-08:40", "08:40-09:00", "09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"],
                        "Sunday": ["08:00-08:20", "08:20-08:40", "08:40-09:00"]
                    })
                },
                {
                    "id": 2, "name": "Dr. Binod Sharma", "availability1shortform": "Mon-Wed: 7am-8am, Sat: 8am-11am, Sun: 8am-9am",
                    "province": "Gandaki", "rate": 4.2, "plc": "Lakeview Hospital", "specialization": "Cardiology",
                    "photo": "/static/doctors/doctor3.jpg", "description": "Specializing in preventative cardiology and heart health.",
                    "availability": json.dumps({
                        "Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"],
                        "Wednesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Thursday": ["Unavailable"], "Friday": ["Unavailable"],
                        "Saturday": ["08:00-08:20", "08:20-08:40", "08:40-09:00", "09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"],
                        "Sunday": ["08:00-08:20", "08:20-08:40", "08:40-09:00"]
                    })
                },
                {
                    "id": 3, "name": "Dr. Chitra Gurung", "availability1shortform": "Mon-Tue: 7am-8am, Sat-Sun: 9am-12pm",
                    "province": "Lumbini", "rate": 4.8, "plc": "Peace Clinic", "specialization": "Pediatrics",
                    "photo": "/static/doctors/doctor4.jpg", "description": "Dedicated pediatric care for infants, children, and adolescents.",
                    "availability": json.dumps({
                        "Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"],
                        "Wednesday": ["Unavailable"], "Thursday": ["Unavailable"], "Friday": ["Unavailable"],
                        "Saturday": ["09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20", "11:20-11:40", "11:40-12:00"],
                        "Sunday": ["09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"]
                    })
                },
                {
                    "id": 4, "name": "Dr. David Rai", "availability1shortform": "Mon-Tue: 9am-10:30am, Fri-Sun: 11am-12:30pm",
                    "province": "Province 1", "rate": 4.0, "plc": "Mountain View Clinic", "specialization": "Orthopedics",
                    "photo": "/static/doctors/doctor2.jpg", "description": "Board-certified orthopedic surgeon with 10+ years experience.",
                    "availability": json.dumps({
                        "Monday": ["09:00-09:30", "09:30-10:00", "10:00-10:30"], "Tuesday": ["09:00-09:30", "09:30-10:00", "10:00-10:30"],
                        "Wednesday": ["Unavailable"], "Thursday": ["Unavailable"],
                        "Friday": ["11:00-11:30", "11:30-12:00", "12:00-12:30"], "Saturday": ["11:00-11:30", "11:30-12:00", "12:00-12:30"],
                        "Sunday": ["11:00-11:30", "11:30-12:00", "12:00-12:30"]
                    })
                },
                 {
                    "id": 5, "name": "Dr. Elina Maharjan", "availability1shortform": "Wed-Fri: 10am-12pm, Sat: 1pm-3pm",
                    "province": "Bagmati", "rate": 4.6, "plc": "Central Health Hub", "specialization": "General Physician",
                    "photo": "/static/doctors/doctor5.jpg", "description": "Comprehensive primary care for all ages.",
                    "availability": json.dumps({
                        "Monday": ["Unavailable"], "Tuesday": ["Unavailable"],
                        "Wednesday": ["10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20", "11:20-11:40", "11:40-12:00"],
                        "Thursday": ["10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20"],
                        "Friday": ["10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20", "11:20-11:40", "11:40-12:00"],
                        "Saturday": ["13:00-13:30", "13:30-14:00", "14:00-14:30", "14:30-15:00"],
                        "Sunday": ["Unavailable"]
                    })
                },
                {
                    "id": 6, "name": "Dr. Farhan Ansari", "availability1shortform": "Mon, Wed, Fri: 2pm-4pm",
                    "province": "Province 2", "rate": 4.1, "plc": "Terai Care Center", "specialization": "Neurology",
                    "photo": "/static/doctors/doctor6.jpg", "description": "Expertise in neurological disorders and treatments.",
                    "availability": json.dumps({
                        "Monday": ["14:00-14:30", "14:30-15:00", "15:00-15:30", "15:30-16:00"],
                        "Tuesday": ["Unavailable"],
                        "Wednesday": ["14:00-14:30", "14:30-15:00", "15:00-15:30", "15:30-16:00"],
                        "Thursday": ["Unavailable"],
                        "Friday": ["14:00-14:30", "14:30-15:00", "15:00-15:30", "15:30-16:00"],
                        "Saturday": ["Unavailable"], "Sunday": ["Unavailable"]
                    })
                },
                 {
                    "id": 7, "name": "Dr. Gita Pandey", "availability1shortform": "Tue, Thu: 9am-11am, Sat: 10am-1pm",
                    "province": "Gandaki", "rate": 4.7, "plc": "Himalayan Clinic", "specialization": "Dermatology",
                    "photo": "/static/doctors/doctor7.jpg", "description": "Advanced skincare solutions and treatments.",
                    "availability": json.dumps({
                        "Monday": ["Unavailable"],
                        "Tuesday": ["09:00-09:30", "09:30-10:00", "10:00-10:30", "10:30-11:00"],
                        "Wednesday": ["Unavailable"],
                        "Thursday": ["09:00-09:30", "09:30-10:00", "10:00-10:30", "10:30-11:00"],
                        "Friday": ["Unavailable"],
                        "Saturday": ["10:00-10:30", "10:30-11:00", "11:00-11:30", "11:30-12:00", "12:00-12:30", "12:30-13:00"],
                        "Sunday": ["Unavailable"]
                    })
                },
                {
                    "id": 8, "name": "Dr. Hari Joshi", "availability1shortform": "Mon-Fri: 8am-10am",
                    "province": "Sudurpashchim", "rate": 3.9, "plc": "Western Regional Clinic", "specialization": "General Physician",
                    "photo": "/static/doctors/doctor8.jpg", "description": "Providing general health check-ups and consultations.",
                     "availability": json.dumps({
                        "Monday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"],
                        "Tuesday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"],
                        "Wednesday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"],
                        "Thursday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"],
                        "Friday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"],
                        "Saturday": ["Unavailable"], "Sunday": ["Unavailable"]
                     })
                },
                {
                    "id": 9, "name": "Dr. Ishani Thapa", "availability1shortform": "Sat-Sun: 3pm-5pm",
                    "province": "Lumbini", "rate": 4.3, "plc": "Community Health Post", "specialization": "Pediatrics",
                    "photo": "/static/doctors/doctor9.jpg", "description": "Weekend pediatric clinic.",
                    "availability": json.dumps({
                         "Monday": ["Unavailable"], "Tuesday": ["Unavailable"], "Wednesday": ["Unavailable"],
                         "Thursday": ["Unavailable"], "Friday": ["Unavailable"],
                         "Saturday": ["15:00-15:20", "15:20-15:40", "15:40-16:00", "16:00-16:20", "16:20-16:40", "16:40-17:00"],
                         "Sunday": ["15:00-15:20", "15:20-15:40", "15:40-16:00", "16:00-16:20", "16:20-16:40", "16:40-17:00"]
                    })
                },
                {
                    "id": 10, "name": "Dr. Jamal Malik", "availability1shortform": "Tue, Thu: 5pm-7pm",
                    "province": "Province 1", "rate": 4.4, "plc": "Eastern Care Hospital", "specialization": "Cardiology",
                    "photo": "/static/doctors/doctor10.jpg", "description": "Evening cardiology consultations available.",
                    "availability": json.dumps({
                        "Monday": ["Unavailable"],
                        "Tuesday": ["17:00-17:30", "17:30-18:00", "18:00-18:30", "18:30-19:00"],
                        "Wednesday": ["Unavailable"],
                        "Thursday": ["17:00-17:30", "17:30-18:00", "18:00-18:30", "18:30-19:00"],
                        "Friday": ["Unavailable"], "Saturday": ["Unavailable"], "Sunday": ["Unavailable"]
                    })
                }
                # Add more doctors if needed following the same structure
            ]
            c.executemany('''INSERT INTO doctors (id, name, availability1shortform, province, rate, plc, specialization, photo, description, availability)
                             VALUES (:id, :name, :availability1shortform, :province, :rate, :plc, :specialization, :photo, :description, :availability)''',
                          initial_doctors)
            print(f"Inserted {len(initial_doctors)} doctors into the database.")
        else:
            print("Doctors table already populated.")

        # --- Column Checks for Bookings (Keep as before) ---
        table_info = c.execute("PRAGMA table_info(bookings)").fetchall()
        column_names = [col[1] for col in table_info]
        if 'appointment_type' not in column_names:
            print("Adding 'appointment_type' column...")
            c.execute("ALTER TABLE bookings ADD COLUMN appointment_type TEXT DEFAULT 'Consultation'")
            print("'appointment_type' column added.")
        if 'status' not in column_names:
            print("Adding 'status' column...")
            c.execute("ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'Pending'")
            print("'status' column added.")
        # --- End Column Check ---

        conn.commit()
        print("Database initialization complete.")

    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
        if conn:
            conn.rollback() # Rollback changes if error occurs
    finally:
        if conn:
            conn.close()


# --- Load doctors data FROM DATABASE ---
def load_doctors_from_db():
    """Fetches all doctors from the database and parses availability JSON."""
    conn = get_db()
    if not conn:
        print("CRITICAL: Database connection failed in load_doctors_from_db.")
        return [] # Return empty list if DB connection fails

    doctors_list = []
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM doctors ORDER BY name ASC") # Optional: Order doctors by name
        doctors_rows = c.fetchall()
        for row in doctors_rows:
            if row is None: continue # Skip if row is None for any reason
            try:
                doctor_dict = dict(row)
                # Parse the availability JSON string into a Python dict
                if 'availability' in doctor_dict and doctor_dict['availability']:
                     doctor_dict['availability'] = json.loads(doctor_dict['availability'])
                else:
                     doctor_dict['availability'] = {} # Default to empty dict if null/empty
                doctors_list.append(doctor_dict)
            except (json.JSONDecodeError, TypeError) as json_err:
                print(f"Warning: Could not parse availability JSON for doctor ID {row['id'] if row else 'N/A'}: {json_err}")
                # Still add doctor but with empty availability
                doctor_dict = dict(row)
                doctor_dict['availability'] = {}
                doctors_list.append(doctor_dict)


    except sqlite3.Error as e:
        print(f"Error fetching doctors from DB: {e}")
        return [] # Return empty on DB error
    finally:
        if conn:
            conn.close()

    print(f"Loaded {len(doctors_list)} doctors from database.")
    return doctors_list

# --- Initialize DB and Load Data ---
init_db() # Run initialization
doctors_data = load_doctors_from_db() # Load doctors from DB into global variable
if not doctors_data:
     print("CRITICAL WARNING: Failed to load doctor data from database. Doctor list will be empty.")


# --- Standard Routes (Home, Booking Page, Confirmation etc.) ---

@app.route('/')
def home():
    # Initialize stats and specialties with defaults FIRST
    stats = {
        'doctor_count': len(doctors_data), # Basic count from loaded data as fallback
        'specialty_count': 0,
        'completed_bookings': 0,
        'total_active_bookings': 0
    }
    specialties = []
    # Pre-calculate specialty count and list from loaded data as a fallback
    if doctors_data:
         unique_specs = {d['specialization'] for d in doctors_data if d.get('specialization')}
         stats['specialty_count'] = len(unique_specs)
         specialties = sorted(list(unique_specs))

    # Try fetching more accurate stats from DB
    conn = get_db()
    if not conn:
        print("Warning: DB connection failed in home route. Using basic stats.")
        flash('Warning: Could not load latest statistics.', 'info')
        # Return with basic stats calculated above
        return render_template('index.html', doctors=doctors_data, stats=stats, specialties=specialties)

    # --- Database connection successful, proceed with queries ---
    c = conn.cursor()
    try:
        # Fetch Accurate Doctor Count from DB
        c.execute("SELECT COUNT(*) FROM doctors")
        db_doctor_count = c.fetchone()
        if db_doctor_count: stats['doctor_count'] = db_doctor_count[0]

        # Fetch Accurate Specialty Count from DB
        c.execute("SELECT COUNT(DISTINCT specialization) FROM doctors WHERE specialization IS NOT NULL AND specialization != ''")
        db_specialty_count = c.fetchone()
        # Only update specialty count if DB provides a value, otherwise keep the calculated one
        if db_specialty_count and db_specialty_count[0] is not None : stats['specialty_count'] = db_specialty_count[0]

        # Fetch Booking Stats from DB
        c.execute("SELECT COUNT(*) FROM bookings WHERE status = 'Completed'")
        completed_count = c.fetchone()
        if completed_count: stats['completed_bookings'] = completed_count[0]

        c.execute("SELECT COUNT(*) FROM bookings WHERE status != 'Cancelled'")
        active_count = c.fetchone()
        if active_count: stats['total_active_bookings'] = active_count[0]

        # Fetch Distinct Specialties for Filtering - Overwrite the fallback list if successful
        c.execute("SELECT DISTINCT specialization FROM doctors WHERE specialization IS NOT NULL AND specialization != '' ORDER BY specialization ASC")
        specialties_rows = c.fetchall()
        specialties = [row['specialization'] for row in specialties_rows] # Overwrite fallback list

    except sqlite3.Error as e:
        print(f"Error fetching stats/specialties from DB: {e}")
        flash('Could not load page statistics due to a database error.', 'error')
        # If DB fails mid-query, the stats dict might be partially updated.
        # The specialties list will be the fallback calculated earlier unless overwritten by the query.

    finally:
        if conn:
            conn.close()

    # *** Add print statement for debugging ***
    print(f"DEBUG: Stats passed to index.html: {stats}")
    print(f"DEBUG: Specialties passed to index.html: {specialties}")

    # Pass doctors_data (loaded from DB) and the fetched/default stats/specialties
    return render_template('index.html', doctors=doctors_data, stats=stats, specialties=specialties)

# --- Other routes remain the same as provided in the previous answer ---
# (booking_page, get_available_slots, confirm_booking, confirmation,
#  get_doctor_availability, delete_booking, doctor_login, doctor_dashboard,
#  update_all_notes, mark_complete, patient_login, patient_dashboard)

@app.route('/booking/<int:doctor_id>')
def booking_page(doctor_id):
    try:
        doctor = next((d for d in doctors_data if d['id'] == doctor_id), None)
        if not doctor:
             flash('Doctor not found.', 'error')
             return redirect(url_for('home'))

        today_str = date.today().strftime('%Y-%m-%d')
        doctor_availability_json = json.dumps(doctor.get('availability', {}))

        response = make_response(render_template(
            'booking.html',
            doctor=doctor,
            doctor_id=doctor_id,
            today=today_str,
            doctor_availability_schedule=doctor_availability_json
        ))

        if not request.cookies.get('device_id'):
            device_id = str(uuid.uuid4())
            response.set_cookie('device_id', device_id, max_age=30*24*60*60, httponly=True, samesite='Lax')

        return response

    except Exception as e:
        print(f"Error in booking_page for doctor {doctor_id}: {e}")
        flash('An error occurred. Please try again later.', 'error')
        return redirect(url_for('home'))

@app.route('/get-available-slots/<int:doctor_id>/<string:date_str>')
def get_available_slots(doctor_id, date_str):
    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = booking_date.strftime('%A')

        doctor = next((d for d in doctors_data if d['id'] == doctor_id), None)
        if not doctor:
            return jsonify({'error': 'Doctor not found'}), 404

        doctor_availability = doctor.get('availability', {})
        general_slots_raw = doctor_availability.get(day_name, [])
        general_slots = [slot for slot in general_slots_raw if isinstance(slot, str) and slot.lower() != "unavailable"]

        if not general_slots:
             return jsonify([])

        conn = get_db()
        if not conn: return jsonify({'error': 'Database connection error'}), 500
        booked_times = set()
        try:
            c = conn.cursor()
            c.execute('''SELECT booking_time FROM bookings
                         WHERE doctor_id = ? AND booking_date = ? AND status != 'Cancelled' ''',
                      (doctor_id, date_str))
            booked_slots_rows = c.fetchall()
            booked_times = {row['booking_time'] for row in booked_slots_rows}
        except sqlite3.Error as e:
            print(f"DB error fetching slots: {e}")
            return jsonify({'error': 'Database error fetching slots'}), 500
        finally:
            if conn: conn.close()

        available_slots = [slot for slot in general_slots if slot not in booked_times]
        return jsonify(available_slots)

    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    except Exception as e:
        print(f"Error in get_available_slots for doctor {doctor_id}, date {date_str}: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    # (Code from previous answer - unchanged)
    doctor_id_str = request.form.get('doctor_id')
    doctor_name = request.form.get('doctor_name')
    patient_name = request.form.get('patient_name')
    patient_phone = request.form.get('patient_phone')
    booking_date = request.form.get('booking_date')
    booking_time = request.form.get('booking_time')
    notes = request.form.get('notes', '').strip()

    if not all([doctor_id_str, doctor_name, patient_name, patient_phone, booking_date, booking_time]):
         flash('⛔ Missing required booking information.', 'error')
         return redirect(request.referrer or url_for('home'))
    try:
        doctor_id = int(doctor_id_str)
    except ValueError:
        flash('⛔ Invalid Doctor ID.', 'error')
        return redirect(url_for('home'))

    doctor = next((d for d in doctors_data if d['id'] == doctor_id), None)
    if not doctor:
        flash('⛔ Doctor not found.', 'error')
        return redirect(url_for('home'))

    try:
        selected_day = datetime.strptime(booking_date, '%Y-%m-%d').strftime('%A')
    except ValueError:
        flash('⛔ Invalid date format.', 'error')
        return redirect(url_for('booking_page', doctor_id=doctor_id))

    conn = get_db()
    if not conn:
        flash('⛔ Database error. Please try again.', 'error')
        return redirect(url_for('booking_page', doctor_id=doctor_id))

    c = conn.cursor()
    booking_id = None
    try:
        today = date.today().strftime('%Y-%m-%d')
        if booking_date < today:
            flash('⛔ You cannot book on a date before today.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        doctor_schedule = doctor.get('availability', {})
        day_schedule = doctor_schedule.get(selected_day, [])
        if not day_schedule or (len(day_schedule) == 1 and day_schedule[0].lower() == 'unavailable'):
            flash(f'⛔ Doctor is generally unavailable on {selected_day}s.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        c.execute('''SELECT 1 FROM bookings
                     WHERE patient_name = ? AND doctor_id = ? AND status != 'Cancelled'
                     AND DATE(booking_date) >= DATE(?, '-5 days') AND DATE(booking_date) <= DATE(?, '+5 days') LIMIT 1''',
                  (patient_name, doctor_id, booking_date, booking_date))
        if c.fetchone():
            flash('⛔ You have a recent booking with this doctor. One booking per 5 days allowed.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        c.execute('''SELECT 1 FROM bookings
                     WHERE doctor_id = ? AND booking_date = ? AND booking_time = ? AND status != 'Cancelled' LIMIT 1''',
                  (doctor_id, booking_date, booking_time))
        if c.fetchone():
            flash('⛔ This time slot is already booked. Please choose another time.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        c.execute('''SELECT 1 FROM bookings
                     WHERE (patient_name = ? OR patient_phone = ?) AND booking_date = ? AND status != 'Cancelled' LIMIT 1''',
                  (patient_name, patient_phone, booking_date))
        if c.fetchone():
            flash('⛔ You already have a booking on this day. Only one booking per day is allowed.', 'error')
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        c.execute('''INSERT INTO bookings
                     (doctor_id, doctor_name, patient_name, patient_phone, booking_date, booking_time, notes, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')''',
                  (doctor_id, doctor_name, patient_name, patient_phone, booking_date, booking_time, notes))
        conn.commit()
        booking_id = c.lastrowid

    except sqlite3.Error as e:
        print(f"Database error during booking confirmation: {e}")
        flash('⛔ A database error occurred. Please try again.', 'error')
        if conn: conn.rollback()
        return redirect(url_for('booking_page', doctor_id=doctor_id))
    except Exception as e:
         print(f"Error during booking confirmation: {e}")
         flash('⛔ An unexpected error occurred. Please try again.', 'error')
         if conn: conn.rollback()
         return redirect(url_for('booking_page', doctor_id=doctor_id))
    finally:
        if conn: conn.close()

    if booking_id:
        flash('✅ Booking confirmed successfully!', 'success')
        return redirect(url_for('confirmation',
                              booking_id=booking_id,
                              doctor_name=doctor_name,
                              patient_name=patient_name,
                              booking_date=booking_date,
                              booking_time=booking_time))
    else:
        flash('⛔ Booking could not be confirmed.', 'error')
        return redirect(url_for('booking_page', doctor_id=doctor_id))

@app.route('/confirmation')
def confirmation():
    # (Code from previous answer - unchanged)
    booking_id = request.args.get('booking_id')
    if not booking_id:
        flash('Invalid confirmation link.', 'error')
        return redirect(url_for('home'))
    return render_template('confirmation.html',
                         booking_id=booking_id,
                         doctor_name=request.args.get('doctor_name'),
                         patient_name=request.args.get('patient_name'),
                         booking_date=request.args.get('booking_date'),
                         booking_time=request.args.get('booking_time'))

@app.route('/get-doctor-availability/<int:doctor_id>')
def get_doctor_availability(doctor_id):
    # (Code from previous answer - unchanged)
    try:
        doctor = next((d for d in doctors_data if d['id'] == doctor_id), None)
        if not doctor:
            return jsonify({'error': 'Doctor not found'}), 404
        doctor_schedule = doctor.get('availability', {})
        if not doctor_schedule: return jsonify({})
        availability_data = defaultdict(list)
        today_dt = date.today()
        end_date = today_dt + timedelta(days=120)
        current_date_loop = today_dt
        while current_date_loop <= end_date:
            day_name = current_date_loop.strftime('%A')
            general_slots_raw = doctor_schedule.get(day_name, [])
            has_general_slots = any(
                isinstance(slot, str) and slot.strip() and slot.lower() != "unavailable"
                for slot in general_slots_raw)
            if has_general_slots:
                month_str = current_date_loop.strftime('%Y-%m')
                day_num = current_date_loop.day
                availability_data[month_str].append(day_num)
            current_date_loop += timedelta(days=1)
        return jsonify(dict(availability_data))
    except Exception as e:
        print(f"Error in get_doctor_availability for doctor {doctor_id}: {e}")
        return jsonify({'error': 'An internal error occurred fetching availability'}), 500

@app.route('/delete-booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    # (Code from previous answer - unchanged)
    conn = get_db()
    if not conn:
        flash('⛔ Database connection error.', 'error')
        return redirect(request.referrer or url_for('home'))
    c = conn.cursor()
    updated = False
    try:
        c.execute("UPDATE bookings SET status = 'Cancelled' WHERE id = ? AND status != 'Cancelled'", (booking_id,))
        conn.commit()
        if c.rowcount > 0:
            flash('✅ Booking successfully cancelled.', 'success')
            updated = True
        else:
            c.execute('SELECT 1 FROM bookings WHERE id = ?', (booking_id,))
            exists = c.fetchone()
            if not exists: flash('⛔ Booking not found.', 'error')
            else: flash('ℹ️ Booking was already cancelled or could not be updated.', 'info')
    except sqlite3.Error as e:
        print(f"Database error cancelling booking {booking_id}: {e}")
        flash('⛔ Database error during cancellation.', 'error')
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

    source = request.form.get('source', 'home')
    patient_identifier = request.form.get('patient_identifier')
    doctor_id = request.form.get('doctor_id')

    if source == 'confirmation' or source == 'home': return redirect(url_for('home'))
    elif source == 'patient_dashboard' and patient_identifier: return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
    elif source == 'doctor_dashboard' and doctor_id:
        try: return redirect(url_for('doctor_dashboard', doctor_id=int(doctor_id)))
        except (ValueError, TypeError): return redirect(url_for('doctor_login'))
    else: return redirect(url_for('home'))

@app.route('/doctor-login', methods=['GET', 'POST'])
def doctor_login():
    # (Code from previous answer - unchanged)
    if request.method == 'POST':
        doctor_name = request.form.get('doctorName', '').strip()
        doctor_id_str = request.form.get('doctorId', '').strip()
        if not doctor_name or not doctor_id_str or not doctor_id_str.isdigit():
             flash('⛔ Please enter both Doctor Name and a valid ID.', 'error')
             return redirect(url_for('doctor_login'))
        doctor_id = int(doctor_id_str)
        doctor = next((d for d in doctors_data if d['name'] == doctor_name and d['id'] == doctor_id), None)
        if doctor:
            print(f"Doctor login successful: ID {doctor_id}, Name {doctor_name}")
            return redirect(url_for('doctor_dashboard', doctor_id=doctor_id))
        else:
            flash('⛔ Invalid doctor name or ID.', 'error')
            print(f"Doctor login failed: ID {doctor_id_str}, Name {doctor_name}")
            return redirect(url_for('doctor_login'))
    return render_template('doctor_login.html')

@app.route('/doctor-dashboard/<int:doctor_id>')
def doctor_dashboard(doctor_id):
    # (Code from previous answer - unchanged)
    conn = get_db()
    if not conn:
         flash('Database connection error.', 'error')
         return render_template('doctor_dashboard.html', doctor_id=doctor_id, bookings_by_month={}, stats={}, chart_config_daily={})
    c = conn.cursor()
    bookings_rows = []
    try:
        c.execute('''SELECT id, doctor_id, doctor_name, patient_name, patient_phone,
                            booking_date, booking_time, notes, status
                     FROM bookings
                     WHERE doctor_id = ? AND status != 'Cancelled'
                     ORDER BY booking_date ASC, booking_time ASC''', (doctor_id,))
        bookings_rows = c.fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching bookings for doctor {doctor_id}: {e}")
        flash('Could not load booking data.', 'error')
    finally:
        if conn: conn.close()

    stats = defaultdict(int)
    appointments_per_day_data = defaultdict(int)
    unique_patients_set = set()
    today_date = date.today(); today_str = today_date.strftime('%Y-%m-%d')
    one_week_later = today_date + timedelta(days=7); current_month_str = today_date.strftime('%Y-%m')
    for booking in bookings_rows:
        try:
            booking_dict = dict(booking); booking_date_obj = datetime.strptime(booking_dict['booking_date'], '%Y-%m-%d').date()
            booking_date_str_loop = booking_dict['booking_date']; booking_status = booking_dict['status']
            if booking_date_obj >= today_date and booking_status == 'Pending':
                if booking_date_str_loop == today_str: stats['today_count'] += 1
                if today_date <= booking_date_obj < one_week_later: stats['week_count'] += 1
                stats['pending_count'] += 1
                if today_date <= booking_date_obj < one_week_later: appointments_per_day_data[booking_date_str_loop] += 1
                if booking_date_str_loop.startswith(current_month_str):
                     patient_identifier = booking_dict['patient_name'] or booking_dict.get('patient_phone')
                     if patient_identifier: unique_patients_set.add(patient_identifier)
        except (ValueError, KeyError, TypeError, AttributeError) as e: print(f"Warning: Skipping booking stat processing: {dict(booking)} - Error: {e}"); continue
    stats['unique_patients_this_month'] = len(unique_patients_set)
    chart_labels_daily = []; chart_data_daily = []
    for i in range(7):
        d = today_date + timedelta(days=i); d_str = d.strftime('%Y-%m-%d')
        chart_labels_daily.append(d.strftime('%a, %b %d')); chart_data_daily.append(appointments_per_day_data[d_str])
    bookings_by_month = defaultdict(lambda: defaultdict(list))
    for booking in bookings_rows:
        try:
            booking_dict = dict(booking); booking_date_dt = datetime.strptime(booking_dict['booking_date'], '%Y-%m-%d')
            month_year = booking_date_dt.strftime('%B %Y'); day = booking_date_dt.strftime('%Y-%m-%d')
            bookings_by_month[month_year][day].append(booking_dict)
        except (ValueError, KeyError, TypeError, AttributeError) as e: print(f"Warning: Skipping booking display grouping: {dict(booking)} - Error: {e}"); continue
    final_bookings_by_month = {my: dict(days) for my, days in bookings_by_month.items()}
    return render_template(
        'doctor_dashboard.html', doctor_id=doctor_id, bookings_by_month=final_bookings_by_month,
        stats=dict(stats), chart_config_daily={'labels': chart_labels_daily, 'data': chart_data_daily})

@app.route('/update-all-notes', methods=['POST'])
def update_all_notes():
    # (Code from previous answer - unchanged)
    if not request.is_json: return jsonify({'success': False, 'message': 'Invalid request format, expected JSON.'}), 400
    data = request.get_json(); updates = data.get('updates', [])
    if not isinstance(updates, list): return jsonify({'success': False, 'message': 'Invalid data format, "updates" should be a list.'}), 400
    conn = None
    try:
        conn = get_db();
        if not conn: return jsonify({'success': False, 'message': 'Database connection error.'}), 500
        c = conn.cursor(); updated_count = 0
        for update in updates:
            booking_id = update.get('bookingId'); notes = update.get('notes')
            if isinstance(booking_id, (int, str)) and str(booking_id).isdigit() and isinstance(notes, str):
                c.execute('''UPDATE bookings SET notes = ? WHERE id = ?''', (notes.strip(), int(booking_id)))
                if c.rowcount > 0: updated_count += 1
            else: print(f"Warning: Skipping invalid update data: {update}")
        conn.commit(); print(f"Updated notes for {updated_count} bookings.")
        return jsonify({'success': True, 'message': f'{updated_count} notes updated successfully!'})
    except sqlite3.Error as db_err:
        print(f"Database error updating notes: {db_err}");
        if conn: conn.rollback(); return jsonify({'success': False, 'message': f'Database error: {db_err}'}), 500
    except Exception as e:
        print(f"Error processing /update-all-notes: {e}");
        if conn: conn.rollback(); return jsonify({'success': False, 'message': f'An internal error occurred: {e}'}), 500
    finally:
        if conn: conn.close()

@app.route('/mark-complete/<int:booking_id>', methods=['POST'])
def mark_complete(booking_id):
    # (Code from previous answer - unchanged)
    conn = None
    try:
        conn = get_db();
        if not conn: return jsonify({'success': False, 'message': 'Database connection error.'}), 500
        c = conn.cursor()
        c.execute("UPDATE bookings SET status = 'Completed' WHERE id = ? AND status = 'Pending'", (booking_id,))
        conn.commit()
        if c.rowcount > 0:
            print(f"Marked booking {booking_id} as completed."); return jsonify({'success': True, 'message': 'Booking marked as completed.'})
        else:
             c.execute("SELECT status FROM bookings WHERE id = ?", (booking_id,)); result = c.fetchone()
             if result and result['status'] == 'Completed': message = 'Booking already marked as completed.'
             elif result: message = f'Booking status is {result["status"]}, cannot mark as completed.'
             else: message = 'Booking not found.'
             print(f"Failed to mark booking {booking_id} as completed: {message}"); return jsonify({'success': False, 'message': message}), 400
    except sqlite3.Error as db_err:
        print(f"Database error marking booking {booking_id} complete: {db_err}");
        if conn: conn.rollback(); return jsonify({'success': False, 'message': f'Database error: {db_err}'}), 500
    except Exception as e:
        print(f"Error processing /mark-complete/{booking_id}: {e}");
        if conn: conn.rollback(); return jsonify({'success': False, 'message': f'An internal error occurred: {e}'}), 500
    finally:
        if conn: conn.close()

@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    # (Code from previous answer - unchanged)
    if request.method == 'POST':
        patient_identifier = request.form.get('patientIdentifier', '').strip()
        if not patient_identifier:
            flash('⛔ Please enter your name or phone number.', 'error'); return redirect(url_for('patient_login'))
        conn = get_db();
        if not conn: flash('Database connection error.', 'error'); return redirect(url_for('patient_login'))
        c = conn.cursor(); booking_exists = False
        try:
            c.execute('''SELECT 1 FROM bookings
                         WHERE (patient_name = ? OR patient_phone = ?) AND status != 'Cancelled' LIMIT 1''',
                      (patient_identifier, patient_identifier))
            booking_exists = c.fetchone()
        except sqlite3.Error as e:
            print(f"DB error during patient login check: {e}"); flash('Database error checking bookings.', 'error')
        finally:
            if conn: conn.close()
        if booking_exists: return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
        else: flash('⛔ No active bookings found for this name or phone number.', 'error'); return redirect(url_for('patient_login'))
    return render_template('patient_login.html')

@app.route('/patient-dashboard/<path:patient_identifier>')
def patient_dashboard(patient_identifier):
    # (Code from previous answer - unchanged)
    if not patient_identifier: flash('Missing patient identifier.', 'error'); return redirect(url_for('patient_login'))
    conn = get_db()
    if not conn: flash('Database connection error.', 'error'); return render_template('patient_dashboard.html', bookings=[], patient_identifier=patient_identifier)
    c = conn.cursor(); bookings_rows = []
    try:
        c.execute('''SELECT id, doctor_name, patient_name, booking_date, booking_time, status, notes
                     FROM bookings WHERE (patient_name = ? OR patient_phone = ?) AND status != 'Cancelled'
                     ORDER BY booking_date DESC, booking_time DESC''', (patient_identifier, patient_identifier))
        bookings_rows = c.fetchall()
    except sqlite3.Error as e: print(f"DB error fetching patient bookings: {e}"); flash('Could not load your bookings.', 'error')
    finally: if conn: conn.close()
    bookings = []; current_dt_obj = datetime.now()
    for row in bookings_rows:
        booking_dict = dict(row); is_deletable = False
        try:
            time_part = booking_dict['booking_time'].split('-')[0].strip()
            possible_formats = ["%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M%p", "%Y-%m-%d %I:%M %p"]
            booking_dt_obj = None
            for fmt in possible_formats:
                try: full_datetime_str = f"{booking_dict['booking_date']} {time_part}"; booking_dt_obj = datetime.strptime(full_datetime_str, fmt); break
                except ValueError: continue
            if booking_dt_obj and booking_dt_obj > current_dt_obj: is_deletable = True
        except Exception as e: print(f"Warning: Could not parse datetime for patient booking ID {booking_dict.get('id')}: {e}")
        booking_dict['is_deletable'] = is_deletable
        bookings.append(booking_dict)
    return render_template('patient_dashboard.html', bookings=bookings, patient_identifier=patient_identifier)


# --- Run Application ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    # Set debug=False in production
    # Use host='0.0.0.0' to make accessible on local network
    app.run(debug=True, host='0.0.0.0', port=port)