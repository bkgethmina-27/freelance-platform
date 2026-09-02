import os
import secrets
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import mysql.connector

# Tier Minimum Pricing Thresholds
TIER_MINIMUM_PRICES = {
    1: 0.00,    # Tier 1 (Rising Talent): $0 floor allowed
    2: 25.00,   # Tier 2 (Verified Pro): Minimum $25 floor
    3: 75.00    # Tier 3 (Top Performer): Minimum $75 floor
}

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_marketplace_key_change_in_production')
CORS(app, supports_credentials=True)

db_initialized = False

def get_db_connection():
    host = os.getenv('DB_HOST', 'localhost')
    user = os.getenv('DB_USER', 'root')
    password = os.getenv('DB_PASSWORD', '')
    database = os.getenv('DB_NAME', 'freelance_db')
    port = int(os.getenv('DB_PORT', 3306))

    if host in ['localhost', '127.0.0.1']:
        return mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port
        )
    else:
        return mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            ssl_disabled=False
        )

@app.before_request
def ensure_db_initialized():
    global db_initialized
    if not db_initialized:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('freelancer', 'client') DEFAULT 'freelancer',
                current_tier INT DEFAULT 1,
                average_rating DECIMAL(3,2) DEFAULT 0.00,
                whatsapp_number VARCHAR(20),
                bio TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS freelancer_sprints (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                current_day INT DEFAULT 1,
                day_1_done BOOLEAN DEFAULT FALSE,
                day_2_done BOOLEAN DEFAULT FALSE,
                day_3_done BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS milestones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                freelancer_id INT NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                verification_token VARCHAR(64) UNIQUE NOT NULL,
                status ENUM('pending', 'verified') DEFAULT 'pending',
                client_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (freelancer_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """)

            conn.commit()
            cursor.close()
            conn.close()
            db_initialized = True
            print("Successfully connected and initialized database tables.")
        except Exception as e:
            print(f"DATABASE INITIALIZATION ERROR: {e}")

# Static File Routing
@app.route('/', methods=['GET'])
def home():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# 1. Registration Endpoint
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'freelancer')
    whatsapp_number = data.get('whatsapp_number', '')

    if not full_name or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "INSERT INTO users (full_name, email, password_hash, role, whatsapp_number) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, (full_name, email, password, role, whatsapp_number))
        conn.commit()
        user_id = cursor.lastrowid
        
        if role == 'freelancer':
            cursor.execute("INSERT INTO freelancer_sprints (user_id) VALUES (%s)", (user_id,))
            conn.commit()

        cursor.close()
        conn.close()
        return jsonify({"message": "User registered successfully!", "user_id": user_id}), 201
    except Exception as err:
        print(f"Register error: {err}")
        return jsonify({"error": str(err)}), 400

# 2. Login Endpoint
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND is_active = TRUE", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and user['password_hash'] == password:
            session['user_id'] = user['id']
            session['role'] = user['role']
            return jsonify({
                "message": "Login successful!",
                "user": {
                    "id": user['id'],
                    "full_name": user['full_name'],
                    "email": user['email'],
                    "role": user['role']
                }
            }), 200

        return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": str(e)}), 500

# 3. Active Session Endpoint
@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, full_name, email, role, whatsapp_number, bio, current_tier FROM users WHERE id = %s AND is_active = TRUE", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            session.clear()
            return jsonify({"error": "User not found"}), 404

        return jsonify(user), 200
    except Exception as e:
        print(f"Me endpoint error: {e}")
        return jsonify({"error": str(e)}), 500

# 4. Logout Endpoint
@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200

# 5. Freelancer Marketplace List
@app.route('/api/freelancers', methods=['GET'])
def get_freelancers():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id, full_name, bio, current_tier, average_rating, whatsapp_number FROM users WHERE role = 'freelancer' AND is_active = TRUE ORDER BY current_tier DESC, average_rating DESC")
        freelancers = cursor.fetchall()
        
        cursor.close()
        conn.close()

        for f in freelancers:
            clean_number = "".join(filter(str.isdigit, f['whatsapp_number'] or ""))
            f['whatsapp_link'] = f"https://wa.me/{clean_number}" if clean_number else None

        return jsonify(freelancers), 200
    except Exception as e:
        print(f"FREELANCERS API ERROR: {e}")
        return jsonify({"error": f"Database query failed: {str(e)}"}), 500

# 6. Update Profile
@app.route('/api/users/update', methods=['PUT'])
def update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    data = request.json
    confirm_password = data.get('password')
    full_name = data.get('full_name')
    bio = data.get('bio')
    whatsapp_number = data.get('whatsapp_number')

    if not confirm_password:
        return jsonify({"error": "Password confirmation required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user or user['password_hash'] != confirm_password:
            cursor.close()
            conn.close()
            return jsonify({"error": "Incorrect password."}), 403

        update_query = """
            UPDATE users 
            SET full_name = COALESCE(%s, full_name),
                bio = COALESCE(%s, bio),
                whatsapp_number = COALESCE(%s, whatsapp_number)
            WHERE id = %s
        """
        cursor.execute(update_query, (full_name, bio, whatsapp_number, user_id))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({"message": "Profile updated successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 7. Soft Delete Profile
@app.route('/api/users/delete', methods=['DELETE'])
def delete_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    data = request.json
    confirm_password = data.get('password')

    if not confirm_password:
        return jsonify({"error": "Password confirmation required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user or user['password_hash'] != confirm_password:
            cursor.close()
            conn.close()
            return jsonify({"error": "Incorrect password."}), 403

        cursor.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
        conn.commit()

        cursor.close()
        conn.close()
        session.clear()

        return jsonify({"message": "Account deactivated successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 8. Milestone Creation
@app.route('/api/milestones/create', methods=['POST'])
def create_milestone():
    user_id = session.get('user_id')
    data = request.json
    freelancer_id = user_id or data.get('freelancer_id')
    title = data.get('title')
    client_name = data.get('client_name', '')

    if not freelancer_id or not title:
        return jsonify({"error": "Missing title or freelancer ID"}), 400

    token = secrets.token_hex(16)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO milestones (freelancer_id, title, client_name, verification_token, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """
        cursor.execute(query, (freelancer_id, title, client_name, token))
        conn.commit()
        milestone_id = cursor.lastrowid
        cursor.close()
        conn.close()

        base_url = request.host_url.rstrip('/')
        return jsonify({
            "message": "Milestone created successfully!",
            "milestone_id": milestone_id,
            "verification_token": token,
            "verification_url": f"{base_url}/verify.html?token={token}"
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 9. Verification & Tier Auto-Promotion
@app.route('/api/milestones/verify/<token>', methods=['GET', 'POST'])
def verify_milestone(token):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM milestones WHERE verification_token = %s", (token,))
        milestone = cursor.fetchone()

        if not milestone:
            cursor.close()
            conn.close()
            return jsonify({"error": "Invalid token"}), 404

        if milestone['status'] == 'verified':
            cursor.close()
            conn.close()
            return jsonify({"message": "Milestone already verified!"}), 200

        cursor.execute("UPDATE milestones SET status = 'verified' WHERE verification_token = %s", (token,))
        conn.commit()

        freelancer_id = milestone['freelancer_id']
        cursor.execute("SELECT COUNT(*) as verified_count FROM milestones WHERE freelancer_id = %s AND status = 'verified'", (freelancer_id,))
        count_result = cursor.fetchone()
        verified_count = count_result['verified_count']

        new_tier = 1
        if verified_count >= 15:
            new_tier = 3
        elif verified_count >= 4:
            new_tier = 2

        cursor.execute("UPDATE users SET current_tier = %s WHERE id = %s", (new_tier, freelancer_id))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "message": "Milestone verified!",
            "total_verified_milestones": verified_count,
            "updated_tier": new_tier
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 10. Service Gig Creation & Price Floor Check
@app.route('/api/gigs/create', methods=['POST'])
def create_gig():
    user_id = session.get('user_id')
    data = request.json
    freelancer_id = user_id or data.get('freelancer_id')
    proposed_price = float(data.get('price', 0))

    if not freelancer_id:
        return jsonify({"error": "User not authenticated"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT current_tier FROM users WHERE id = %s", (freelancer_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        user_tier = user['current_tier']
        minimum_allowed = TIER_MINIMUM_PRICES.get(user_tier, 0.00)

        if proposed_price < minimum_allowed:
            return jsonify({
                "error": "Price below tier threshold",
                "message": f"Tier {user_tier} minimum rate is ${minimum_allowed:.2f}."
            }), 400

        return jsonify({
            "message": "Gig price accepted!",
            "tier": user_tier,
            "price": proposed_price
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 11. Complete Sprint Day
@app.route('/api/sprints/complete-day', methods=['POST'])
def complete_sprint_day():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    day_number = data.get('day')

    if day_number not in [1, 2, 3]:
        return jsonify({"error": "Invalid day"}), 400

    try:
        column_name = f"day_{day_number}_done"
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = f"UPDATE freelancer_sprints SET {column_name} = TRUE, current_day = %s + 1 WHERE user_id = %s"
        cursor.execute(query, (day_number, user_id))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": f"Day {day_number} marked done!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 12. Retrieve Sprint Status
@app.route('/api/sprints/me', methods=['GET'])
def get_sprint_progress():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM freelancer_sprints WHERE user_id = %s", (user_id,))
        sprint = cursor.fetchone()
        cursor.close()
        conn.close()

        if not sprint:
            return jsonify({"error": "Sprint not found"}), 404

        return jsonify(sprint), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)