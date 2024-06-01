import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
from email import policy

import imaplib
import smtplib


def fetch_emails(email_user, email_password, sender_email, server='imap.gmail.com'):
    mail = imaplib.IMAP4_SSL(server)
    mail.login(email_user, email_password)
    mail.select('inbox')  # Select the inbox or another specific mailbox
    typ, search_data = mail.search(None, f'(UNSEEN FROM "{sender_email}")')

    email_ids = set(search_data[0].split())  # Using a set to avoid duplicate email IDs

    emails = []
    for email_id in email_ids:
        _, data = mail.fetch(email_id, '(RFC822)')
        raw_email = data[0][1]
        # Use policy.default to return a higher-level EmailMessage object
        msg = email.message_from_bytes(raw_email, policy=policy.default)

        # Instead of extracting parts and creating a dictionary, append the full EmailMessage object
        emails.append(msg)

    return emails


def get_email_content(email_message):
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")
            if content_type == 'text/plain' and 'attachment' not in content_disposition:
                return part.get_payload(decode=True).decode()  # Decode from Base64 and decode bytes to str
            elif content_type == 'text/html' and 'attachment' not in content_disposition:
                return part.get_payload(decode=True).decode()  # Optional: return HTML content
    else:
        # If it's not multipart, just return the entire payload
        return email_message.get_payload(decode=True).decode()

    return ""  # Return an empty string if no suitable part was found


def send_email(is_forward_orig_email, user, password, recipient, subject, body, original_email, server='smtp.gmail.com', port=587):
    """
    Sends an existing EmailMessage object with additional body text at the top.

    Args:
        is_forward_orig_email (int): Value to indicate whether to send an email, or forward (includes the body of original email)
        user (str): Sender's email address.
        password (str): Sender's email password.
        recipient (str): Recipient's email address.
        subject (str): Subject of the forwarded email.
        body (str): HTML content to prepend to the email.
        original_email (email.message.EmailMessage): Original EmailMessage to send.
        server (str): SMTP server address.
        port (int): SMTP server port.
    """
    # Setup the SMTP server
    with smtplib.SMTP(server, port) as smtp:
        smtp.starttls()  # Start TLS encryption
        smtp.login(user, password)  # Authenticate with the SMTP server

        # Create a new MIMEMultipart message to forward the email with additional content
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = recipient
        msg['Subject'] = 'Your GPT summary of: ' + subject

        # Add the new HTML body text as the first part of the email
        intro_text = MIMEText(body, 'html')
        msg.attach(intro_text)

        if is_forward_orig_email:  # if you want to forward the original email, this will take care of that
            msg.attach(MIMEText("<br><br><b>ORIGINAL EMAIL<b><hr><br>", 'html'))

            # Check if original_email is already multipart
            if original_email.is_multipart():
                for part in original_email.walk():
                    # We clone each part of the original message
                    msg.attach(part)
            else:
                # If the original email is not multipart, just attach it as a plain text part
                plain_text = MIMEText(original_email.get_payload(decode=True), 'plain')
                msg.attach(plain_text)

        # Send the constructed message
        smtp.send_message(msg)
        print("Email sent successfully.")