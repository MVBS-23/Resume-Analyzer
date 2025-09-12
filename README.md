
# AI Resume Analyzer (Flask + TF-IDF)

A simple Flask web app that lets you upload multiple **PDF** resumes and paste a **Job Description (JD)**. 
It extracts text using **PyMuPDF**, computes **TF-IDF** vectors, and ranks resumes by **cosine similarity** to the JD.

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the app**
   ```bash
   python app.py
   ```

3. Open your browser at http://127.0.0.1:5000/

4. Paste your JD, upload one or more PDF resumes, and click **Analyze Resumes**.

## Notes

- Results can be downloaded as a CSV from the results page.
- Uploaded files and the last results CSV are stored in the `uploads/` folder.
- This prototype uses **TF-IDF**; for better semantic understanding, swap in **Sentence Transformers** embeddings later.

## Folder Structure

```text
ResumeAnalyzerFlask/
├─ app.py
├─ requirements.txt
├─ README.md
├─ uploads/        # uploaded PDFs + last_results.csv
└─ templates/
   ├─ index.html
   └─ results.html
```
