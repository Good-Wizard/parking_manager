from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
import sqlite3
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

DATABASE = 'database.db'
HISTORY_DATABASE = 'history.db'

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/errors.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.ERROR)
app.logger.addHandler(file_handler)

# Create table if it does not exist in the main database
try:
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS parking (
                    id INTEGER PRIMARY KEY,
                    plate_number TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT
                )''')
    conn.commit()
    conn.close()
except Exception as e:
    app.logger.error(f"Error creating parking table: {e}")

# Create table if it does not exist in the history database
try:
    conn = sqlite3.connect(HISTORY_DATABASE)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY,
                    plate_number TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    duration INTEGER,
                    cost INTEGER
                )''')
    conn.commit()
    conn.close()
except Exception as e:
    app.logger.error(f"Error creating history table: {e}")

def get_db():
    try:
        conn = sqlite3.connect(DATABASE)
        return conn
    except Exception as e:
        app.logger.error(f"Error connecting to database: {e}")
        return None

def get_history_db():
    try:
        conn = sqlite3.connect(HISTORY_DATABASE)
        return conn
    except Exception as e:
        app.logger.error(f"Error connecting to history database: {e}")
        return None

@app.route('/')
def index():
    return redirect('/home')

@app.route('/home')
def home():
    try:
        conn = get_db()
        if conn is None:
            raise Exception("Database connection failed")
        cur = conn.cursor()
        cur.execute("SELECT id, plate_number, entry_time FROM parking WHERE exit_time IS NULL")
        parked_cars = cur.fetchall()
        conn.close()

        total_spaces = 100
        occupied_spaces = len(parked_cars)
        free_spaces = total_spaces - occupied_spaces

        return render_template('index.html', parked_cars=parked_cars, free_spaces=free_spaces, occupied_spaces=occupied_spaces)
    except Exception as e:
        app.logger.error(f"Error in home route: {e}")
        return render_template('index.html', error_message="مشکلی در بارگیری داده‌ها رخ داده است. لطفاً دوباره تلاش کنید.")

@app.route('/park', methods=['POST'])
def park_car():
    try:
        plate_number = request.form['plate_part1'] + request.form['plate_letter'] + request.form['plate_part2'] + request.form['plate_part3']
        entry_time = datetime.now()

        conn = get_db()
        if conn is None:
            raise Exception("Database connection failed")
        cur = conn.cursor()
        cur.execute("INSERT INTO parking (plate_number, entry_time) VALUES (?, ?)", (plate_number, entry_time))
        conn.commit()
        conn.close()

        # Save to history database
        conn = get_history_db()
        if conn is None:
            raise Exception("History database connection failed")
        cur = conn.cursor()
        cur.execute("INSERT INTO history (plate_number, entry_time) VALUES (?, ?)", (plate_number, entry_time))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Error in park_car route: {e}")
        return render_template('index.html', error_message="مشکلی در ثبت خودرو رخ داده است. لطفاً دوباره تلاش کنید.")

@app.route('/exit/<int:car_id>', methods=['POST'])
def exit_car(car_id):
    try:
        exit_time = datetime.now()

        conn = get_db()
        if conn is None:
            raise Exception("Database connection failed")
        cur = conn.cursor()
        cur.execute("SELECT plate_number, entry_time FROM parking WHERE id = ?", (car_id,))
        car_data = cur.fetchone()
        if car_data is None:
            raise Exception("Car not found")
        plate_number = car_data[0]
        entry_time_str = car_data[1]
        entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S.%f')
        duration = exit_time - entry_time
        minutes = int(duration.total_seconds() // 60)

        # Calculate the cost based on new rules
        if minutes <= 5:
            cost = 0
        elif minutes <= 15:
            cost = 2500
        elif minutes <= 30:
            cost = 5000
        elif minutes <= 45:
            cost = 7500
        else:
            cost = 10000

        cur.execute("UPDATE parking SET exit_time = ? WHERE id = ?", (exit_time, car_id))
        conn.commit()
        conn.close()

        # Save to history database
        conn = get_history_db()
        if conn is None:
            raise Exception("History database connection failed")
        cur = conn.cursor()
        cur.execute("UPDATE history SET exit_time = ?, duration = ?, cost = ? WHERE plate_number = ? AND entry_time = ?",
                    (exit_time, minutes, cost, plate_number, entry_time_str))
        conn.commit()
        conn.close()

        return jsonify({"duration": f"{minutes} دقیقه", "cost": cost})
    except Exception as e:
        app.logger.error(f"Error in exit_car route: {e}")
        return jsonify({"error": "مشکلی در خروج خودرو رخ داده است. لطفاً دوباره تلاش کنید."})

@app.route('/history')
def history():
    try:
        conn = get_history_db()
        if conn is None:
            raise Exception("History database connection failed")
        cur = conn.cursor()
        cur.execute("SELECT * FROM history")
        history_data = cur.fetchall()
        conn.close()

        return render_template('history.html', history_data=history_data)
    except Exception as e:
        app.logger.error(f"Error in history route: {e}")
        return render_template('history.html', error_message="مشکلی در بارگیری تاریخچه رخ داده است. لطفاً دوباره تلاش کنید.")

if __name__ == '__main__':
    app.run(debug=True)
