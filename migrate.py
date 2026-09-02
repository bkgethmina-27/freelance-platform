import mysql.connector

# Replace YOUR_AIVEN_PASSWORD with your actual Aiven password from the screen
aiven_config = {
    'host': 'mysql-18dbb4b7-bk-1121.l.aivencloud.com',
    'port': 11757,
    'user': 'avnadmin',
    'password': 'AVNS_NzqcAHn6qe-Syt7a21-',
    'database': 'defaultdb',
    'ssl_disabled': False
}

conn = mysql.connector.connect(**aiven_config)
cursor = conn.cursor()

# Create tables in Aiven cloud database
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