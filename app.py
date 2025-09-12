import os
import re
import fitz  # PyMuPDF
import pandas as pd
from flask import Flask, render_template, request, redirect, flash

app = Flask(__name__)
app.secret_key = "resume_secret_key"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    """Check file extension"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(pdf_path):
    """Extract plain text from PDF"""
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text


def score_resume(text, keywords):
    """Count keyword matches in resume text"""
    score = 0
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            score += 1
    return score


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        job_description = request.form.get("job_description")
        resumes = request.files.getlist("resumes")

        if not job_description:
            flash("Please enter a job description")
            return redirect(request.url)

        keywords = re.findall(r"\w+", job_description)
        results = []
        raw_scores = []

        # Step 1: Score all resumes
        for file in resumes:
            if file and allowed_file(file.filename):
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
                file.save(filepath)

                resume_text = extract_text_from_pdf(filepath)
                score = score_resume(resume_text, keywords)
                raw_scores.append((file.filename, score))

        # Step 2: Normalize scores relative to best resume
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

        print("Rendering results.html with:", df.to_dict(orient="records"))  # Debug
        return render_template("results.html", results=df.to_dict(orient="records"))

    # GET request → load index.html
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)  # Force port 5000
