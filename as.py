import sqlite3
import io
import os
import json

# --- Configuration ---
# *** REPLACE THIS WITH THE ACTUAL PATH TO YOUR SQLITE DB FILE ***
SQLITE_DB_PATH = 'database/bookings.db'
# Output SQL file (optional, if None, prints to console)
OUTPUT_SQL_FILE = 'supabase_import.sql'
# Number of rows per INSERT statement batch (adjust based on row size/complexity)
INSERT_BATCH_SIZE = 200
# Schema name in PostgreSQL (Supabase default)
PG_SCHEMA = 'public'
# --- End Configuration ---


def map_sqlite_type_to_pg(sqlite_type, column_name, is_pk, is_auto_increment_like):
    """Maps SQLite data types to PostgreSQL types. VERY basic mapping."""
    sqlite_type_upper = sqlite_type.upper() if sqlite_type else ''

    # Handle potential auto-increment primary keys first
    if is_pk and is_auto_increment_like:
        # Use BIGSERIAL for safety if numbers might exceed 2 billion
        # Or SERIAL if you are sure they won't. BIGSERIAL recommended.
        return 'BIGSERIAL PRIMARY KEY' if 'id' in column_name.lower() else 'SERIAL PRIMARY KEY'
        # Note: This removes the need for separate PRIMARY KEY clause for single PK cols

    # General Type Mapping (adjust as needed!)
    if 'INT' in sqlite_type_upper:
        # If it was already identified as PK, type is handled above.
        # Otherwise, map to INTEGER or BIGINT.
        return 'BIGINT' if is_pk else 'INTEGER'
    elif 'TEXT' in sqlite_type_upper or 'CLOB' in sqlite_type_upper or 'CHAR' in sqlite_type_upper:
         # Check for likely JSON stored as text
         if 'json' in column_name.lower() or 'availability' in column_name.lower(): # Customize based on your columns
            return 'JSONB' # Use JSONB in Postgres if it was JSON text in SQLite
         return 'TEXT'
    elif 'REAL' in sqlite_type_upper or 'FLOAT' in sqlite_type_upper or 'DOUBLE' in sqlite_type_upper:
        # Consider NUMERIC for exact precision if needed, otherwise DOUBLE PRECISION
        return 'DOUBLE PRECISION'
    elif 'BLOB' in sqlite_type_upper:
        return 'BYTEA'
    elif 'NUMERIC' in sqlite_type_upper or 'DECIMAL' in sqlite_type_upper:
        return 'NUMERIC' # Potentially add precision/scale if known
    elif 'BOOL' in sqlite_type_upper:
        return 'BOOLEAN'
    elif 'DATE' in sqlite_type_upper:
        # How was date stored? If text 'YYYY-MM-DD', map to DATE.
        # If stored as number/julian day, conversion might be needed.
        return 'DATE' # Assumption
    elif 'TIME' in sqlite_type_upper:
         # Includes TIMESTAMP, DATETIME etc.
         # TIMESTAMPTZ (Timestamp with Time Zone) is generally recommended in Postgres
         return 'TIMESTAMPTZ' # Assumption
    else:
        print(f"Warning: Unrecognized SQLite type '{sqlite_type}' for column '{column_name}'. Defaulting to TEXT.")
        return 'TEXT'

def format_value_for_pg(value):
    """Formats Python values for inclusion in PostgreSQL INSERT statements."""
    if value is None:
        return 'NULL'
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    elif isinstance(value, bytes):
        # Format bytes as PostgreSQL bytea literal (hex format)
        return f"'\\x{value.hex()}'"
    elif isinstance(value, str):
        # Escape single quotes and wrap in single quotes
        escaped_value = value.replace("'", "''")
        return f"'{escaped_value}'"
    elif isinstance(value, (dict, list)):
        # Assume this should be treated as JSON
        json_string = json.dumps(value)
        escaped_json = json_string.replace("'", "''")
        return f"'{escaped_json}'::jsonb" # Explicit cast to JSONB
    else:
        # Default: attempt to cast to string, escape quotes
        escaped_value = str(value).replace("'", "''")
        return f"'{escaped_value}'"


def generate_supabase_sql(db_path, output_file=None):
    """Connects to SQLite DB, reads schema & data, generates PG SQL."""

    if not os.path.exists(db_path):
        print(f"Error: SQLite database file not found at '{db_path}'")
        return

    print(f"Connecting to SQLite database: {db_path}")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # Use dictionary row factory for easier access by column name
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row['name'] for row in cursor.fetchall()]
        print(f"Found tables: {tables}")

        # Use io.StringIO to build the SQL string efficiently
        sql_output = io.StringIO()
        sql_output.write(f"-- SQLite to PostgreSQL Conversion Script Output --\n")
        sql_output.write(f"-- Generated on: {datetime.now().isoformat()} --\n\n")
        sql_output.write(f"SET statement_timeout = 0;\n")
        sql_output.write(f"SET lock_timeout = 0;\n")
        sql_output.write(f"SET idle_in_transaction_session_timeout = 0;\n")
        sql_output.write(f"SET client_encoding = 'UTF8';\n")
        sql_output.write(f"SET standard_conforming_strings = on;\n")
        sql_output.write(f"SELECT pg_catalog.set_config('search_path', '', false);\n")
        sql_output.write(f"SET check_function_bodies = false;\n")
        sql_output.write(f"SET xmloption = content;\n")
        sql_output.write(f"SET client_min_messages = warning;\n")
        sql_output.write(f"SET row_security = off;\n\n")
        # sql_output.write(f"CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA};\n") # Schema usually exists
        # sql_output.write(f"ALTER SCHEMA {PG_SCHEMA} OWNER TO postgres; -- Adjust owner if needed\n\n")


        # Process each table for schema (CREATE TABLE)
        print("\n--- Generating CREATE TABLE statements ---")
        foreign_keys_sql = [] # Store FK constraints to add later
        for table_name in tables:
            print(f"Processing schema for table: {table_name}")
            sql_output.write(f"\n-- Schema for table: {table_name} --\n")
            sql_output.write(f"DROP TABLE IF EXISTS {PG_SCHEMA}.\"{table_name}\" CASCADE;\n") # Drop if exists
            sql_output.write(f"CREATE TABLE {PG_SCHEMA}.\"{table_name}\" (\n")

            cursor.execute(f"PRAGMA table_info('{table_name}');")
            columns_info = cursor.fetchall()

            # Detect if integer primary key behaves like auto-increment
            pk_cols = [col['name'] for col in columns_info if col['pk'] > 0]
            is_auto_increment_like = False
            if len(pk_cols) == 1:
                 pk_col_name = pk_cols[0]
                 pk_col_info = next((col for col in columns_info if col['name'] == pk_col_name), None)
                 # Simple check: if PK is INTEGER type in SQLite, likely auto-increment
                 if pk_col_info and 'INT' in (pk_col_info['type'] or '').upper():
                     is_auto_increment_like = True


            column_definitions = []
            for i, col in enumerate(columns_info):
                col_name = col['name']
                sqlite_type = col['type']
                is_pk = col['pk'] > 0
                is_not_null = col['notnull'] == 1
                default_val = col['dflt_value']

                pg_type_mapping = map_sqlite_type_to_pg(sqlite_type, col_name, is_pk, is_auto_increment_like and len(pk_cols) == 1)

                col_def = f"    \"{col_name}\" {pg_type_mapping}"

                 # Add NOT NULL constraint *unless* type already includes PRIMARY KEY
                if is_not_null and 'PRIMARY KEY' not in pg_type_mapping:
                    col_def += " NOT NULL"

                # Handle DEFAULT values (basic handling, might need adjustment)
                if default_val is not None:
                     # Special cases for current time
                     if 'CURRENT_TIMESTAMP' in str(default_val).upper():
                          col_def += " DEFAULT now()"
                     elif 'CURRENT_DATE' in str(default_val).upper():
                          col_def += " DEFAULT CURRENT_DATE"
                     elif 'CURRENT_TIME' in str(default_val).upper():
                          col_def += " DEFAULT CURRENT_TIME"
                     else:
                          # Use the formatting function for default constants
                          col_def += f" DEFAULT {format_value_for_pg(default_val)}"

                column_definitions.append(col_def)

             # Add multi-column primary key constraint if needed (and not handled by SERIAL types)
            if len(pk_cols) > 1:
                 pk_constraint = f",\n    PRIMARY KEY ({', '.join(f'\"{col}\"' for col in pk_cols)})"
                 column_definitions.append(pk_constraint)
             # Remove trailing comma from the *last non-PK* definition if PK is separate
            elif not column_definitions[-1].strip().endswith(')') and len(pk_cols) > 1 : # Check last item is not already PK clause
                 pass # PK clause already added


            sql_output.write(",\n".join(column_definitions))
            sql_output.write("\n);\n")
            # Add table owner if needed (usually handled by Supabase role)
            # sql_output.write(f"ALTER TABLE {PG_SCHEMA}.\"{table_name}\" OWNER TO postgres;\n")

            # Store foreign key definitions to add after all tables are created
            cursor.execute(f"PRAGMA foreign_key_list('{table_name}');")
            fks = cursor.fetchall()
            if fks:
                for fk in fks:
                    fk_id = fk['id'] # Used to group composite FKs if any
                    from_col = fk['from']
                    target_table = fk['table']
                    to_col = fk['to']
                    on_update = fk['on_update'].upper()
                    on_delete = fk['on_delete'].upper()

                    fk_sql = f"ALTER TABLE ONLY {PG_SCHEMA}.\"{table_name}\" ADD CONSTRAINT \"{table_name}_{from_col}_fk_{fk_id}\" FOREIGN KEY (\"{from_col}\") REFERENCES {PG_SCHEMA}.\"{target_table}\"(\"{to_col}\")"
                    if on_update != 'NO ACTION': fk_sql += f" ON UPDATE {on_update}"
                    if on_delete != 'NO ACTION': fk_sql += f" ON DELETE {on_delete}"
                    fk_sql += ";\n"
                    foreign_keys_sql.append(fk_sql)

        # Process each table for data (INSERT INTO)
        print("\n--- Generating INSERT INTO statements ---")
        for table_name in tables:
            print(f"Processing data for table: {table_name}")
            sql_output.write(f"\n-- Data for table: {table_name} --\n")

            cursor.execute(f"SELECT * FROM \"{table_name}\";") # Fetch all rows
            rows = cursor.fetchall()

            if not rows:
                print(f"Table '{table_name}' is empty. Skipping INSERT.")
                continue

            # Get column names in the correct order from the cursor description
            column_names = [description[0] for description in cursor.description]
            quoted_column_names = ', '.join(f'\"{name}\"' for name in column_names)

            insert_prefix = f"INSERT INTO {PG_SCHEMA}.\"{table_name}\" ({quoted_column_names}) VALUES\n"

            value_rows = []
            for i, row in enumerate(rows):
                # Map Python row values to SQL formatted strings
                formatted_values = [format_value_for_pg(row[col_name]) for col_name in column_names]
                value_rows.append(f"({', '.join(formatted_values)})")

                # Write INSERT statement in batches
                if len(value_rows) >= INSERT_BATCH_SIZE or i == len(rows) - 1:
                    sql_output.write(insert_prefix)
                    sql_output.write(",\n".join(value_rows))
                    sql_output.write(";\n")
                    print(f"  Generated INSERT batch for rows {i - len(value_rows) + 1} to {i+1}")
                    value_rows = [] # Reset batch


        # Add Foreign Key constraints at the end
        if foreign_keys_sql:
            print("\n--- Generating FOREIGN KEY constraints ---")
            sql_output.write("\n\n-- Foreign Key Constraints --\n")
            for fk_sql in foreign_keys_sql:
                sql_output.write(fk_sql)


        # Write the output
        generated_sql = sql_output.getvalue()
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(generated_sql)
            print(f"\nSQL script successfully written to: {output_file}")
        else:
            print("\n--- Generated SQL Script ---")
            print(generated_sql)
            print("--- End of SQL Script ---")

    except sqlite3.Error as e:
        print(f"An error occurred with the SQLite database: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("SQLite connection closed.")

# --- Run the script ---
from datetime import datetime
generate_supabase_sql(SQLITE_DB_PATH, OUTPUT_SQL_FILE)