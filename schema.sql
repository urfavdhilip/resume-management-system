-- Run against the MySQL database selected in .env.
-- The application also creates these tables automatically at startup.
CREATE TABLE IF NOT EXISTS admins (
  admin_id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS candidates (
  candidate_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(180) NOT NULL,
  email VARCHAR(180) NOT NULL,
  phone VARCHAR(40), address TEXT, summary TEXT,
  photo_file VARCHAR(255), resume_file VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_candidate_name (full_name), INDEX idx_candidate_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS education (
  education_id INT AUTO_INCREMENT PRIMARY KEY,
  candidate_id INT NOT NULL,
  degree VARCHAR(180) NOT NULL, institution VARCHAR(220) NOT NULL,
  field_of_study VARCHAR(180), start_year SMALLINT, end_year SMALLINT,
  grade VARCHAR(40), details TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_education_candidate FOREIGN KEY (candidate_id)
    REFERENCES candidates(candidate_id) ON DELETE CASCADE,
  INDEX idx_education_candidate (candidate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS skills (
  skill_id INT AUTO_INCREMENT PRIMARY KEY,
  candidate_id INT NOT NULL, skill_name VARCHAR(120) NOT NULL,
  category ENUM('Technical','Soft','Tools','Language','Other') DEFAULT 'Technical',
  proficiency ENUM('Beginner','Intermediate','Advanced','Expert') DEFAULT 'Intermediate',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_skill_candidate FOREIGN KEY (candidate_id)
    REFERENCES candidates(candidate_id) ON DELETE CASCADE,
  UNIQUE KEY uq_candidate_skill (candidate_id, skill_name),
  INDEX idx_skill_candidate (candidate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
