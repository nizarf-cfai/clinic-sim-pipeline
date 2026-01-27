import time
import os
import smtplib
from imap_tools import MailBox, AND
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.cloud import dialogflowcx_v3beta1 as dialogflow
from google.oauth2 import service_account

# ================= CONFIGURATION =================
GMAIL_USER = "nizar.rizax@gmail.com"
GMAIL_APP_PASSWORD = "dclr amzs zbmv iwok" 

PROJECT_ID = "medforce-pilot-backend"
LOCATION_ID = "europe-west2"  
AGENT_ID = "78ca4c26-89d6-45db-96a2-54236538d312" 
LANGUAGE_CODE = "en"
KEY_PATH = "key.json" 
# =================================================

credentials = service_account.Credentials.from_service_account_file(KEY_PATH)

def get_dialogflow_response(text, session_id):
    client_options = None
    if LOCATION_ID != "global":
        api_endpoint = f"{LOCATION_ID}-dialogflow.googleapis.com:443"
        client_options = {"api_endpoint": api_endpoint}

    session_client = dialogflow.SessionsClient(
        credentials=credentials, 
        client_options=client_options
    )
    
    session_path = f"projects/{PROJECT_ID}/locations/{LOCATION_ID}/agents/{AGENT_ID}/sessions/{session_id}"

    text_input = dialogflow.TextInput(text=text)
    query_input = dialogflow.QueryInput(text=text_input, language_code=LANGUAGE_CODE)

    request = dialogflow.DetectIntentRequest(session=session_path, query_input=query_input)
    response = session_client.detect_intent(request=request)

    reply_texts = []
    for message in response.query_result.response_messages:
        if message.text:
            reply_texts.append(message.text.text[0])
            
    return "\n\n".join(reply_texts)

def send_email_reply(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject 

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())
        server.quit()
        print(f"-> Sent reply to {to_email}")
    except Exception as e:
        print(f"Error sending email: {e}")

# --- NEW FUNCTION: BETTER TEXT CLEANING ---
def clean_email_body(raw_text):
    """
    Reads the email but stops when it finds the previous conversation 
    (quoted text), so we don't send the whole history to the bot.
    """
    if not raw_text:
        return ""
        
    lines = raw_text.strip().splitlines()
    cleaned_lines = []
    
    for line in lines:
        # Common markers that the previous email is starting
        if line.strip().startswith(">"): # Standard quote
            break
        if "On " in line and "wrote:" in line: # Gmail style "On Mon... wrote:"
            break
        if "-----Original Message-----" in line: # Outlook style
            break
        if "From:" in line and "Sent:" in line: # Outlook style
            break
            
        cleaned_lines.append(line)
    
    # Join them back together with newlines so the Bot can read the list
    return "\n".join(cleaned_lines)[:1000] # Limit to 1000 chars

def run_listener():
    print(f"--- Email Bridge Running ({GMAIL_USER}) ---")
    print("Listening ONLY for emails with subject: 'MedForce Clinic'...")

    while True:
        try:
            with MailBox('imap.gmail.com').login(GMAIL_USER, GMAIL_APP_PASSWORD) as mailbox:
                
                # Filter for Unread + Subject Match
                criteria = AND(seen=False, subject="MedForce Clinic")
                
                for msg in mailbox.fetch(criteria):
                    print(f"\n[NEW MATCHING EMAIL] From: {msg.from_} | Subject: {msg.subject}")
                    
                    user_text = msg.text or msg.html
                    
                    # USE THE NEW CLEANING FUNCTION HERE
                    clean_text = clean_email_body(user_text)
                    
                    print(f"User said (Cleaned): \n{clean_text}")
                    print("-" * 20)

                    # Ask Dialogflow
                    bot_reply = get_dialogflow_response(clean_text, msg.from_)
                    
                    print(f"Bot says: {bot_reply}")

                    if bot_reply:
                        send_email_reply(msg.from_, msg.subject, bot_reply)
                    
        except Exception as e:
            print(f"Connection error (retrying in 5s): {e}")

        time.sleep(5)

if __name__ == "__main__":
    run_listener()