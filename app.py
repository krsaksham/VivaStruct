from flask import Flask, render_template, request, redirect
from sentence_transformers import SentenceTransformer, util
import mysql.connector

app = Flask(__name__)

# Load AI model
model = SentenceTransformer('all-MiniLM-L6-v2')

# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="your_password",  # 🔴 changed for safety
    database="vivasense",
    port=3306
)
cursor = db.cursor()

# Store tests
tests = {}

# ---------------- AI Evaluation ----------------
def evaluate_answer(ideal, student, max_marks):
    ideal_emb = model.encode(ideal, convert_to_tensor=True)
    student_emb = model.encode(student, convert_to_tensor=True)

    similarity = util.cos_sim(ideal_emb, student_emb)
    score = float(similarity[0][0])

    if score < 0.35:
        return 0, 0

    marks = round(score * max_marks)
    return marks, round(score, 2)


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------------- EXAMINER ----------------
@app.route("/examiner", methods=["GET", "POST"])
def examiner():

    if request.method == "POST":
        test_id = request.form.get("test_id")
        question = request.form.get("question")
        ideal = request.form.get("ideal")
        max_marks = request.form.get("max_marks")

        if test_id not in tests:
            tests[test_id] = []

        tests[test_id].append({
            "question": question,
            "ideal": ideal,
            "max_marks": int(max_marks)
        })

    return render_template("examiner.html", tests=tests)


# DELETE QUESTION
@app.route("/delete_question/<test_id>/<int:index>")
def delete_question(test_id, index):
    if test_id in tests and 0 <= index < len(tests[test_id]):
        tests[test_id].pop(index)
    return redirect("/examiner")


# ---------------- STUDENT ----------------
@app.route("/student", methods=["GET", "POST"])
def student():

    results = []
    total_marks = 0
    total_max = 0
    selected_test = []

    if request.method == "POST":
        test_id = request.form.get("test_id")

        if test_id in tests:
            selected_test = tests[test_id]

        name = request.form.get("name")
        roll = request.form.get("roll")

        for i, q in enumerate(selected_test):
            answer = request.form.get(f"answer_{i}")

            if answer:
                marks, score = evaluate_answer(
                    q["ideal"],
                    answer,
                    q["max_marks"]
                )

                results.append({
                    "question": q["question"],
                    "marks": marks,
                    "max_marks": q["max_marks"],
                    "score": score
                })

                total_marks += marks
                total_max += q["max_marks"]

        if name and roll:
            cursor.execute(
                "INSERT INTO students (name, roll_no, total_marks, total_max) VALUES (%s,%s,%s,%s)",
                (name, roll, total_marks, total_max)
            )
            db.commit()

            student_id = cursor.lastrowid

            for i, r in enumerate(results):
                cursor.execute(
                    "INSERT INTO evaluations (student_id, question, student_answer, marks, max_marks) VALUES (%s,%s,%s,%s,%s)",
                    (
                        student_id,
                        selected_test[i]["question"],
                        request.form.get(f"answer_{i}"),
                        r["marks"],
                        r["max_marks"]
                    )
                )
            db.commit()

    return render_template(
        "student.html",
        tests=tests,
        questions=selected_test,
        results=results,
        total_marks=total_marks,
        total_max=total_max
    )


# ---------------- RECORDS ----------------
@app.route("/records")
def records():
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    return render_template("records.html", students=students)


# DELETE RECORD
@app.route("/delete_record/<int:id>")
def delete_record(id):
    cursor.execute("DELETE FROM evaluations WHERE student_id=%s", (id,))
    cursor.execute("DELETE FROM students WHERE id=%s", (id,))
    db.commit()
    return redirect("/records")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)