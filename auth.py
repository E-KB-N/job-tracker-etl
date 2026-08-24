import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes we need
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar.events'
]

def generate_new_token():
    
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)

    with open('token.json', 'w') as token:
        token.write(creds.to_json())
        
    print("Success! A fresh token.json has been created with the correct scopes.")

if __name__ == '__main__':
    generate_new_token()