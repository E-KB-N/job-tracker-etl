import os
import base64
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import gspread
from google import genai
from google.genai import types

# Load environment variables from a local .env file
load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise Exception("GEMINI_API_KEY environment variable is not set.")

SHEET_ID = "1XcdyusjyMP_5p6QBXwQXNI-QJ-_bn6qsLZC5dkzwuX8" # Actual Google Sheet ID

client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-3.5-flash"

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify', # GMAIL integration
    'https://www.googleapis.com/auth/spreadsheets', # Google Shee integration
    'https://www.googleapis.com/auth/calendar.events' # Google Calendar integration
]

# ==========================================
# 1. AUTHENTICATION
# ==========================================
def get_credentials():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("token.json is invalid. Please re-run authentication.")
    return creds

# ==========================================
# 2. EXTRACT (GMAIL API)
# ==========================================
def get_email_body(payload):
    if 'data' in payload.get('body', {}):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif 'parts' in part:
                return get_email_body(part)
    return ""

def fetch_recent_job_emails(gmail_service):
    query = (
        "category:primary newer_than:1d "
        "(application OR interview OR applied OR rejection OR update) "
        "-Temu -turing -mercor -micro1 -outlier -remotasks -alignerr "
        "-binance -coinbase -crypto -kraken"
    )
    
    results = gmail_service.users().messages().list(userId='me', q=query, maxResults=20).execute()
    messages = results.get('messages', [])
    
    email_data = []
    for msg in messages:
        msg_detail = gmail_service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        payload = msg_detail['payload']
        headers = payload.get('headers', [])
        
        sender = next((header['value'] for header in headers if header['name'] == 'From'), "Unknown")
        subject = next((header['value'] for header in headers if header['name'] == 'Subject'), "No Subject")
        body = get_email_body(payload)
        
        email_data.append({"id": msg['id'], "sender": sender, "subject": subject, "body": body})
        
    return email_data

# ==========================================
# 3. TRANSFORM (GEMINI API)
# ==========================================
def parse_email_with_llm(email_text, sender):
    prompt = f"""
    You are an expert data extraction assistant. Analyze the following email and extract job application telemetry.
    The email may contain updates for MULTIPLE job applications (e.g., a LinkedIn digest).
    
    Return ONLY a valid JSON ARRAY of objects (`[...]`). Do not include markdown formatting or explanations.
    If the email is entirely unrelated to job applications, return an empty array: []

    Each object in the array must contain exactly these 15 keys:
    1. "Company_Name": (String) The actual hiring company.
    2. "Job_Title": (String) The specific role applied for.
    3. "Application_Date": (String) YYYY-MM-DD format if mentioned, else null.
    4. "Current_Status": (String) Must be exactly one of: [Applied, Rejected, Interviewing, Offer].
    5. "Pipeline_Stage": (String or null) e.g., Resume Screen, Technical Assessment, Final Round.
    6. "JD_Summary": (String or null) 1-2 sentence summary of the role.
    7. "Job_Posting_URL": (String or null) URL linking to the job or platform.
    8. "Point_of_Contact": (String or null) Name of the recruiter or sender.
    9. "Action_Deadline": (String or null) YYYY-MM-DD or explicit deadline text for a test/interview RSVP.
    10. "Constructive_Feedback": (String or null) Any specific reason given for rejection.
    11. "Location_Type": (String or null) [Remote, Hybrid, On-site, Relocation].
    12. "Platform_Source": (String or null) Where the application originated (e.g., LinkedIn, Wellfound, Greenhouse).
    13. "Salary_Range_Posted": (String or null) Extracted compensation figures.
    14. "Interview_Date": (String or null) YYYY-MM-DD if an interview is scheduled.
    15. "Last_Updated": (String) Always use {datetime.now().strftime('%Y-%m-%d')}.
    
    Email Text:
    {email_text}
    """
    
    max_retries = 3
    wait_time = 15
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            return json.loads(response.text)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "503" in str(e):
                print(f"Rate limit hit. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                wait_time *= 2
            else:
                print(f"API Error: {e}")
                return []
    return []

# ==========================================
# 4. LOAD (GOOGLE SHEETS & CALENDAR)
# ==========================================
def sync_event_to_calendar(creds, job_data):
    """
    Creates an all-day calendar event if an Interview_Date or actionable Deadline is present.
    """
    company = job_data.get("Company_Name")
    title = job_data.get("Job_Title", "Job Event")
    interview_date = job_data.get("Interview_Date")
    action_deadline = job_data.get("Action_Deadline")
    
    event_date = None
    event_title_prefix = ""
    
    if interview_date:
        event_date = interview_date
        event_title_prefix = "Interview: "
    elif action_deadline and job_data.get("Current_Status") == "Interviewing":
        event_date = action_deadline
        event_title_prefix = "Deadline: "
        
    if not event_date:
        return
        
    try:
        calendar_service = build('calendar', 'v3', credentials=creds)
        
        event_body = {
            'summary': f"{event_title_prefix}{company} - {title}",
            'description': (
                f"Role: {title}\n"
                f"Company: {company}\n"
                f"Status: {job_data.get('Current_Status')}\n"
                f"Stage: {job_data.get('Pipeline_Stage')}\n"
                f"Platform: {job_data.get('Platform_Source')}"
            ),
            'start': {'date': event_date},
            'end': {'date': event_date},
        }
        
        created_event = calendar_service.events().insert(
            calendarId='primary', 
            body=event_body
        ).execute()
        
        print(f" -> [Calendar] Added event: {created_event.get('summary')} for {event_date}")
        
    except Exception as e:
        print(f" -> [Calendar Error] Could not create event: {e}")

def upsert_to_sheets(gc, data):
    if not data or data.get("Not_Job_Related"):
        return False
        
    sheet = gc.open_by_key(SHEET_ID).sheet1
    records = sheet.get_all_records()
    
    company_name = data.get("Company_Name")
    job_title = data.get("Job_Title", "Unknown Role")
    
    if not company_name:
        return False
        
    row_data = [
        data.get("Company_Name", ""), data.get("Job_Title", ""), data.get("Application_Date", ""),
        data.get("Current_Status", ""), data.get("Pipeline_Stage", ""), data.get("JD_Summary", ""),
        data.get("Job_Posting_URL", ""), data.get("Point_of_Contact", ""), data.get("Action_Deadline", ""),
        data.get("Constructive_Feedback", ""), data.get("Location_Type", ""), data.get("Platform_Source", ""),
        data.get("Salary_Range_Posted", ""), data.get("Interview_Date", ""), data.get("Last_Updated", "")
    ]

    existing_row_index = next(
        (i for i, record in enumerate(records) 
         if record.get("Company_Name") == company_name and record.get("Job_Title") == job_title), 
        None
    )

    if existing_row_index is not None:
        sheet.update(
            values=[row_data],
            range_name=f"A{existing_row_index + 2}:O{existing_row_index + 2}"
        )
        print(f"Updated existing record for {company_name} - {job_title}")
    else:
        sheet.append_row(row_data)
        print(f"Appended new record for {company_name} - {job_title}")
        
    return True

# ==========================================
# EXECUTION
# ==========================================
def run_pipeline():
    print("Starting ETL Pipeline...")
    creds = get_credentials()
    
    gmail_service = build('gmail', 'v1', credentials=creds)
    gc = gspread.authorize(creds)
    
    print("Scanning inbox for recent job updates (last 24 hours)...")
    emails = fetch_recent_job_emails(gmail_service)
    
    if not emails:
        print("No recent job emails found. Pipeline sleeping.")
        return
        
    for email in emails:
        print(f"\nProcessing email from: {email['sender']} - {email['subject']}")
        
        job_updates_list = parse_email_with_llm(email['body'], email['sender'])
        
        print(f"Jobs Found by Gemini: {len(job_updates_list) if job_updates_list else 0}")
        
        if job_updates_list:
            for job_data in job_updates_list:
                if job_data and isinstance(job_data, dict) and job_data.get("Company_Name"):
                    print(f" -> Upserting: {job_data.get('Company_Name')} | {job_data.get('Job_Title')} | {job_data.get('Current_Status')}")
                    success = upsert_to_sheets(gc, job_data)
                    
                    if success:
                        sync_event_to_calendar(creds, job_data)
                        
                    time.sleep(2)
                
        time.sleep(12) 

    print("\nPipeline execution complete.")

if __name__ == '__main__':
    run_pipeline()