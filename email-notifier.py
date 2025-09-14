import pandas as pd
import os
import time
import hashlib
from datetime import datetime
import base64
from email.mime.text import MIMEText
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Configuration
CSV_FILE = "executive_orders.csv"
GOOGLE_GROUP = "white-house-eo-tracker@googlegroups.com"
SENDER_EMAIL = "eo.tracker@gmail.com"  # Replace with your email
CHECK_INTERVAL = 3600  # Check every hour (in seconds)
LAST_STATE_FILE = "last_eo_state.txt"

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    """Get an authorized Gmail API service instance"""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # If there are no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    return build('gmail', 'v1', credentials=creds)

def get_file_hash():
    """Generate a hash of the CSV file to detect changes"""
    with open(CSV_FILE, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def save_last_state(hash_value):
    """Save the current file hash"""
    with open(LAST_STATE_FILE, 'w') as f:
        f.write(hash_value)

def get_last_state():
    """Get the last saved file hash"""
    if os.path.exists(LAST_STATE_FILE):
        with open(LAST_STATE_FILE, 'r') as f:
            return f.read().strip()
    return ""

def find_new_executive_orders():
    """Check if there are new executive orders in the CSV file"""
    try:
        df = pd.read_csv(CSV_FILE)
        # Filter for executive orders
        eo_df = df[df['is_eo'] == True]
        
        # Sort by date published (most recent first)
        eo_df = eo_df.sort_values(by='date_published', ascending=False)
        
        # Get the most recent EO
        most_recent_eo = eo_df.iloc[0] if not eo_df.empty else None
        
        # Get the last processed state
        last_hash = get_last_state()
        current_hash = get_file_hash()
        
        # If file has changed and we have a recent EO
        if current_hash != last_hash and most_recent_eo is not None:
            # Save new state
            save_last_state(current_hash)
            
            # Check if this is the first run (no previous hash)
            if not last_hash:
                print("Initial run - recording current state without sending email")
                return None
            
            return most_recent_eo
        
        return None
    except Exception as e:
        print(f"Error checking for new executive orders: {e}")
        return None

def format_eo_for_email(eo):
    """Format the executive order data for email"""
    
    # Format the date nicely
    try:
        date_obj = datetime.strptime(eo['date_published'].split('+')[0], '%Y-%m-%d %H:%M:%S')
        formatted_date = date_obj.strftime('%B %d, %Y')
    except:
        formatted_date = eo['date_published']
    
    # Create a summary of the text (first 300 characters)
    text_summary = eo['text'][:300] + "..." if len(eo['text']) > 300 else eo['text']
    
    email_body = f"""
NEW EXECUTIVE ORDER DETECTED

Title: {eo['title']}
Published: {formatted_date}
URL: {eo['url']}

Summary:
{text_summary}

---
This is an automated notification from the White House Executive Order Tracker.
To unsubscribe, visit the Google Group settings at: 
https://groups.google.com/g/white-house-eo-tracker
    """
    
    return email_body

def send_email_with_gmail_api(eo):
    """Send notification email using Gmail API"""
    try:
        service = get_gmail_service()
        
        # Create message
        email_body = format_eo_for_email(eo)
        message = MIMEText(email_body)
        message['to'] = GOOGLE_GROUP
        message['from'] = SENDER_EMAIL
        message['subject'] = f"New White House Action: {eo['title']}"
        
        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send the message
        message = service.users().messages().send(
            userId='me', 
            body={'raw': raw_message}
        ).execute()
        
        print(f"Notification email sent successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Message Id: {message['id']}")
        
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def main():
    print(f"Starting Executive Order notification service at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Monitoring file: {CSV_FILE}")
    print(f"Target Google Group: {GOOGLE_GROUP}")
    
    # For one-time execution
    new_eo = find_new_executive_orders()
    if new_eo is not None:
        print(f"New executive order found: {new_eo['title']}")
        send_email_with_gmail_api(new_eo)
    else:
        print("No new executive orders found")

if __name__ == "__main__":
    main()