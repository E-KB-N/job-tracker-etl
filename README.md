# Job Search HQ: Automated ETL Pipeline & Interactive Dashboard

An end-to-end data analytics and automation ecosystem that tracks job applications by extracting and parsing email telemetry from Gmail using **Google Gemini LLM**, storing structured records in **Google Sheets**, and delivering a high-performance **Streamlit Web Application** for interactive pipeline monitoring.

---

## System Architecture & Workflow

* **Extract (Gmail API):** Scans the primary Gmail inbox using targeted queries to capture read and unread status updates over a rolling window while filtering out marketing noise.
* **Transform (Google Gemini SDK):** Leverages advanced LLMs (`gemini-3.5-flash`) to parse unstructured email bodies—including multi-job digest emails—into a strict, validated 15-column JSON schema.
* **Load (Google Sheets API & gspread):** Performs a safe database **upsert** using a composite primary key (`Company_Name` + `Job_Title`) to prevent duplicate entries and multi-role overwrites.
* **Automate (GitHub Actions CI/CD):** Runs autonomously in the cloud three times daily via a cron schedule, injecting secure credentials via GitHub Secrets.
* **Visualize & Monitor (Streamlit App):** A fully responsive web dashboard featuring executive overview metrics, application momentum charts, recruitment funnel conversions, source effectiveness scoring, and a real-time Light/Dark Mode theme switcher.

---

## Tech Stack

* **Language:** Python
* **Web Framework:** Streamlit (Layout engine, custom UI tokens, interactive filters)
* **Data Processing & Visualization:** Pandas, NumPy, Plotly (Interactive charts & funnels)
* **APIs & Cloud Integrations:** Google Gmail API, Google Sheets API (`gspread`), Google Auth
* **AI / LLM:** Google GenAI SDK (`google-genai`)
* **CI/CD Automation:** GitHub Actions (Cron Scheduling & Secret Injection)

---

## Project Structure

```text
├── .github/
│   └── workflows/
│       └── etl_pipeline.yml     # Cloud automation config (runs 3x daily)
├── .streamlit/
│   └── config.toml              # Streamlit client configuration
├── app.py                       # Job Search HQ Streamlit Web Dashboard
├── main.py                      # Core Gmail-to-Sheets ETL pipeline script
├── auth.py                      # Local OAuth authentication helper
├── requirements.txt             # Project dependencies
└── README.md                    # Project documentation
```

Getting Started & Local Installation
1. Clone the Repository
Bash
git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
cd your-repo-name
2. Install Dependencies
Bash
pip install -r requirements.txt
3. Configure Environment Variables
Create a local .env file in the root directory for your pipeline credentials:

Code snippet
GEMINI_API_KEY=your_gemini_api_key_here
4. Run the ETL Pipeline Locally
To run the automated Gmail extraction and Google Sheets synchronization script:

Bash
python main.py
5. Launch the Streamlit Dashboard Locally
To start the interactive web application on your local machine:

Bash
streamlit run app.py
