# Automated Job Application Tracker (ETL Pipeline)

An automated data pipeline that extracts job application emails from Gmail, parses structured telemetry using Google Gemini LLM, and upserts them into Google Sheets using a composite primary key.

## Architecture
1. **Extract:** Scans the primary Gmail inbox using the Gmail API.
2. **Transform:** Parses unstructured email bodies into a strict 15-column schema using Google Gemini.
3. **Load:** Upserts records into Google Sheets using a composite key (`Company_Name` + `Job_Title`) to prevent multi-role overwrites.
4. **Automate:** Scheduled to run autonomously via GitHub Actions.

## Tech Stack
* Python
* Google Gmail API & Google Sheets API (`gspread`)
* Google GenAI SDK (`google-genai`)
* GitHub Actions (CI/CD Cron Scheduling)