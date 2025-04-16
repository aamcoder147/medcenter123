# Filename: app.py
# ****** MODIFIED CODE ******
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
    # For now, returns a placeholder user if an ID is provided
    if user_id:
         return User(user_id)
    return None # Important for anonymous users

# --- Database Initialization ---
def get_db():
    db_folder = 'database'
    db_path = os.path.join(db_folder, 'bookings.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # Return dict-like rows for easier access
    return conn

def init_db():
    db_folder = 'database'
    db_path = os.path.join(db_folder, 'bookings.db')
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)

    # Use get_db() to ensure row_factory is set if needed elsewhere too
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    print("Initializing database...")

    # Create Bookings Table (Keep status, keep type for potential future use but don't query for dashboard)
    c.execute('''CREATE TABLE IF NOT EXISTS bookings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  doctor_id INTEGER NOT NULL,
                  doctor_name TEXT,
                  patient_name TEXT NOT NULL,
                  patient_phone TEXT,
                  booking_date TEXT NOT NULL,
                  booking_time TEXT NOT NULL,
                  notes TEXT,
                  appointment_type TEXT DEFAULT 'Consultation', -- Keeping column, but won't be used in dashboard charts
                  status TEXT DEFAULT 'Pending',               -- Status: Pending, Completed, Cancelled
                  ip_address TEXT,
                  cookie_id TEXT,
                  fingerprint TEXT,
                  user_id INTEGER, -- Consider relationship if using login
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                 )''')
    print("Bookings table checked/created.")

    # --- Check and Add Columns if they don't exist ---
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
    conn.close()
    print("Database initialization complete.")

init_db() # Run initialization

# Load doctors data (Keep using JSON for now)
doctors_data_path = 'doctors.json'
try:
    with open(doctors_data_path) as f:
        doctors_data = json.load(f)
except FileNotFoundError:
    print(f"Error: {doctors_data_path} not found. Please create it.")
    doctors_data = {'doctors': []} # Provide a default empty structure

# --- Standard Routes (Home, Booking Page, Confirmation etc.) ---

@app.route('/')
def home():
    return render_template('index.html', doctors=doctors_data.get('doctors', []))


@app.route('/booking/<int:doctor_id>')
def booking_page(doctor_id):
    try:
        doctor = next((d for d in doctors_data.get('doctors', []) if d['id'] == doctor_id), None)
        if not doctor:
             flash('Doctor not found.', 'error')
             return redirect(url_for('home'))

        today_str = date.today().strftime('%Y-%m-%d')

        response = make_response(render_template(
            'booking.html',
            doctor=doctor,
            doctor_id=doctor_id,
            today=today_str
            # REMOVED: availability=doctor.get('availability', {}) # Availability fetched dynamically now
        ))

        if not request.cookies.get('device_id'):
            device_id = str(uuid.uuid4())
            response.set_cookie('device_id', device_id, max_age=30*24*60*60, httponly=True, samesite='Lax')

        return response

    except Exception as e:
        print(f"Error in booking_page for doctor {doctor_id}: {e}")
        flash('An error occurred. Please try again later.', 'error')
        return redirect(url_for('home'))

# --- NEW ROUTE to fetch available slots ---
@app.route('/get-available-slots/<int:doctor_id>/<string:date_str>')
def get_available_slots(doctor_id, date_str):
    try:
        # Validate date format
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day_name = booking_date.strftime('%A') # Get 'Monday', 'Tuesday' etc.

        # Find doctor and their general availability for that day
        doctor = next((d for d in doctors_data.get('doctors', []) if d['id'] == doctor_id), None)
        if not doctor:
            return jsonify({'error': 'Doctor not found'}), 404

        doctor_availability = doctor.get('availability', {})
        general_slots = doctor_availability.get(day_name, [])

        if not general_slots or "Unavailable" in general_slots:
             return jsonify([]) # Return empty list if unavailable

        # Query DB for booked slots for this doctor on this date
        conn = get_db()
        c = conn.cursor()
        c.execute('''SELECT booking_time FROM bookings
                     WHERE doctor_id = ? AND booking_date = ? AND status != 'Cancelled' ''',
                  (doctor_id, date_str))
        booked_slots_rows = c.fetchall()
        conn.close()

        booked_times = {row['booking_time'] for row in booked_slots_rows}

        # Filter general slots to get available ones
        available_slots = [slot for slot in general_slots if slot not in booked_times]

        return jsonify(available_slots)

    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400
    except Exception as e:
        print(f"Error in get_available_slots for doctor {doctor_id}, date {date_str}: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    try:
        doctor_id = int(request.form['doctor_id'])
        patient_name = request.form['patient_name'].strip()
        patient_phone = request.form['patient_phone'].strip()
        booking_date_str = request.form['booking_date']
        # booking_time comes from the hidden input now, set by JS when a card is clicked
        booking_time = request.form.get('booking_time') # Use .get() for safety
        notes = request.form.get('notes', '').strip()
        ip_address = request.remote_addr
        cookie_id = request.cookies.get('device_id')
        user_id = current_user.id if current_user.is_authenticated else None
        fingerprint = request.form.get('fingerprint')
        # appointment_type = request.form.get('appointment_type', 'Consultation') # Still capture if sent

        # --- Basic Validation ---
        if not all([doctor_id, patient_name, patient_phone, booking_date_str, booking_time]):
            flash('⛔ Please fill in all required fields, including selecting a time slot.', 'error')
            # Need to redirect back to booking page
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        doctor = next((d for d in doctors_data.get('doctors', []) if d['id'] == doctor_id), None)
        if not doctor:
            flash('⛔ Invalid Doctor ID.', 'error')
            return redirect(url_for('home'))
        doctor_name = doctor['name']

        booking_date = datetime.strptime(booking_date_str, '%Y-%m-%d').date()
        selected_day_name = booking_date.strftime('%A')
        today_date = date.today()

        # --- Advanced Validation ---
        conn = get_db()
        c = conn.cursor()

        if booking_date < today_date:
            flash('⛔ You cannot book on a date before today.', 'error')
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # Check if doctor is generally available (redundant check maybe, but safe)
        # doctor_availability = doctor.get('availability', {})
        # day_schedule = doctor_availability.get(selected_day_name, [])
        # if "Unavailable" in day_schedule or not day_schedule:
        #     flash(f'⛔ {doctor_name} is not available on {selected_day_name}s.', 'error')
        #     conn.close()
        #     return redirect(url_for('booking_page', doctor_id=doctor_id))

        # Check if THIS SPECIFIC slot is already booked (most important check)
        c.execute('''SELECT 1 FROM bookings
                     WHERE doctor_id = ? AND booking_date = ? AND booking_time = ? AND status != 'Cancelled' ''',
                  (doctor_id, booking_date_str, booking_time))
        if c.fetchone():
            flash('⛔ This time slot was just booked. Please select another time.', 'error') # Slightly different msg
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # Check for existing booking by patient on the same day
        c.execute('''SELECT 1 FROM bookings
                     WHERE booking_date = ? AND status != 'Cancelled'
                     AND (patient_phone = ? OR (fingerprint IS NOT NULL AND fingerprint = ?) OR patient_name = ?)''',
                  (booking_date_str, patient_phone, fingerprint, patient_name))
        if c.fetchone():
            flash('⛔ You already have another booking scheduled for this day (identified by phone, device, or name). Only one booking per day is allowed.', 'error')
            conn.close()
            return redirect(url_for('booking_page', doctor_id=doctor_id))

        # --- Save to Database ---
        c.execute('''INSERT INTO bookings
                     (doctor_id, doctor_name, patient_name, patient_phone, booking_date, booking_time,
                      notes, status, ip_address, cookie_id, fingerprint, user_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', # Removed appointment_type
                  (doctor_id, doctor_name, patient_name, patient_phone, booking_date_str, booking_time,
                   notes, 'Pending', ip_address, cookie_id, fingerprint, user_id))
        conn.commit()
        booking_id = c.lastrowid
        conn.close()

        flash('✅ Booking confirmed successfully!', 'success')
        return redirect(url_for('confirmation', booking_id=booking_id))

    except ValueError as ve:
         print(f"Value error during booking confirmation: {ve}")
         flash('⛔ Invalid data provided (e.g., date format). Please check your input.', 'error')
         # Attempt to redirect back to booking page if doctor_id is available
         try:
             doc_id_for_redirect = int(request.form.get('doctor_id', 0))
             if doc_id_for_redirect:
                 return redirect(url_for('booking_page', doctor_id=doc_id_for_redirect))
         except: pass # Ignore errors trying to get doctor_id for redirect
         return redirect(url_for('home')) # Fallback redirect
    except sqlite3.Error as db_err:
        print(f"Database error during booking confirmation: {db_err}")
        flash('⛔ A database error occurred. Please try again.', 'error')
        # Attempt to redirect back to booking page
        try:
            doc_id_for_redirect = int(request.form.get('doctor_id', 0))
            if doc_id_for_redirect:
                return redirect(url_for('booking_page', doctor_id=doc_id_for_redirect))
        except: pass
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Error confirming booking: {e}")
        flash('⛔ An unexpected error occurred. Please contact support.', 'error')
        # Attempt to redirect back to booking page
        try:
            doc_id_for_redirect = int(request.form.get('doctor_id', 0))
            if doc_id_for_redirect:
                return redirect(url_for('booking_page', doctor_id=doc_id_for_redirect))
        except: pass
        return redirect(url_for('home'))

# --- Other routes remain unchanged ---

@app.route('/confirmation')
def confirmation():
    booking_id = request.args.get('booking_id')
    if not booking_id:
        return redirect(url_for('home'))

    conn = get_db()
    c = conn.cursor()
    # Fetch necessary columns for confirmation page
    c.execute('''SELECT id, doctor_name, patient_name, booking_date, booking_time
                 FROM bookings WHERE id = ?''', (booking_id,))
    booking = c.fetchone()
    conn.close()

    if not booking:
        flash('⛔ Booking not found.', 'error')
        return redirect(url_for('home'))

    # Convert row object to dict for easier template access if needed
    booking_dict = dict(booking) if booking else None
    return render_template('confirmation.html', booking=booking_dict)


@app.route('/delete-booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    conn = get_db()
    c = conn.cursor()

    c.execute('SELECT 1 FROM bookings WHERE id = ?', (booking_id,))
    exists = c.fetchone()

    if exists:
        # Instead of deleting, mark as Cancelled
        c.execute("UPDATE bookings SET status = 'Cancelled' WHERE id = ?", (booking_id,))
        conn.commit()
        flash('✅ Booking successfully cancelled.', 'success')
    else:
        flash('⛔ Booking not found.', 'error')

    conn.close()

    source = request.form.get('source', 'home')
    patient_identifier = request.form.get('patient_identifier')
    doctor_id = request.form.get('doctor_id') # Get doctor_id if source is doctor dash

    if source == 'confirmation' or source == 'home':
        return redirect(url_for('home'))
    elif source == 'patient_dashboard' and patient_identifier:
         return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
    elif source == 'doctor_dashboard' and doctor_id:
        # Make sure doctor_id is valid before redirecting
        try:
            valid_doctor_id = int(doctor_id)
            return redirect(url_for('doctor_dashboard', doctor_id=valid_doctor_id))
        except (ValueError, TypeError):
             return redirect(url_for('doctor_login')) # Fallback if invalid ID passed
    else:
        return redirect(url_for('home'))


# --- Doctor Login and Dashboard ---

@app.route('/doctor-login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        doctor_name = request.form.get('doctorName', '').strip()
        doctor_id_str = request.form.get('doctorId', '').strip()

        if not doctor_name or not doctor_id_str or not doctor_id_str.isdigit():
             flash('⛔ Please enter both Doctor Name and a valid ID.', 'error')
             return redirect(url_for('doctor_login'))

        doctor_id = int(doctor_id_str)
        doctor = next((d for d in doctors_data.get('doctors', []) if d['name'] == doctor_name and d['id'] == doctor_id), None)

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
    conn = get_db()
    c = conn.cursor()

    # Fetch bookings for the doctor - EXPLICITLY list needed columns
    c.execute('''SELECT id, doctor_id, doctor_name, patient_name, patient_phone,
                        booking_date, booking_time, notes, status
                 FROM bookings
                 WHERE doctor_id = ? AND status != 'Cancelled'
                 ORDER BY booking_date ASC, booking_time ASC''', (doctor_id,))
    bookings_rows = c.fetchall() # Fetches list of Row objects
    conn.close()

    # --- Data Processing for Stats & Daily Chart ONLY ---
    stats = {
        'today_count': 0,
        'week_count': 0,
        'pending_count': 0,
        'unique_patients_this_month': 0
    }
    appointments_per_day_data = defaultdict(int) # { 'YYYY-MM-DD': count }
    unique_patients_set = set()

    today_date = date.today()
    today_str = today_date.strftime('%Y-%m-%d')
    one_week_later = today_date + timedelta(days=7)
    current_month_str = today_date.strftime('%Y-%m')

    # Access rows by column name
    for booking in bookings_rows:
        try:
            # Convert Row to dict for easier processing if preferred, or access via booking['col_name']
            booking_dict = dict(booking)
            booking_date_obj = datetime.strptime(booking_dict['booking_date'], '%Y-%m-%d').date()
            booking_date_str_loop = booking_dict['booking_date'] # Use a different variable name inside loop
            booking_status = booking_dict['status']

            # Process only future/today's pending bookings for stats/charts
            if booking_date_obj >= today_date and booking_status == 'Pending':

                # --- Stats ---
                if booking_date_str_loop == today_str:
                    stats['today_count'] += 1
                if today_date <= booking_date_obj < one_week_later:
                    stats['week_count'] += 1
                stats['pending_count'] += 1

                # --- Daily Chart Data ---
                if today_date <= booking_date_obj < one_week_later:
                     appointments_per_day_data[booking_date_str_loop] += 1

                # --- Unique Patients (This Month, Future/Today Pending) ---
                if booking_date_str_loop.startswith(current_month_str):
                     patient_identifier = booking_dict['patient_name'] or booking_dict.get('patient_phone')
                     if patient_identifier:
                         unique_patients_set.add(patient_identifier)

        except (ValueError, KeyError, TypeError) as e: # Catch potential errors
            print(f"Warning: Skipping booking due to processing error: {dict(booking)} - Error: {e}")
            continue


    stats['unique_patients_this_month'] = len(unique_patients_set)

    # --- Prepare chart data for Daily Chart ONLY ---
    chart_labels_daily = []
    chart_data_daily = []
    for i in range(7):
        d = today_date + timedelta(days=i)
        d_str = d.strftime('%Y-%m-%d')
        chart_labels_daily.append(d.strftime('%a, %b %d')) # e.g., "Mon, Oct 26"
        chart_data_daily.append(appointments_per_day_data[d_str])

    # --- Organize Bookings for Display ---
    bookings_by_month = defaultdict(lambda: defaultdict(list))
    for booking in bookings_rows:
        try:
            booking_dict = dict(booking) # Convert to dict
            booking_date_dt = datetime.strptime(booking_dict['booking_date'], '%Y-%m-%d')
            month_year = booking_date_dt.strftime('%B %Y')
            day = booking_date_dt.strftime('%Y-%m-%d')
            bookings_by_month[month_year][day].append(booking_dict) # Append the dict
        except (ValueError, KeyError, TypeError) as e:
             print(f"Warning: Skipping booking in display grouping: {dict(booking)} - Error: {e}")
             continue

    # Convert defaultdicts to regular dicts for JSON serialization if needed by template/JS later
    # Although Jinja2 handles defaultdicts fine.
    final_bookings_by_month = {my: dict(days) for my, days in bookings_by_month.items()}

    return render_template(
        'doctor_dashboard.html',
        doctor_id=doctor_id,
        bookings_by_month=final_bookings_by_month, # Pass the converted dict
        stats=stats,
        # Pass ONLY the daily chart config
        chart_config_daily={
            'labels': chart_labels_daily,
            'data': chart_data_daily
        }
    )

# Endpoint to handle note updates
@app.route('/update-all-notes', methods=['POST'])
def update_all_notes():
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid request format, expected JSON.'}), 400
    data = request.get_json()
    updates = data.get('updates', [])
    if not isinstance(updates, list):
         return jsonify({'success': False, 'message': 'Invalid data format, "updates" should be a list.'}), 400

    conn = None
    try:
        conn = get_db() # Use central function
        c = conn.cursor()
        updated_count = 0
        for update in updates:
            booking_id = update.get('bookingId')
            notes = update.get('notes')
            if isinstance(booking_id, (int, str)) and str(booking_id).isdigit() and isinstance(notes, str):
                c.execute('''UPDATE bookings SET notes = ? WHERE id = ?''', (notes.strip(), int(booking_id)))
                if c.rowcount > 0: updated_count += 1
            else: print(f"Warning: Skipping invalid update data: {update}")
        conn.commit()
        print(f"Updated notes for {updated_count} bookings.")
        return jsonify({'success': True, 'message': f'{updated_count} notes updated successfully!'})
    except sqlite3.Error as db_err:
        print(f"Database error updating notes: {db_err}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {db_err}'}), 500
    except Exception as e:
        print(f"Error processing /update-all-notes: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'An internal error occurred: {e}'}), 500
    finally:
        if conn: conn.close()


# Endpoint to mark booking as complete
@app.route('/mark-complete/<int:booking_id>', methods=['POST'])
def mark_complete(booking_id):
    conn = None
    try:
        conn = get_db() # Use central function
        c = conn.cursor()
        # Ensure we only update 'Pending' bookings to 'Completed'
        c.execute("UPDATE bookings SET status = 'Completed' WHERE id = ? AND status = 'Pending'", (booking_id,))
        conn.commit()
        if c.rowcount > 0:
            print(f"Marked booking {booking_id} as completed.")
            return jsonify({'success': True, 'message': 'Booking marked as completed.'})
        else:
             # Check if already completed or not found/not pending
             c.execute("SELECT status FROM bookings WHERE id = ?", (booking_id,))
             result = c.fetchone()
             if result and result['status'] == 'Completed': # Access by column name
                  message = 'Booking already marked as completed.'
             elif result:
                  message = f'Booking status is {result["status"]}, cannot mark as completed.'
             else:
                  message = 'Booking not found.'
             print(f"Failed to mark booking {booking_id} as completed: {message}")
             return jsonify({'success': False, 'message': message}), 400 # Use 400 Bad Request for logic errors

    except sqlite3.Error as db_err:
        print(f"Database error marking booking {booking_id} complete: {db_err}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'Database error: {db_err}'}), 500
    except Exception as e:
        print(f"Error processing /mark-complete/{booking_id}: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'An internal error occurred: {e}'}), 500
    finally:
        if conn: conn.close()


# --- Patient Login and Dashboard ---

@app.route('/patient-login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        patient_identifier = request.form.get('patientIdentifier', '').strip()
        if not patient_identifier:
            flash('⛔ Please enter your name or phone number.', 'error')
            return redirect(url_for('patient_login'))

        conn = get_db() # Use central function
        c = conn.cursor()
        c.execute('''SELECT 1 FROM bookings
                     WHERE (patient_name = ? OR patient_phone = ?) AND status != 'Cancelled' LIMIT 1''',
                  (patient_identifier, patient_identifier))
        booking_exists = c.fetchone()
        conn.close()

        if booking_exists:
            return redirect(url_for('patient_dashboard', patient_identifier=patient_identifier))
        else:
            flash('⛔ No active bookings found for this name or phone number.', 'error')
            return redirect(url_for('patient_login'))

    return render_template('patient_login.html')


@app.route('/patient-dashboard/<path:patient_identifier>')
def patient_dashboard(patient_identifier):
    if not patient_identifier:
         return redirect(url_for('patient_login'))

    conn = get_db() # Use central function
    c = conn.cursor()
    # Explicitly select columns needed for patient dashboard
    c.execute('''SELECT id, doctor_name, patient_name, booking_date, booking_time, status, notes
                 FROM bookings
                 WHERE (patient_name = ? OR patient_phone = ?) AND status != 'Cancelled'
                 ORDER BY booking_date DESC, booking_time DESC''',
              (patient_identifier, patient_identifier))
    bookings_rows = c.fetchall()
    conn.close()

    # Convert rows to dicts for easier template access
    bookings = [dict(row) for row in bookings_rows]

    current_datetime = datetime.now() # Pass object for comparison

    return render_template('patient_dashboard.html',
                         bookings=bookings,
                         current_datetime=current_datetime,
                         patient_identifier=patient_identifier)

# --- Run Application ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    # Set debug=False in production
    # Use host='0.0.0.0' to make accessible on local network
    app.run(debug=True, host='0.0.0.0', port=port)