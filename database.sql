CREATE DATABASE vivasense;
USE vivasense;

CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    roll_no VARCHAR(50),
    total_marks INT,
    total_max INT
);

CREATE TABLE evaluations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    question TEXT,
    student_answer TEXT,
    marks INT,
    max_marks INT
);