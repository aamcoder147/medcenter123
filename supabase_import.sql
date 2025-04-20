-- SQLite to PostgreSQL Conversion Script Output --
-- Generated on: 2025-04-20T04:22:42.755494 --

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


-- Schema for table: bookings --
DROP TABLE IF EXISTS public."bookings" CASCADE;
CREATE TABLE public."bookings" (
    "id" BIGSERIAL PRIMARY KEY,
    "doctor_id" INTEGER NOT NULL,
    "doctor_name" TEXT,
    "patient_name" TEXT NOT NULL,
    "patient_phone" TEXT,
    "booking_date" TEXT NOT NULL,
    "booking_time" TEXT NOT NULL,
    "notes" TEXT,
    "appointment_type" TEXT DEFAULT '''Consultation''',
    "status" TEXT DEFAULT '''Pending''',
    "ip_address" TEXT,
    "cookie_id" TEXT,
    "fingerprint" TEXT,
    "user_id" INTEGER,
    "created_at" TIMESTAMPTZ DEFAULT now()
);

-- Schema for table: doctors --
DROP TABLE IF EXISTS public."doctors" CASCADE;
CREATE TABLE public."doctors" (
    "id" BIGSERIAL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "availability1shortform" TEXT,
    "province" TEXT,
    "governorate" TEXT,
    "facility_type" TEXT,
    "rate" DOUBLE PRECISION,
    "plc" TEXT,
    "specialization" TEXT,
    "photo" TEXT,
    "description" TEXT,
    "availability" TEXT
);

-- Schema for table: reviews --
DROP TABLE IF EXISTS public."reviews" CASCADE;
CREATE TABLE public."reviews" (
    "id" BIGSERIAL PRIMARY KEY,
    "doctor_id" INTEGER NOT NULL,
    "reviewer_name" TEXT NOT NULL,
    "reviewer_phone" TEXT,
    "rating" INTEGER NOT NULL,
    "comment" TEXT,
    "created_at" TIMESTAMPTZ DEFAULT now(),
    "is_approved" INTEGER DEFAULT '1'
);

-- Schema for table: site_testimonials --
DROP TABLE IF EXISTS public."site_testimonials" CASCADE;
CREATE TABLE public."site_testimonials" (
    "id" BIGSERIAL PRIMARY KEY,
    "reviewer_name" TEXT NOT NULL,
    "rating" INTEGER NOT NULL,
    "comment" TEXT,
    "created_at" TIMESTAMPTZ DEFAULT now(),
    "is_approved" INTEGER DEFAULT '0'
);

-- Schema for table: site_reviews --
DROP TABLE IF EXISTS public."site_reviews" CASCADE;
CREATE TABLE public."site_reviews" (
    "id" BIGSERIAL PRIMARY KEY,
    "reviewer_name" TEXT NOT NULL,
    "rating" INTEGER NOT NULL,
    "comment" TEXT,
    "created_at" TIMESTAMPTZ DEFAULT now(),
    "is_approved" INTEGER DEFAULT '1'
);

-- Data for table: bookings --
INSERT INTO public."bookings" ("id", "doctor_id", "doctor_name", "patient_name", "patient_phone", "booking_date", "booking_time", "notes", "appointment_type", "status", "ip_address", "cookie_id", "fingerprint", "user_id", "created_at") VALUES
(1, 6, 'Dr. Farhan Ansari', 'aa', '741258963', '2025-04-14', '14:00-14:30', '', 'Consultation', 'Pending', NULL, NULL, NULL, NULL, '2025-04-12 08:33:12'),
(2, 1, 'Dr. Aisha Khan', 'ggjh', '741852963', '2025-04-12', '08:00-08:20', 'knjjhj', 'Consultation', 'Pending', NULL, NULL, NULL, NULL, '2025-04-12 09:10:40'),
(3, 1, 'Dr. Aisha Khan', '123456789', '321654987', '2025-04-12', '08:20-08:40', 'j', 'Consultation', 'Pending', NULL, NULL, NULL, NULL, '2025-04-12 12:32:01'),
(4, 1, 'Dr. Aisha Khan', 'jj', '798465301', '2025-04-12', '08:40-09:00', '', 'Consultation', 'Pending', NULL, NULL, NULL, NULL, '2025-04-12 13:01:31'),
(5, 1, 'Dr. Aisha Khan', '789456321', '753159624', '2025-04-12', '09:00-09:20', '', 'Consultation', 'Cancelled', NULL, NULL, NULL, NULL, '2025-04-12 13:35:43'),
(6, 1, 'Dr. Aisha Khan', 'aada', '789632540', '2025-04-12', '09:00-09:20', '', 'Consultation', 'Cancelled', NULL, NULL, NULL, NULL, '2025-04-12 13:37:45'),
(7, 1, 'Dr. Aisha Khan', '7899', '789654321', '2025-04-12', '09:00-09:20', '', 'Consultation', 'Pending', NULL, NULL, NULL, NULL, '2025-04-12 13:38:15'),
(8, 2, 'Dr. Binod Sharma', 'ABDULRHMAN ABDULLAH MOHAMMAD ABDULLAH ALHUMIKANI', '770150639', '2025-04-13', '08:00-08:20', '', 'Consultation', 'Pending', '127.0.0.1', '1977e1de-cd7e-4045-b8f1-8a3e6d1603b9', '950054a955be90460b5374ddfd3ca6a4', NULL, '2025-04-12 18:25:06'),
(9, 10, 'Dr. Jamal Malik', 'AL-BAIHANI SECONDARY SCHOOL', '781275727', '2025-04-15', '17:00-17:30', '', 'Consultation', 'Pending', '127.0.0.1', '1977e1de-cd7e-4045-b8f1-8a3e6d1603b9', '9ffd87eb10bff427b4d7041fc3e21ec9', NULL, '2025-04-12 20:18:13'),
(10, 1, 'Dr. Aisha Khan', 'ww', '789456123', '2025-04-13', '08:00-08:20', '', 'Consultation', 'Cancelled', '127.0.0.1', '1977e1de-cd7e-4045-b8f1-8a3e6d1603b9', '950054a955be90460b5374ddfd3ca6a4', NULL, '2025-04-12 21:11:48'),
(11, 1, 'Dr. Aisha Khan', 'ee', '74589632312', '2025-04-23', '07:00-07:20', '', 'Consultation', 'Pending', '127.0.0.1', '1977e1de-cd7e-4045-b8f1-8a3e6d1603b9', '950054a955be90460b5374ddfd3ca6a4', NULL, '2025-04-12 21:13:05'),
(12, 1, 'Dr. Aisha Khan', 'kjj', '748596321', '2025-04-13', '08:00-08:20', '', 'Consultation', 'Cancelled', '127.0.0.1', '1977e1de-cd7e-4045-b8f1-8a3e6d1603b9', '950054a955be90460b5374ddfd3ca6a4', NULL, '2025-04-12 22:13:35'),
(13, 5, 'Dr. Elina Maharjan', '[poij', '789654123', '2025-04-16', '10:00-10:20', '', 'Consultation', 'Pending', '127.0.0.1', '1977e1de-cd7e-4045-b8f1-8a3e6d1603b9', '950054a955be90460b5374ddfd3ca6a4', NULL, '2025-04-14 12:14:26');

-- Data for table: doctors --
INSERT INTO public."doctors" ("id", "name", "availability1shortform", "province", "governorate", "facility_type", "rate", "plc", "specialization", "photo", "description", "availability") VALUES
(1, 'Dr. Aisha Khan', 'Mon-Thu: 7am-8am, Sat-Sun: 8am-11am', 'Bagmati', 'Kathmandu', 'Private Clinic', 4.5, 'City Clinic', 'Dermatology', '/static/doctors/doctor1.jpg', 'Expert in cosmetic and medical dermatology.', '{"Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Wednesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Thursday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Friday": ["Unavailable"], "Saturday": ["08:00-08:20", "08:20-08:40", "08:40-09:00", "09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"], "Sunday": ["08:00-08:20", "08:20-08:40", "08:40-09:00"]}'),
(2, 'Dr. Binod Sharma', 'Mon-Wed:7:00am-8:00am, Sat: 8am-11am, Sun: 8am-9am', 'Gandaki', 'Kaski', 'Hospital', 4.2, 'Lakeview Hospital', 'Cardiology', '/static/doctors/doctor3.jpg', 'Specializing in preventative cardiology and heart health.', '{"Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Wednesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Thursday": ["Unavailable"], "Friday": ["Unavailable"], "Saturday": ["08:00-08:20", "08:20-08:40", "08:40-09:00", "09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"], "Sunday": ["08:00-08:20", "08:20-08:40", "08:40-09:00"]}'),
(3, 'Dr. Chitra Gurung', 'Mon-Tue: 7am-8am, Sat-Sun: 9am-12pm', 'Lumbini', 'Rupandehi', 'Private Clinic', 4.8, 'Peace Clinic', 'Pediatrics', '/static/doctors/doctor4.jpg', 'Dedicated pediatric care for infants, children, and adolescents.', '{"Monday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Tuesday": ["07:00-07:20", "07:20-07:40", "07:40-08:00"], "Wednesday": ["Unavailable"], "Thursday": ["Unavailable"], "Friday": ["Unavailable"], "Saturday": ["09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20", "11:20-11:40", "11:40-12:00"], "Sunday": ["09:00-09:20", "09:20-09:40", "09:40-10:00", "10:00-10:20", "10:20-10:40", "10:40-11:00"]}'),
(4, 'Dr. David Rai', 'Mon-Tue: 9am-10:30am, Fri-Sun: 11am-12:30pm', 'Province 1', 'Morang', 'Clinic', 4.0, 'Mountain View Clinic', 'Orthopedics', '/static/doctors/doctor2.jpg', 'Board-certified orthopedic surgeon with 10+ years experience.', '{"Monday": ["09:00-09:30", "09:30-10:00", "10:00-10:30"], "Tuesday": ["09:00-09:30", "09:30-10:00", "10:00-10:30"], "Wednesday": ["Unavailable"], "Thursday": ["Unavailable"], "Friday": ["11:00-11:30", "11:30-12:00", "12:00-12:30"], "Saturday": ["11:00-11:30", "11:30-12:00", "12:00-12:30"], "Sunday": ["11:00-11:30", "11:30-12:00", "12:00-12:30"]}'),
(5, 'Dr. Elina Maharjan', 'Wed-Fri: 10am-12pm, Sat: 1pm-3pm', 'Bagmati', 'Lalitpur', 'Health Hub', 4.6, 'Central Health Hub', 'General Physician', '/static/doctors/doctor5.jpg', 'Comprehensive primary care for all ages.', '{"Monday": ["Unavailable"], "Tuesday": ["Unavailable"], "Wednesday": ["10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20", "11:20-11:40", "11:40-12:00"], "Thursday": ["10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20"], "Friday": ["10:00-10:20", "10:20-10:40", "10:40-11:00", "11:00-11:20", "11:20-11:40", "11:40-12:00"], "Saturday": ["13:00-13:30", "13:30-14:00", "14:00-14:30", "14:30-15:00"], "Sunday": ["Unavailable"]}'),
(6, 'Dr. Farhan Ansari', 'Mon/Wed/Fri: 2pm-4pm', 'Province 2', 'Parsa', 'Care Center', 4.1, 'Terai Care Center', 'Neurology', '/static/doctors/doctor6.jpg', 'Expertise in neurological disorders and treatments.', '{"Monday": ["14:00-14:30", "14:30-15:00", "15:00-15:30", "15:30-16:00"], "Tuesday": ["Unavailable"], "Wednesday": ["14:00-14:30", "14:30-15:00", "15:00-15:30", "15:30-16:00"], "Thursday": ["Unavailable"], "Friday": ["14:00-14:30", "14:30-15:00", "15:00-15:30", "15:30-16:00"], "Saturday": ["Unavailable"], "Sunday": ["Unavailable"]}'),
(7, 'Dr. Gita Pandey', 'Tue/Thu: 9am-11am, Sat: 10am-1pm', 'Gandaki', 'Kaski', 'Clinic', 4.7, 'Himalayan Clinic', 'Dermatology', '/static/doctors/doctor7.jpg', 'Advanced skincare solutions and treatments.', '{"Monday": ["Unavailable"], "Tuesday": ["09:00-09:30", "09:30-10:00", "10:00-10:30", "10:30-11:00"], "Wednesday": ["Unavailable"], "Thursday": ["09:00-09:30", "09:30-10:00", "10:00-10:30", "10:30-11:00"], "Friday": ["Unavailable"], "Saturday": ["10:00-10:30", "10:30-11:00", "11:00-11:30", "11:30-12:00", "12:00-12:30", "12:30-13:00"], "Sunday": ["Unavailable"]}'),
(8, 'Dr. Hari Joshi', 'Mon-Fri: 8am-10am', 'Sudurpashchim', 'Kailali', 'Regional Clinic', 3.9, 'Western Regional Clinic', 'General Physician', '/static/doctors/doctor8.jpg', 'Providing general health check-ups and consultations.', '{"Monday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"], "Tuesday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"], "Wednesday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"], "Thursday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"], "Friday": ["08:00-08:30", "08:30-09:00", "09:00-09:30", "09:30-10:00"], "Saturday": ["Unavailable"], "Sunday": ["Unavailable"]}'),
(9, 'Dr. Ishani Thapa', 'Sat-Sun: 3pm-5pm', 'Lumbini', 'Kapilvastu', 'Health Post', 4.3, 'Community Health Post', 'Pediatrics', '/static/doctors/doctor9.jpg', 'Weekend pediatric clinic.', '{"Monday": ["Unavailable"], "Tuesday": ["Unavailable"], "Wednesday": ["Unavailable"], "Thursday": ["Unavailable"], "Friday": ["Unavailable"], "Saturday": ["15:00-15:20", "15:20-15:40", "15:40-16:00", "16:00-16:20", "16:20-16:40", "16:40-17:00"], "Sunday": ["15:00-15:20", "15:20-15:40", "15:40-16:00", "16:00-16:20", "16:20-16:40", "16:40-17:00"]}'),
(10, 'Dr. Jamal Malik', 'Tue\Thu: 5pm-7pm', 'Province 1', 'Jhapa', 'Hospital', 4.4, 'Eastern Care Hospital', 'Cardiology', '/static/doctors/doctor10.jpg', 'Evening cardiology consultations available.', '{"Monday": ["Unavailable"], "Tuesday": ["17:00-17:30", "17:30-18:00", "18:00-18:30", "18:30-19:00"], "Wednesday": ["Unavailable"], "Thursday": ["17:00-17:30", "17:30-18:00", "18:00-18:30", "18:30-19:00"], "Friday": ["Unavailable"], "Saturday": ["Unavailable"], "Sunday": ["Unavailable"]}');

-- Data for table: reviews --
INSERT INTO public."reviews" ("id", "doctor_id", "reviewer_name", "reviewer_phone", "rating", "comment", "created_at", "is_approved") VALUES
(1, 1, 'aaaaaa', '770150639', 3, 'kmlmklmlm', '2025-04-12 11:48:38', 1),
(2, 1, 'hvh', '789632541', 3, '', '2025-04-12 11:51:19', 1),
(3, 1, 'aa', '789654123', 3, '', '2025-04-12 12:01:19', 1),
(4, 1, 'jkb', '123564897', 3, 'k', '2025-04-12 12:01:43', 1),
(5, 1, '321654987', '321654987', 1, 'h', '2025-04-12 12:32:21', 1),
(6, 1, 'jj', '789456123', 1, 'aqw', '2025-04-12 13:01:52', 1),
(7, 2, 'ABDULRHMAN ABDULLAH MOHAMMAD ABDULLAH ALHUMIKANI', '770150635', 4, 'jjknjk', '2025-04-12 18:25:38', 1),
(8, 10, 'AL-BAIHANI SECONDARY SCHOOL', '781275727', 2, '', '2025-04-12 20:18:37', 1),
(9, 1, 'ww', '741852963', 2, '', '2025-04-12 21:12:19', 1);

-- Data for table: site_testimonials --
INSERT INTO public."site_testimonials" ("id", "reviewer_name", "rating", "comment", "created_at", "is_approved") VALUES
(1, 'ABDULRHMAN ABDULLAH MOHAMMAD ABDULLAH ALHUMIKANI', 3, '', '2025-04-12 19:06:35', 0);

-- Data for table: site_reviews --
INSERT INTO public."site_reviews" ("id", "reviewer_name", "rating", "comment", "created_at", "is_approved") VALUES
(1, '444445', 1, 'j', '2025-04-12 19:16:02', 1),
(2, '454564', 3, 'mknknkn', '2025-04-12 19:16:35', 1),
(3, 'lmlkmlm', 3, 'nknnl', '2025-04-12 19:16:48', 1),
(4, 'ABDULRHMAN ABDULLAH MOHAMMAD ABDULLAH ALHUMIKANI', 3, 'lml', '2025-04-12 20:03:17', 1),
(5, 'jkhkj', 3, '', '2025-04-12 22:40:17', 1),
(6, 'oiuy', 4, 'mmn', '2025-04-12 23:00:00', 1),
(7, 'jjjk', 2, '', '2025-04-14 12:12:03', 1),
(8, 'bmn', 3, '', '2025-04-18 20:52:26', 1);


-- Foreign Key Constraints --
ALTER TABLE ONLY public."bookings" ADD CONSTRAINT "bookings_doctor_id_fk_0" FOREIGN KEY ("doctor_id") REFERENCES public."doctors"("id");
ALTER TABLE ONLY public."reviews" ADD CONSTRAINT "reviews_doctor_id_fk_0" FOREIGN KEY ("doctor_id") REFERENCES public."doctors"("id");
