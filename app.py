import os
import re
import io
import fitz  # PyMuPDF
import pandas as pd
from flask import Flask, render_template, request, redirect, flash, session, url_for, send_file, jsonify
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from datetime import datetime

app = Flask(__name__)
app.secret_key = "resume_secret_key"
bcrypt = Bcrypt(app)

# ---------------------- MongoDB Setup ----------------------
client = MongoClient("mongodb://localhost:27017/")  # Replace with Atlas URI if needed
db = client["resume_analyzer"]
users_collection = db["users"]
results_collection = db["results"]

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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


# ---------------------- INDEX (PUBLIC ENTRY) ----------------------
@app.route("/", methods=["GET"])
def index():
    username = session.get("user")
    restore = request.args.get("resume_restore")
    saved_form = session.pop("pending_form", None) if restore else None
    return render_template("index.html", username=username, saved_form=saved_form)


# ---------------------- ANALYZE (Protected Processing) ----------------------
# ---------------------- ANALYZE (Protected Processing) ----------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        # If user not logged in, tell frontend to show login modal
        if "user" not in session:
            print("⚠️ User not logged in — returning login_required")
            return jsonify({"status": "login_required"})

        username = session.get("user")
        email = session.get("email")

        job_description = request.form.get("job_description")
        resumes = request.files.getlist("resumes")

        if not job_description:
            print("⚠️ No job description provided")
            return jsonify({"status": "error", "message": "Please enter a job description"})

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
            color = (
                "bg-success" if normalized >= 0.7
                else "bg-warning" if normalized >= 0.4
                else "bg-danger"
            )
            results.append({
                "Resume": filename,
                "Score": normalized,
                "Color": color
            })

        df = pd.DataFrame(results).sort_values(by="Score", ascending=False).reset_index(drop=True)
        session["results"] = df.to_dict(orient="records")

        # Save results to DB
        results_collection.insert_one({
            "email": email,
            "username": username,
            "job_description": job_description,
            "results": session["results"],
            "timestamp": datetime.utcnow()
        })

        print("✅ Analysis complete for user:", username)
        return jsonify({"status": "success", "redirect": url_for("results_page")})

    except Exception as e:
        print("❌ Error in /analyze:", str(e))
        return jsonify({"status": "error", "message": str(e)})



# ---------------------- RESULTS PAGE ----------------------
@app.route("/results")
def results_page():
    if "results" not in session:
        flash("No results found. Please analyze again.")
        return redirect(url_for("index"))
    return render_template("results.html", results=session["results"], username=session.get("user"))


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

        color = (
            "bg-success" if normalized >= 0.7
            else "bg-warning" if normalized >= 0.4
            else "bg-danger"
        )

        results.append({
            "Resume": filename,
            "Score": normalized,
            "Color": color
        })

    df = pd.DataFrame(results).sort_values(by="Score", ascending=False).reset_index(drop=True)

    session["results"] = df.to_dict(orient="records")

    # Save results history in MongoDB
    results_collection.insert_one({
        "email": email,
        "username": username,
        "job_description": job_description,
        "results": session["results"],
        "timestamp": datetime.utcnow()
    })

    return render_template("results.html", results=session["results"], username=username)


# ---------------------- EXPORT RESULTS ----------------------
@app.route("/export")
def export():
    if "results" not in session:
        flash("No results available to export.")
        return redirect(url_for("index"))

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

        user = users_collection.find_one({"email": email})
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = user["name"]
            session["email"] = user["email"]
            session["role"] = user.get("role", "User")

            # ✅ Restore previous form data if present
            if session.get("pending_form"):
                flash("Welcome back, " + user["name"] + "! You can continue your analysis.")
                return redirect(url_for("index", resume_restore="1"))
            else:
                flash("Welcome back, " + user["name"] + "!")
                return redirect(url_for("index"))
        else:
            flash("Invalid email or password.")
            return redirect(url_for("login"))

    return render_template("login.html")


# ---------------------- STORE FORM TEMPORARILY ----------------------
@app.route("/store_form", methods=["POST"])
def store_form():
    """
    Temporarily saves job description and filenames in session
    if the user is not logged in.
    """
    job_description = request.form.get("job_description")
    filenames = [f.filename for f in request.files.getlist("resumes")]
    session["pending_form"] = {"job_description": job_description, "filenames": filenames}  
    return jsonify({"status": "stored"})   


# ---------------------- SIGNUP ----------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        role = request.form.get("role")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not re.match(r'^(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,}$', password):
            flash("Password must include one number and one special character.")
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
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
