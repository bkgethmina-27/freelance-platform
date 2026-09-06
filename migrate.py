import os
import mysql.connector

# Credentials come from environment variables - never hardcode them here.
# Set these before running the script, e.g.:
#   export DB_HOST=...
#   export DB_PORT=...
#   export DB_USER=...
#   export DB_PASSWORD=...
#   export DB_NAME=...
aiven_config = {
    'host': os.environ['DB_HOST'],
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ['DB_USER'],
    'password': os.environ['DB_PASSWORD'],
    'database': os.environ['DB_NAME'],
    'ssl_disabled': False
}

# Note: app.py already creates and migrates all tables automatically on
# first request (see ensure_db_initialized), including users, categories,
# freelancer_sprints, milestones, and gigs, plus the column migrations for
# older deployments. This script is only useful for a one-off manual setup
# or inspection outside of running the Flask app, and its schema below is
# kept intentionally minimal/legacy - prefer letting app.py manage the
# schema.

conn = mysql.connector.connect(**aiven_config)
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
    client_id INT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    verification_token VARCHAR(64) UNIQUE NOT NULL,
    status ENUM('pending', 'verified') DEFAULT 'pending',
    client_confirmed BOOLEAN DEFAULT FALSE,
    freelancer_confirmed BOOLEAN DEFAULT FALSE,
    client_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (freelancer_id) REFERENCES users(id) ON DELETE CASCADE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS portfolios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    freelancer_id INT NOT NULL,
    project_title VARCHAR(150),
    project_url VARCHAR(255),
    description TEXT,
    FOREIGN KEY (freelancer_id) REFERENCES users(id) ON DELETE CASCADE
);
""")

conn.commit()
cursor.close()
conn.close()

print("Cloud database schema created successfully on Aiven!")
