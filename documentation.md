# Job Search HQ: Technical Architecture & Engineering Documentation

## 1. Problem Statement & Motivation
* The modern job search generates a high volume of fragmented, unstructured telemetry across multiple channels (LinkedIn, direct emails, ATS portals).
* Manual tracking introduces significant data latency, human error, and prevents meaningful performance analysis of interview conversion rates.
* **Job Search HQ** engineers a zero-touch, end-to-end data pipeline to autonomously extract, model, and visualize this lifecycle, transforming an operational bottleneck into a streamlined, data-driven system.

## 2. Architecture & Data Flow
* **Extraction Engine:** A scheduled cron job queries the Gmail API, utilizing targeted filters to capture relevant communication while discarding marketing noise.
* **Transformation Layer:** The Google GenAI SDK (`gemini-3.5-flash`) serves as the parsing engine, strictly enforcing a 15-column JSON schema to extract structured entities from noisy, multi-role digest emails.
* **Loading Mechanism:** A robust integration with the Google Sheets API executes idempotent upserts via a composite primary key (`Company_Name` + `Job_Title`).
* **Presentation Layer:** A Streamlit application provides interactive executive dashboards, visualizing funnel momentum, conversion rates, and SLA tracking for overdue application updates.

## 3. Technical Challenges & Engineering Solutions
* **Idempotency & Data Integrity:** Running an automated ETL sync multiple times daily risks duplicating rows. The pipeline logic guarantees idempotency by checking existing state and applying targeted updates rather than blind appends.
* **Unstructured Multi-Entity Parsing:** Job board digests often pack multiple roles into a single email. The LLM prompt is engineered to decompose these arrays into distinct, normalized database records.
* **Secure Environment Parity:** The application utilizes a dynamic credential loader, seamlessly transitioning between local development (`token.json`) and secure cloud deployments (`st.secrets`) without exposing secrets.
* **Data Quality Handling:** A custom parsing module aggressively cleans mixed datetime formats, Excel serial numbers, and missing salary telemetry to prevent downstream visualization failures.

## 4. Future Analytics Enhancements
* Deploying Looker Studio for deep-dive historical BI reporting, alongside Google Calendar API integration for automated interview scheduling telemetry.    