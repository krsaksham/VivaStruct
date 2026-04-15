from difflib import SequenceMatcher

import mysql.connector
from flask import Flask, redirect, render_template, request
from sentence_transformers import SentenceTransformer, util

app = Flask(__name__)

model = None

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="your password",
    database="vivasense",
    port=3306,
)
cursor = db.cursor()


def get_model():
    global model

    if model is None:
        try:
            model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            model = False

    return model if model is not False else None


def fallback_similarity(ideal, student):
    ideal_text = (ideal or "").strip().lower()
    student_text = (student or "").strip().lower()

    if not ideal_text or not student_text:
        return 0.0

    word_overlap = 0.0
    ideal_words = set(ideal_text.split())
    student_words = set(student_text.split())
    if ideal_words or student_words:
        word_overlap = len(ideal_words & student_words) / len(ideal_words | student_words)

    sequence_score = SequenceMatcher(None, ideal_text, student_text).ratio()
    return round((word_overlap + sequence_score) / 2, 2)


def initialize_database():
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100),
            roll_no VARCHAR(50),
            total_marks INT,
            total_max INT,
            grade VARCHAR(10)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS evaluations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT,
            question TEXT,
            student_answer TEXT,
            marks INT,
            max_marks INT,
            semantic_score FLOAT,
            keyword_score FLOAT,
            final_score FLOAT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS test_questions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            test_id VARCHAR(100),
            question TEXT,
            ideal_answer TEXT,
            max_marks INT
        )
        """
    )

    optional_alters = [
        "ALTER TABLE students ADD COLUMN grade VARCHAR(10)",
        "ALTER TABLE evaluations ADD COLUMN semantic_score FLOAT",
        "ALTER TABLE evaluations ADD COLUMN keyword_score FLOAT",
        "ALTER TABLE evaluations ADD COLUMN final_score FLOAT",
    ]
    for query in optional_alters:
        try:
            cursor.execute(query)
        except mysql.connector.Error:
            pass

    db.commit()


def get_tests():
    cursor.execute(
        """
        SELECT id, test_id, question, ideal_answer, max_marks
        FROM test_questions
        ORDER BY test_id, id
        """
    )
    rows = cursor.fetchall()
    tests = {}

    for question_id, test_id, question, ideal_answer, max_marks in rows:
        tests.setdefault(test_id, []).append(
            {
                "id": question_id,
                "question": question,
                "ideal": ideal_answer,
                "max_marks": max_marks,
            }
        )

    return tests


def get_test_questions(test_id):
    cursor.execute(
        """
        SELECT id, question, ideal_answer, max_marks
        FROM test_questions
        WHERE test_id = %s
        ORDER BY id
        """,
        (test_id,),
    )
    rows = cursor.fetchall()
    return [
        {
            "id": row[0],
            "question": row[1],
            "ideal": row[2],
            "max_marks": row[3],
        }
        for row in rows
    ]


def keyword_score(ideal, student):
    ideal_words = set((ideal or "").lower().split())
    student_words = set((student or "").lower().split())

    if not ideal_words:
        return 0.0

    return round(len(ideal_words & student_words) / len(ideal_words), 2)


def calculate_grade(total_marks, total_max):
    if total_max == 0:
        return "F"

    percentage = (total_marks / total_max) * 100
    if percentage >= 90:
        return "A+"
    if percentage >= 80:
        return "A"
    if percentage >= 70:
        return "B+"
    if percentage >= 60:
        return "B"
    if percentage >= 50:
        return "C"
    return "F"


def evaluate_answer(ideal, student, max_marks):
    loaded_model = get_model()

    if loaded_model is not None:
        ideal_emb = loaded_model.encode(ideal, convert_to_tensor=True)
        student_emb = loaded_model.encode(student, convert_to_tensor=True)
        similarity = util.cos_sim(ideal_emb, student_emb)
        semantic_score = float(similarity[0][0])
    else:
        semantic_score = fallback_similarity(ideal, student)

    kw_score = keyword_score(ideal, student)
    final_score = round((0.6 * semantic_score) + (0.4 * kw_score), 2)

    if final_score < 0.35:
        return 0, round(semantic_score, 2), kw_score, final_score

    marks = round(final_score * max_marks)
    return marks, round(semantic_score, 2), kw_score, final_score


initialize_database()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/examiner", methods=["GET", "POST"])
def examiner():
    if request.method == "POST":
        test_id = request.form.get("test_id", "").strip()
        question = request.form.get("question", "").strip()
        ideal = request.form.get("ideal", "").strip()
        max_marks = request.form.get("max_marks", "").strip()

        if test_id and question and ideal and max_marks:
            cursor.execute(
                """
                INSERT INTO test_questions (test_id, question, ideal_answer, max_marks)
                VALUES (%s, %s, %s, %s)
                """,
                (test_id, question, ideal, int(max_marks)),
            )
            db.commit()

    return render_template("examiner.html", tests=get_tests())


@app.route("/delete_question/<int:question_id>")
def delete_question(question_id):
    cursor.execute("DELETE FROM test_questions WHERE id = %s", (question_id,))
    db.commit()
    return redirect("/examiner")


@app.route("/student", methods=["GET", "POST"])
def student():
    tests = get_tests()
    results = []
    total_marks = 0
    total_max = 0
    selected_test = []
    grade = None
    selected_test_id = ""
    name = ""
    roll = ""

    if request.method == "POST":
        selected_test_id = request.form.get("test_id", "").strip()
        name = request.form.get("name", "").strip()
        roll = request.form.get("roll", "").strip()
        action = request.form.get("action", "load")

        if selected_test_id:
            selected_test = get_test_questions(selected_test_id)

        if action == "submit":
            for i, q in enumerate(selected_test):
                answer = request.form.get(f"answer_{i}", "").strip()
                if not answer:
                    continue

                marks, semantic_score, kw_score, final_score = evaluate_answer(
                    q["ideal"], answer, q["max_marks"]
                )

                results.append(
                    {
                        "question": q["question"],
                        "marks": marks,
                        "max_marks": q["max_marks"],
                        "semantic_score": semantic_score,
                        "keyword_score": kw_score,
                        "final_score": final_score,
                        "student_answer": answer,
                    }
                )
                total_marks += marks
                total_max += q["max_marks"]

            grade = calculate_grade(total_marks, total_max)

            if name and roll:
                cursor.execute(
                    """
                    INSERT INTO students (name, roll_no, total_marks, total_max, grade)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (name, roll, total_marks, total_max, grade),
                )
                db.commit()
                student_id = cursor.lastrowid

                for result in results:
                    cursor.execute(
                        """
                        INSERT INTO evaluations
                        (student_id, question, student_answer, marks, max_marks, semantic_score, keyword_score, final_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            student_id,
                            result["question"],
                            result["student_answer"],
                            result["marks"],
                            result["max_marks"],
                            result["semantic_score"],
                            result["keyword_score"],
                            result["final_score"],
                        ),
                    )
                db.commit()

    return render_template(
        "student.html",
        tests=tests,
        questions=selected_test,
        results=results,
        total_marks=total_marks,
        total_max=total_max,
        grade=grade,
        selected_test_id=selected_test_id,
        student_name=name,
        student_roll=roll,
    )


@app.route("/records")
def records():
    cursor.execute(
        "SELECT id, name, roll_no, total_marks, total_max, grade FROM students ORDER BY id DESC"
    )
    students = cursor.fetchall()
    cursor.execute(
        """
        SELECT student_id, question, student_answer, marks, max_marks, semantic_score, keyword_score, final_score
        FROM evaluations
        ORDER BY id DESC
        """
    )
    evaluation_rows = cursor.fetchall()
    evaluations_by_student = {}

    for row in evaluation_rows:
        student_id = row[0]
        evaluations_by_student.setdefault(student_id, []).append(
            {
                "question": row[1],
                "student_answer": row[2],
                "marks": row[3],
                "max_marks": row[4],
                "semantic_score": row[5],
                "keyword_score": row[6],
                "final_score": row[7],
            }
        )

    return render_template(
        "records.html",
        students=students,
        evaluations_by_student=evaluations_by_student,
    )


@app.route("/delete_record/<int:record_id>")
def delete_record(record_id):
    cursor.execute("DELETE FROM evaluations WHERE student_id = %s", (record_id,))
    cursor.execute("DELETE FROM students WHERE id = %s", (record_id,))
    db.commit()
    return redirect("/records")


if __name__ == "__main__":
    app.run(debug=True)
