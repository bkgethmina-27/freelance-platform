import os
import secrets
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import mysql.connector

TIER_MULTIPLIERS = {
    1: 1.0,
    2: 2.5,
    3: 5.0
}

# Max number of simultaneously active gigs a freelancer can have at each tier.
# Kept low at Tier 1 so listings rotate between beginners instead of one
# person's gigs crowding out everyone else.
TIER_ACTIVE_GIG_CAP = {
    1: 2,
    2: 4,
    3: 8
}

DEFAULT_CATEGORIES = [
    ("Writing & Translation", 5.00),
    ("Graphic Design", 8.00),
    ("Web Development", 15.00),
    ("Data Entry & Admin", 3.00),
    ("Video Editing", 10.00),
    ("Digital Marketing", 8.00),
]

# Soft cap on how many active Tier-1 freelancers a category can hold at once.
# Once a category is full at Tier 1, new signups into that category are turned
# away (with a suggestion to pick another category) instead of flooding a
# category where there isn't enough demand to go around.
TIER_1_CATEGORY_CAP = 25

app = Flask(__name__, static_folder='static', static_url_path='/static')
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
                primary_category_id INT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                base_price DECIMAL(10,2) NOT NULL
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

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS gigs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                freelancer_id INT NOT NULL,
                category_id INT NOT NULL,
                title VARCHAR(255),
                price DECIMAL(10,2) NOT NULL,
                tier INT NOT NULL,
                status ENUM('active', 'completed') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (freelancer_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );
            """)

            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM categories")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    "INSERT INTO categories (name, base_price) VALUES (%s, %s)",
                    DEFAULT_CATEGORIES
                )
                conn.commit()

            # Migration safety net: these tables may already exist from a
            # previous deploy without the newer columns. ADD COLUMN is
            # wrapped individually so an existing column on one doesn't
            # block the others (MySQL errors instead of no-op'ing on
            # duplicates unless the server supports IF NOT EXISTS).
            migrations = [
                "ALTER TABLE users ADD COLUMN primary_category_id INT",
                "ALTER TABLE gigs ADD COLUMN category_id INT",
                "ALTER TABLE gigs ADD COLUMN status ENUM('active', 'completed') DEFAULT 'active'",
            ]
            for stmt in migrations:
                try:
                    cursor.execute(stmt)
                    conn.commit()
                except Exception:
                    conn.rollback()

            # Backfill any pre-existing rows that predate the categories
            # system so they aren't left with a NULL category forever.
            try:
                cursor.execute("SELECT id FROM categories ORDER BY id LIMIT 1")
                fallback = cursor.fetchone()
                if fallback:
                    cursor.execute("UPDATE users SET primary_category_id = %s WHERE primary_category_id IS NULL", (fallback[0],))
                    cursor.execute("UPDATE gigs SET category_id = %s WHERE category_id IS NULL", (fallback[0],))
                    conn.commit()
            except Exception:
                conn.rollback()
            cursor.close()
            conn.close()
            db_initialized = True
        except Exception:
            pass

# Explicit Root & Static Page File Routes
@app.route('/', methods=['GET'])
def home():
    return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def serve_root_files(filename):
    # If request is inside static folder or is an html page, serve directly from static directory
    if os.path.exists(os.path.join(app.static_folder, filename)):
        return send_from_directory(app.static_folder, filename)
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, base_price FROM categories ORDER BY name")
        categories = cursor.fetchall()

        # Attach current Tier-1 headcount so the frontend can show/gray-out
        # categories that are full for beginners at signup time.
        cursor.execute("""
            SELECT primary_category_id, COUNT(*) as count
            FROM users
            WHERE is_active = TRUE AND current_tier = 1 AND primary_category_id IS NOT NULL
            GROUP BY primary_category_id
        """)
        counts = {row['primary_category_id']: row['count'] for row in cursor.fetchall()}

        cursor.close()
        conn.close()

        for c in categories:
            c['tier1_count'] = counts.get(c['id'], 0)
            c['tier1_cap'] = TIER_1_CATEGORY_CAP
            c['tier1_full'] = c['tier1_count'] >= TIER_1_CATEGORY_CAP

        return jsonify(categories), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    whatsapp_number = data.get('whatsapp_number', '')
    category_id = data.get('category_id')

    if not full_name or not email or not password or not category_id:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Invalid category."}), 400

        # New freelancers start at Tier 1. Enforce the per-category beginner
        # cap here so one category doesn't get flooded with more beginners
        # than there's demand for.
        cursor.execute("""
            SELECT COUNT(*) as count FROM users
            WHERE is_active = TRUE AND current_tier = 1 AND primary_category_id = %s
        """, (category_id,))
        tier1_count = cursor.fetchone()['count']

        if tier1_count >= TIER_1_CATEGORY_CAP:
            cursor.close()
            conn.close()
            return jsonify({"error": "This category's beginner slots are full right now. Please pick another category or check back later."}), 409

        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, role, whatsapp_number, primary_category_id) VALUES (%s, %s, %s, 'freelancer', %s, %s)",
            (full_name, email, password, whatsapp_number, category_id)
        )
        conn.commit()
        user_id = cursor.lastrowid

        cursor.execute("INSERT INTO freelancer_sprints (user_id) VALUES (%s)", (user_id,))
        conn.commit()

        cursor.close()
        conn.close()
        return jsonify({"message": "User registered successfully!", "user_id": user_id}), 201
    except Exception as err:
        return jsonify({"error": str(err)}), 400

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
            return jsonify({
                "message": "Login successful!",
                "user": {
                    "id": user['id'],
                    "full_name": user['full_name'],
                    "email": user['email']
                }
            }), 200

        return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200

@app.route('/api/freelancers', methods=['GET'])
def get_freelancers():
    try:
        category_id = request.args.get('category_id')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT u.id, u.full_name, u.bio, u.current_tier, u.average_rating,
                   u.whatsapp_number, u.primary_category_id, c.name as category_name
            FROM users u
            LEFT JOIN categories c ON u.primary_category_id = c.id
            WHERE u.is_active = TRUE
        """
        params = ()
        if category_id:
            query += " AND u.primary_category_id = %s"
            params = (category_id,)
        query += " ORDER BY u.average_rating DESC"

        cursor.execute(query, params)
        freelancers = cursor.fetchall()

        cursor.close()
        conn.close()

        for f in freelancers:
            clean_number = "".join(filter(str.isdigit, f['whatsapp_number'] or ""))
            f['whatsapp_link'] = f"https://wa.me/{clean_number}" if clean_number else None

        # Fair-visibility rotation: rather than sorting strictly by tier (which
        # buries every beginner below every experienced freelancer, forever),
        # group by tier and interleave round-robin so each tier gets a turn
        # near the top of the feed. Within a tier, freelancers keep their
        # rating-sorted order from the query above.
        by_tier = {}
        for f in freelancers:
            by_tier.setdefault(f['current_tier'], []).append(f)

        interleaved = []
        tiers_desc = sorted(by_tier.keys(), reverse=True)
        max_len = max((len(v) for v in by_tier.values()), default=0)
        for i in range(max_len):
            for t in tiers_desc:
                if i < len(by_tier[t]):
                    interleaved.append(by_tier[t][i])

        return jsonify(interleaved), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sprints/status', methods=['GET'])
def get_automated_sprint_status():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT bio, whatsapp_number FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        day_1_done = bool(user and user.get('bio') and user.get('whatsapp_number'))

        cursor.execute("SELECT COUNT(*) as count FROM milestones WHERE freelancer_id = %s", (user_id,))
        milestones_created = cursor.fetchone()['count']
        day_2_done = milestones_created > 0

        cursor.execute("SELECT COUNT(*) as count FROM milestones WHERE freelancer_id = %s AND status = 'verified'", (user_id,))
        milestones_verified = cursor.fetchone()['count']
        day_3_done = milestones_verified > 0

        cursor.execute("""
            UPDATE freelancer_sprints 
            SET day_1_done = %s, day_2_done = %s, day_3_done = %s 
            WHERE user_id = %s
        """, (day_1_done, day_2_done, day_3_done, user_id))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "day_1": {"title": "Complete Profile & WhatsApp Number", "completed": day_1_done},
            "day_2": {"title": "Create First Work Milestone", "completed": day_2_done},
            "day_3": {"title": "Receive First Verified Review", "completed": day_3_done}
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/gigs/create', methods=['POST'])
def create_gig():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    title = data.get('title', 'Untitled Gig')
    price = data.get('price')
    category_id = data.get('category_id')

    if not category_id:
        return jsonify({"message": "Please select a category."}), 400

    try:
        price = float(price)
    except (TypeError, ValueError):
        return jsonify({"message": "Price must be a valid number."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT current_tier FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({"error": "User not found"}), 404

        tier = user['current_tier']

        cursor.execute("SELECT base_price FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
        if not category:
            cursor.close()
            conn.close()
            return jsonify({"message": "Invalid category."}), 400

        multiplier = TIER_MULTIPLIERS.get(tier, 1.0)
        minimum_price = float(category['base_price']) * multiplier

        if price < minimum_price:
            cursor.close()
            conn.close()
            return jsonify({"message": f"Price must be at least ${minimum_price:.2f} for this category at your Tier {tier}."}), 400

        # Enforce the active-listing cap so one freelancer's gigs (especially
        # at Tier 1) don't crowd out everyone else's visibility.
        cap = TIER_ACTIVE_GIG_CAP.get(tier, 999)
        cursor.execute(
            "SELECT COUNT(*) as count FROM gigs WHERE freelancer_id = %s AND status = 'active'",
            (user_id,)
        )
        active_count = cursor.fetchone()['count']
        if active_count >= cap:
            cursor.close()
            conn.close()
            return jsonify({"message": f"You've reached your limit of {cap} active gigs for Tier {tier}. Mark an existing gig as completed to post a new one."}), 409

        cursor.execute(
            "INSERT INTO gigs (freelancer_id, category_id, title, price, tier) VALUES (%s, %s, %s, %s, %s)",
            (user_id, category_id, title, price, tier)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Gig published successfully!", "tier": tier, "price": price}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/users/update', methods=['PUT'])
def update_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    password = data.get('password')
    full_name = data.get('full_name')
    whatsapp_number = data.get('whatsapp_number')
    bio = data.get('bio')

    if not password:
        return jsonify({"error": "Password confirmation is required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT password_hash FROM users WHERE id = %s AND is_active = TRUE", (user_id,))
        user = cursor.fetchone()

        if not user or user['password_hash'] != password:
            cursor.close()
            conn.close()
            return jsonify({"error": "Incorrect password."}), 401

        cursor.execute(
            "UPDATE users SET full_name = %s, whatsapp_number = %s, bio = %s WHERE id = %s",
            (full_name, whatsapp_number, bio, user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Profile updated successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/delete', methods=['DELETE'])
def delete_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    password = data.get('password')

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT password_hash FROM users WHERE id = %s AND is_active = TRUE", (user_id,))
        user = cursor.fetchone()

        if not user or user['password_hash'] != password:
            cursor.close()
            conn.close()
            return jsonify({"error": "Incorrect password."}), 401

        cursor.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        session.clear()

        return jsonify({"message": "Account deactivated."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/milestones/create', methods=['POST'])
def create_milestone():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    title = data.get('title')
    client_name = data.get('client_name', '')

    if not title:
        return jsonify({"error": "Milestone title is required."}), 400

    token = secrets.token_hex(16)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO milestones (freelancer_id, title, verification_token, client_name) VALUES (%s, %s, %s, %s)",
            (user_id, title, token, client_name)
        )
        conn.commit()
        cursor.close()
        conn.close()

        verification_url = f"{request.host_url.rstrip('/')}/verify.html?token={token}"
        return jsonify({"message": "Milestone token issued.", "verification_token": token, "verification_url": verification_url}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/milestones/verify/<token>', methods=['POST'])
def verify_milestone(token):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM milestones WHERE verification_token = %s", (token,))
        milestone = cursor.fetchone()

        if not milestone:
            cursor.close()
            conn.close()
            return jsonify({"error": "Invalid verification token."}), 404

        if milestone['status'] == 'verified':
            cursor.close()
            conn.close()
            return jsonify({"error": "This milestone has already been verified."}), 400

        cursor.execute("UPDATE milestones SET status = 'verified' WHERE id = %s", (milestone['id'],))
        conn.commit()

        freelancer_id = milestone['freelancer_id']
        cursor.execute(
            "SELECT COUNT(*) as count FROM milestones WHERE freelancer_id = %s AND status = 'verified'",
            (freelancer_id,)
        )
        total_verified = cursor.fetchone()['count']

        if total_verified >= 6:
            new_tier = 3
        elif total_verified >= 3:
            new_tier = 2
        else:
            new_tier = 1

        cursor.execute("UPDATE users SET current_tier = %s WHERE id = %s", (new_tier, freelancer_id))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "message": "Milestone verified.",
            "total_verified_milestones": total_verified,
            "updated_tier": new_tier
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)