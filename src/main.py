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

    email_ids = set(search_data[0].split())  # Using set to avoid duplicate email IDs

    emails = []
    for email_id in email_ids:
        _, data = mail.fetch(email_id, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        # now extract the body of each email, and store in the array
        body = None
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get("Content-Disposition")
                if content_type == "text/plain" and content_disposition is None:
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = msg.get_payload(decode=True).decode()

        # Append the body to the email information in a dictionary
        email_info = {
            "from": msg.get("from"),
            "subject": msg.get("subject"),
            "body": body,
        }

        emails.append(email_info)  # Append email info dictionary to the list

    return emails

if __name__ == '__main__':
    #print(load_api_key('test_email_subject')) # test method

    sender_email = 'ravigahlla@gmail.com' # replace with load_api_key('sender_email') when NOT testing

    emails = fetch_emails(load_api_key('gmail_user'), load_api_key('gmail_pass'), sender_email)

    #print(len(emails))

    for email in emails:
        print(f"{email['from']}")
        print(f"{email['subject']}")
        #print(f"{email['body']}")