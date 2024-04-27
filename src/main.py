import imaplib
import email
import json

# send the key, get the value from the hidden .config file
def load_api_key(key):
    with open('../.config', 'r') as file:
        config = json.load(file)
        return config[key]

# fetch the emails

def fetch_emails(email_user, email_password, sender_email, server='imap.gmail.com'):
    mail = imaplib.IMAP4_SSL(server)
    mail.login(email_user, email_password)
    mail.select('inbox')
    typ, search_data = mail.search(None, f'(UNSEEN FROM "{sender_email}")')

    email_ids = search_data[0].split()
    emails = []
    for email_id in email_ids:
        _, data = mail.fetch(email_id, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        emails.append(msg)
    return emails

if __name__ == '__main__':
    #print(load_api_key('test_email_subject')) # test method

    emails = fetch_emails(load_api_key('gmail_user'), load_api_key('gmail_pass'), 'ravigahlla@gmail.com')

    for msg in emails:
        # Assuming msg is an email.message.EmailMessage object
        # Extracting email headers can vary depending on the actual object structure and email content type
        email_subject = msg.get("subject")
        email_from = msg.get("from")
        print(f"From: {email_from}, Subject: {email_subject}")