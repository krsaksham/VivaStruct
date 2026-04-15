CREATE DATABASE vivasense;
USE vivasense;

CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    roll_no VARCHAR(50),
    total_marks INT,
    total_max INT,
    grade VARCHAR(10)
);

CREATE TABLE evaluations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    question TEXT,
    student_answer TEXT,
    marks INT,
    max_marks INT,
    semantic_score FLOAT,
    keyword_score FLOAT,
    final_score FLOAT
);

CREATE TABLE test_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    test_id VARCHAR(100),
    question TEXT,
    ideal_answer TEXT,
    max_marks INT
);
