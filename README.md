# Automated Job Application Tracker (ETL Pipeline)

An automated end-to-end data pipeline that extracts job application emails from Gmail, parses structured telemetry using the Google Gemini LLM, and intelligently upserts records into Google Sheets using a composite primary key.

---

## Architecture & Workflow

* **Extract (Gmail API):** Scans the primary Gmail inbox using targeted queries, capturing both read and unread status updates over a rolling 24-hour window while filtering out marketing and crypto platform noise.
* **Transform (Google Gemini SDK):** Leverages `gemini-3.5-flash` to parse unstructured email bodies including multi-job LinkedIn digest emails into a strict, validated 15-column JSON schema.
* **Load (Google Sheets API & gspread):** Performs a safe database **upsert** using a composite primary key (`Company_Name` + `Job_Title`) to prevent duplicate entries and multi-role overwrites.
* **Automate (GitHub Actions CI/CD):** Runs autonomously in the cloud three times daily via a cron schedule, injecting secure tokens via GitHub Secrets.

---

## Tech Stack

* **Language:** Python
* **APIs & Libraries:** Google Gmail API, Google Sheets API (`gspread`)
* **AI / LLM:** Google GenAI SDK (`google-genai`)
* **CI/CD Automation:** GitHub Actions (Cron Scheduling & Secret Injection)

---

## Project Structure

```text
├── .github/
│   └── workflows/
│       └── etl_pipeline.yml  # Cloud automation config (runs 3x daily)
├── main.py                   # Core ETL pipeline script
├── auth.py                   # Local OAuth authentication helper
├── requirements.txt          # Project dependencies
└── README.md 
```

1. Clone the repository:
git clone [https://github.com/your-username/your-repo-name.git]
cd your-repo-name

2. Install dependencies:
pip install google-api-python-client google-auth gspread google-genai python-dotenv

3. Configure Environment Variables:
Create a local .env file in the root directory:
GEMINI_API_KEY=your_gemini_api_key_here

4. Run Locally:
python main.py



