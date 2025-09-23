import os
import re
import io
import fitz  # PyMuPDF
import pandas as pd
from flask import Flask, render_template, request, redirect, flash, session, url_for, send_file

app = Flask(__name__)
app.secret_key = "resume_secret_key"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text


def score_resume(text, keywords):
    score = 0
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            score += 1
    return score



# ---------------------- HOME (Protected) ----------------------
@app.route("/", methods=["GET", "POST"])
def upload_file():
    if "user" not in session:   # protect home
        return redirect(url_for("login"))

    username = session.get("user")  # get logged in user

    if request.method == "POST":
        job_description = request.form.get("job_description")
        resumes = request.files.getlist("resumes")

        if not job_description:
            flash("Please enter a job description")
            return redirect(request.url)

        keywords = re.findall(r"\w+", job_description)
        results = []
        raw_scores = []

        for file in resumes:
            if file and allowed_file(file.filename):
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
                file.save(filepath)

                resume_text = extract_text_from_pdf(filepath)
                score = score_resume(resume_text, keywords)
                raw_scores.append((file.filename, score))

        max_score = max([s for _, s in raw_scores]) if raw_scores else 1

        for filename, score in raw_scores:
            normalized = round(score / max_score, 4) if max_score > 0 else 0

            if normalized >= 0.7:
                color = "bg-success"
            elif normalized >= 0.4:
                color = "bg-warning"
            else:
                color = "bg-danger"

            results.append({
                "Resume": filename,
                "Score": normalized,
                "Color": color
            })

        df = pd.DataFrame(results).sort_values(by="Score", ascending=False).reset_index(drop=True)

        # Save results to session for export
        session["results"] = df.to_dict(orient="records")

        return render_template("results.html", results=session["results"], username=username)

    return render_template("index.html", username=username)


# ---------------------- EXPORT RESULTS ----------------------
@app.route("/export")
def export():
    if "results" not in session:
        flash("No results available to export.")
        return redirect(url_for("upload_file"))

    df = pd.DataFrame(session["results"])

    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="resume_scores.csv"
    )


# ---------------------- LOGIN ----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # TODO: Replace with real authentication
        if email == "admin@test.com" and password == "admin":
            session["user"] = email  # set session
            return redirect(url_for("upload_file"))
        else:
            flash("Invalid credentials, try again.")
            return redirect(url_for("login"))

    return render_template("login.html")


# ---------------------- SIGNUP ----------------------
import re

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        role = request.form.get("role")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # ✅ Password validation (backend)
        if not re.match(r'^(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,}$', password):
            flash("Password must be at least 8 characters, include one number and one special character.")
            return redirect(url_for("signup"))

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for("signup"))

        if users_collection.find_one({"email": email}):
            flash("Email already registered!")
            return redirect(url_for("signup"))

        hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
        users_collection.insert_one({
            "name": name,
            "email": email,
            "role": role,
            "password": hashed_pw
        })

        flash("Account created successfully! Please log in.")
        return redirect(url_for("login"))

    return render_template("signup.html")

# ---------------------- LOGOUT ----------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
