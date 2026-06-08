import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request, render_template

app = Flask(__name__, template_folder='templates', static_folder='static')

DATABASE = 'naps.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS naps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER NOT NULL,          -- in seconds
                rating INTEGER DEFAULT 3,           -- 1 to 5 scale
                location TEXT DEFAULT 'bed',        -- 'bed', 'sofa', 'desk', 'other'
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/naps', methods=['GET'])
def get_naps():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM naps ORDER BY start_time DESC')
            rows = cursor.fetchall()
            naps = [dict(row) for row in rows]
            return jsonify(naps)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/naps', methods=['POST'])
def add_nap():
    try:
        data = request.json
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        duration = data.get('duration')  # duration in seconds
        rating = data.get('rating', 3)
        location = data.get('location', 'bed')
        notes = data.get('notes', '')

        if not start_time or not end_time or duration is None:
            return jsonify({'error': 'Missing required fields'}), 400

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO naps (start_time, end_time, duration, rating, location, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (start_time, end_time, int(duration), int(rating), location, notes)
            )
            conn.commit()
            new_id = cursor.lastrowid
            
            cursor.execute('SELECT * FROM naps WHERE id = ?', (new_id,))
            row = cursor.fetchone()
            return jsonify(dict(row)), 211
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/naps/<int:nap_id>', methods=['PUT'])
def update_nap(nap_id):
    try:
        data = request.json
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        duration = data.get('duration')
        rating = data.get('rating')
        location = data.get('location')
        notes = data.get('notes')

        with get_db() as conn:
            cursor = conn.cursor()
            # Fetch existing to merge
            cursor.execute('SELECT * FROM naps WHERE id = ?', (nap_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Nap not found'}), 404
            
            current_data = dict(row)
            
            new_start = start_time if start_time is not None else current_data['start_time']
            new_end = end_time if end_time is not None else current_data['end_time']
            new_duration = int(duration) if duration is not None else current_data['duration']
            new_rating = int(rating) if rating is not None else current_data['rating']
            new_location = location if location is not None else current_data['location']
            new_notes = notes if notes is not None else current_data['notes']

            cursor.execute(
                '''
                UPDATE naps
                SET start_time = ?, end_time = ?, duration = ?, rating = ?, location = ?, notes = ?
                WHERE id = ?
                ''',
                (new_start, new_end, new_duration, new_rating, new_location, new_notes, nap_id)
            )
            conn.commit()
            
            cursor.execute('SELECT * FROM naps WHERE id = ?', (nap_id,))
            row = cursor.fetchone()
            return jsonify(dict(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/naps/<int:nap_id>', methods=['DELETE'])
def delete_nap(nap_id):
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM naps WHERE id = ?', (nap_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Nap not found'}), 404
            
            cursor.execute('DELETE FROM naps WHERE id = ?', (nap_id,))
            conn.commit()
            return jsonify({'message': 'Nap deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    # Runs on port 5000 by default, with host 0.0.0.0 to allow access in local dev environments
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
