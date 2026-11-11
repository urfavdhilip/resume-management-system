"""MySQL connection and schema initialization for Resume Management System."""
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Return a fresh connection per request; never share global connections."""
    database = os.getenv("DB_NAME", "resume_management")
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=database,
        connection_timeout=10,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        autocommit=False,
    )
    conn.ping(reconnect=True, attempts=3, delay=1)
    return conn


def initialize_database():
    """Create the application's tables if absent; never drops user data."""
    conn = get_db_connection()
    cur = conn.cursor()
    statements = [
        """CREATE TABLE IF NOT EXISTS admins (
            admin_id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS candidates (
            candidate_id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(180) NOT NULL,
            email VARCHAR(180) NOT NULL,
            phone VARCHAR(40) NULL,
            address TEXT NULL,
            summary TEXT NULL,
            photo_file VARCHAR(255) NULL,
            resume_file VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_candidate_name (full_name),
            INDEX idx_candidate_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS education (
            education_id INT AUTO_INCREMENT PRIMARY KEY,
            candidate_id INT NOT NULL,
            degree VARCHAR(180) NOT NULL,
            institution VARCHAR(220) NOT NULL,
            field_of_study VARCHAR(180) NULL,
            start_year SMALLINT NULL,
            end_year SMALLINT NULL,
            grade VARCHAR(40) NULL,
            details TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_education_candidate FOREIGN KEY (candidate_id)
                REFERENCES candidates(candidate_id) ON DELETE CASCADE,
            INDEX idx_education_candidate (candidate_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS skills (
            skill_id INT AUTO_INCREMENT PRIMARY KEY,
            candidate_id INT NOT NULL,
            skill_name VARCHAR(120) NOT NULL,
            category ENUM('Technical','Soft','Tools','Language','Other') DEFAULT 'Technical',
            proficiency ENUM('Beginner','Intermediate','Advanced','Expert') DEFAULT 'Intermediate',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_skill_candidate FOREIGN KEY (candidate_id)
                REFERENCES candidates(candidate_id) ON DELETE CASCADE,
            UNIQUE KEY uq_candidate_skill (candidate_id, skill_name),
            INDEX idx_skill_candidate (candidate_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]
    try:
        for statement in statements:
            cur.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
