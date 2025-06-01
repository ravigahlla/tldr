import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
from email import policy
from email.header import decode_header

import imaplib
import smtplib
import socket # For catching network errors like gaierror

from . import tldr_openai_helper

# Import the logger instance from our new tldr_logger module
from .tldr_logger import logger

# Custom Exceptions for email operations (optional, but can be helpful)
class EmailConnectionError(Exception):
    """Custom exception for email connection failures."""
    pass

class EmailFetchingError(Exception):
    """Custom exception for email fetching failures."""
    pass

class EmailSendingError(Exception):
    """Custom exception for email sending failures."""
    pass

DEFAULT_IMAP_PORT_SSL = 993 # Standard IMAP SSL port

def connect_to_imap(email_user: str, email_password: str, server: str, port: int = DEFAULT_IMAP_PORT_SSL):
    """
    Connects to the IMAP server, logs in, and selects the INBOX.
    Stores the email_user on the connection object for logging purposes.

    Returns:
        imaplib.IMAP4_SSL: The IMAP connection object.
    Raises:
        EmailConnectionError: If connection or login fails.
    """
    logger.info(f"Attempting to connect to IMAP server: {server}:{port} for user: {email_user}")
    try:
        mail = imaplib.IMAP4_SSL(server, port)
        rc, resp = mail.login(email_user, email_password)
        if rc == 'OK':
            logger.info(f"Successfully logged into IMAP server for user: {email_user}")
            mail.user_for_logging = email_user # Store for logger in close_imap_connection
            
            rc_select, data_select = mail.select("inbox")
            if rc_select == 'OK':
                logger.info("INBOX selected successfully.")
                return mail
            else:
                error_message_select = data_select[0].decode() if data_select and data_select[0] else "Unknown error selecting INBOX"
                logger.error(f"Failed to select INBOX. Server response: {error_message_select}")
                try:
                    mail.logout() # Attempt logout even if select failed
                except Exception:
                    pass 
                raise EmailConnectionError(f"Failed to select INBOX for user {email_user}: {error_message_select}")
        else:
            error_message_login = resp[0].decode() if resp and resp[0] else "Unknown login error"
            logger.error(f"IMAP login failed for user {email_user}. Server response: {error_message_login}")
            raise EmailConnectionError(f"IMAP login failed for user {email_user}: {error_message_login}")
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP connection/operational error for user {email_user}: {e}", exc_info=True)
        raise EmailConnectionError(f"IMAP connection failed for user {email_user}: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error connecting to IMAP for user {email_user}: {e}", exc_info=True)
        raise EmailConnectionError(f"Unexpected IMAP connection error for {email_user}: {e}") from e

def close_imap_connection(mail_conn: imaplib.IMAP4_SSL):
    """
    Logs out and closes the IMAP connection.
    Uses 'user_for_logging' attribute if set on mail_conn.
    """
    if mail_conn:
        user_to_log = getattr(mail_conn, 'user_for_logging', 'unknown user')
        try:
            logger.info(f"Attempting to logout from IMAP server for user: {user_to_log}")
            mail_conn.logout()
            logger.info(f"Successfully logged out from IMAP server for user: {user_to_log}")
        except (imaplib.IMAP4.error, AttributeError, Exception) as e: 
            logger.warning(f"Error during IMAP logout for user {user_to_log} (connection might have already been closed or invalid): {e}")

def fetch_emails(mail_conn: imaplib.IMAP4_SSL, sender_email: str):
    """
    Fetches unread emails from a specific sender using an existing IMAP connection.
    Uses UID for searching and fetching.

    Args:
        mail_conn: Active imaplib.IMAP4_SSL connection object with INBOX selected.
        sender_email: The email address of the sender to filter by.

    Returns:
        list: A list of tuples, where each tuple is (UID (bytes), email.message.Message object).
              Returns an empty list if no matching emails are found or in case of non-critical errors.
    Raises:
        EmailFetchingError: If there's a critical error during search or fetch.
    """
    messages_data = []
    try:
        search_criteria = f'(UNSEEN FROM "{sender_email}")'
        logger.info(f"Searching for emails with criteria: {search_criteria}")

        # Search for UIDs
        typ, msg_uid_data = mail_conn.uid('search', None, search_criteria)
        if typ != 'OK':
            logger.error(f"Error searching for emails: {msg_uid_data[0].decode() if msg_uid_data and msg_uid_data[0] else 'Unknown error'}")
            raise EmailFetchingError(f"Failed to search emails: {msg_uid_data}")

        email_uids_bytes_list = msg_uid_data[0].split() # List of UIDs as bytes

        if not email_uids_bytes_list:
            logger.info(f"No unread emails found from {sender_email}.")
            return []

        logger.info(f"Found {len(email_uids_bytes_list)} unread email(s) from {sender_email}.")

        for uid_bytes in email_uids_bytes_list:
            # Fetch the email by UID
            # RFC822 fetches the entire message
            typ, msg_data = mail_conn.uid('fetch', uid_bytes, '(RFC822)')
            if typ != 'OK':
                logger.warning(f"Error fetching email UID {uid_bytes.decode()}: {msg_data[0].decode() if msg_data and msg_data[0] else 'Unknown error'}. Skipping this email.")
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    # Parse the email content using the modern `policy`
                    msg = email.message_from_bytes(response_part[1], policy=policy.default)
                    messages_data.append((uid_bytes, msg))
                    logger.debug(f"Successfully fetched and parsed email UID {uid_bytes.decode()}")
        
        return messages_data

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP operational error during email fetching: {e}", exc_info=True)
        # Depending on the error, you might want to re-raise or handle differently
        # For now, let's assume it's a significant fetching issue.
        raise EmailFetchingError(f"IMAP error during email fetching: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during email fetching: {e}", exc_info=True)
        raise EmailFetchingError(f"Unexpected error during email fetching: {e}") from e

def mark_emails_as_read(mail_conn: imaplib.IMAP4_SSL, uids: list):
    """
    Marks a list of emails as read (Seen) using their UIDs.

    Args:
        mail_conn: Active imaplib.IMAP4_SSL connection object with INBOX selected.
        uids: A list of email UIDs (as bytes) to mark as read.
    """
    if not uids:
        logger.info("No email UIDs provided to mark as read.")
        return True # Nothing to do, considered success

    uids_str_list = [uid.decode() for uid in uids] # For logging
    logger.info(f"Attempting to mark {len(uids_str_list)} email(s) as read: {', '.join(uids_str_list)}")
    
    try:
        # Join UIDs into a comma-separated string for the store command
        # imaplib expects UIDs to be bytes for the command itself.
        uid_set = b','.join(uids)
        typ, response = mail_conn.uid('store', uid_set, '+FLAGS', r'(\Seen)')
        
        if typ == 'OK':
            logger.info(f"Successfully marked email(s) {', '.join(uids_str_list)} as read.")
            return True
        else:
            error_message = response[0].decode() if response and response[0] else "Unknown error"
            logger.error(f"Failed to mark email(s) {', '.join(uids_str_list)} as read. Server response: {error_message}")
            # Optionally raise an EmailFetchingError or just return False
            # For now, just log and return False as it's not a total failure of the main process
            return False
            
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP operational error while marking emails {', '.join(uids_str_list)} as read: {e}", exc_info=True)
        return False # Or raise EmailFetchingError
    except Exception as e:
        logger.error(f"Unexpected error while marking emails {', '.join(uids_str_list)} as read: {e}", exc_info=True)
        return False # Or raise EmailFetchingError

def get_email_content(msg: email.message.Message):
    """
    Extracts the text content from an email.message.Message object.
    Prefers plain text, falls back to HTML if plain text is not available.
    """
    body_plain = None
    body_html = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" not in content_disposition: # Skip attachments
                if content_type == "text/plain" and body_plain is None: # Prefer plain text
                    try:
                        body_plain = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                        logger.debug("Extracted text/plain part.")
                    except Exception as e:
                        logger.warning(f"Could not decode text/plain part with charset {part.get_content_charset()}: {e}")
                elif content_type == "text/html" and body_html is None: # Fallback to HTML
                    try:
                        body_html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                        logger.debug("Extracted text/html part.")
                    except Exception as e:
                        logger.warning(f"Could not decode text/html part with charset {part.get_content_charset()}: {e}")
    else: # Not multipart, try to get payload directly
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            try:
                body_plain = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
                logger.debug("Extracted text/plain from non-multipart.")
            except Exception as e:
                logger.warning(f"Could not decode text/plain from non-multipart with charset {msg.get_content_charset()}: {e}")
        elif content_type == "text/html":
            try:
                body_html = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
                logger.debug("Extracted text/html from non-multipart.")
            except Exception as e:
                logger.warning(f"Could not decode text/html from non-multipart with charset {msg.get_content_charset()}: {e}")

    if body_plain:
        logger.info("Using text/plain content for email body.")
        return body_plain.strip()
    elif body_html:
        logger.info("Using text/html content for email body (plain text not found).")
        # Consider a simple HTML to text conversion here if needed, or return HTML
        # For now, returning HTML as is, or you could use a library like beautifulsoup4 to extract text
        # For simplicity, let's assume the summarizer can handle basic HTML or you strip it later.
        return body_html.strip() # Or clean it
    else:
        logger.warning("Could not find text/plain or text/html content in the email.")
        return None

def get_config_info():
    """
    Returns a string containing helper information for this summarizer.
    """
    try:
        # This creates a direct dependency on tldr_openai_helper just for a string.
        # Consider refactoring: main.py could fetch this and pass to send_email.
        model_name = getattr(tldr_openai_helper, 'open_ai_model', 'N/A')
        config_info_html = f"LLM Model: {model_name}<br><br>"
        logger.debug(f"Generated config info for email: {config_info_html.strip()}")
        return config_info_html
    except Exception as e:
        logger.warning(f"Could not retrieve OpenAI model name for config info: {e}")
        return "LLM Model: Not available<br><br>"

def send_email(is_forward_orig_email: bool, user, password, recipient, subject, body_html, original_email_msg: email.message.EmailMessage = None, server='smtp.gmail.com', port=587):
    """
    Sends an email, optionally forwarding an original email message.

    Args:
        is_forward_orig_email (bool): If True, attaches the original_email_msg.
        user (str): Sender's email address.
        password (str): Sender's email password (app password for Gmail).
        recipient (str): Recipient's email address.
        subject (str): Subject of the new email.
        body_html (str): HTML content for the new email.
        original_email_msg (email.message.EmailMessage, optional): Original EmailMessage to attach/forward.
        server (str): SMTP server address.
        port (int): SMTP server port (587 for TLS, 465 for SSL).

    Returns:
        bool: True if email was sent successfully, False otherwise.
    """
    logger.info(f"Attempting to send email. To: {recipient}, Subject: {subject}")
    smtp = None  # Initialize smtp to None for the finally block
    try:
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = recipient
        # Ensure subject is not None or empty, provide a default if necessary
        msg['Subject'] = subject if subject else "tldr Summary"
        
        # Get config info (consider passing this as an argument)
        config_prepend_html = get_config_info()

        # Safely prepend config info to the body
        # This assumes body_html is a complete HTML document or a fragment
        # A more robust way might be to ensure body_html is a proper HTML doc or use a template
        if "<body>" in body_html.lower():
            parts = body_html.split("<body>", 1)
            if len(parts) > 1:
                 processed_body_html = f"{parts[0]}<body>{config_prepend_html}{parts[1]}"
            else: # No closing </body> ?
                 processed_body_html = f"{config_prepend_html}{body_html}" # Prepend if split fails
        else: # If no <body> tag, just prepend (might be a fragment)
            processed_body_html = f"{config_prepend_html}{body_html}"

        # Remove potential markdown artifacts if they exist
        processed_body_html = processed_body_html.replace("```html", "").replace("```", "")

        msg.attach(MIMEText(processed_body_html, 'html', _charset='utf-8'))

        if is_forward_orig_email and original_email_msg:
            logger.debug("Attaching original email content.")
            msg.attach(MIMEText("<br><hr><b>ORIGINAL EMAIL:</b><br><br>", 'html', _charset='utf-8'))

            # Make a deep copy if you plan to modify original_email_msg parts,
            # or if it might be reused. For simple forwarding, direct iteration is fine.
            if original_email_msg.is_multipart():
                for part in original_email_msg.walk():
                    # We clone each part of the original message
                    # Be careful with Content-ID and other headers if they might conflict
                    # For simple forwarding, this is often okay.
                    cloned_part = email.message.Message() # Create a new base message
                    for k, v in part.items(): # Copy headers
                        cloned_part[k] = v
                    cloned_part.set_payload(part.get_payload(decode=False)) # Copy payload (raw)
                    if cloned_part.get_content_maintype() == 'text':
                         # Ensure charset is set for text parts, EmailMessage might not do this automatically
                         charset = part.get_content_charset() or 'utf-8'
                         cloned_part.set_charset(charset)

                    msg.attach(cloned_part)
            else:
                # If the original email is not multipart, attach its payload
                payload = original_email_msg.get_payload(decode=True)
                content_type = original_email_msg.get_content_type()
                charset = original_email_msg.get_content_charset() or 'utf-8'
                try:
                    # Try to decode if text, otherwise attach as is (could be image etc.)
                    if original_email_msg.get_content_maintype() == 'text':
                        decoded_payload = payload.decode(charset, errors='replace')
                        part_to_attach = MIMEText(decoded_payload, original_email_msg.get_content_subtype(), _charset=charset)
                    else: # For non-text, create a generic MIME part
                        part_to_attach = email.mime.base.MIMEBase(original_email_msg.get_content_maintype(), original_email_msg.get_content_subtype())
                        part_to_attach.set_payload(payload)
                        email.encoders.encode_base64(part_to_attach) # Encode if necessary
                        filename = original_email_msg.get_filename()
                        if filename:
                             part_to_attach.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(part_to_attach)

                except Exception as e:
                    logger.error(f"Error attaching non-multipart original email content: {e}", exc_info=True)
                    # Fallback: attach as plain text if all else fails
                    msg.attach(MIMEText(f"Could not fully process original message part. Error: {e}", 'plain', _charset='utf-8'))

        # Connect to SMTP server
        logger.debug(f"Connecting to SMTP server: {server}:{port}")
        # For Gmail, port 587 uses STARTTLS, port 465 uses SMTP_SSL directly
        if port == 465:
            smtp = smtplib.SMTP_SSL(server, port, timeout=30)
        else: # Assuming port 587 or other that requires STARTTLS
            smtp = smtplib.SMTP(server, port, timeout=30)
            smtp.starttls()
        
        # Combined login and send within the same try block after connection
        logger.debug(f"Logging into SMTP server as {user}")
        smtp.login(user, password)
        logger.info(f"Successfully logged into SMTP server.")
            
        smtp.send_message(msg)
        logger.info(f"Email successfully sent to: {recipient}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed for user {user}. Server response: {e.smtp_code} - {e.smtp_error}", exc_info=True)
    except smtplib.SMTPConnectError as e:
        logger.error(f"Failed to connect to SMTP server {server}:{port}. Error: {e.smtp_code} - {e.smtp_error}", exc_info=True)
    except smtplib.SMTPServerDisconnected as e:
        logger.error(f"SMTP server disconnected unexpectedly: {e}", exc_info=True)
    except smtplib.SMTPException as e: # Catch-all for other smtplib errors
        logger.error(f"An SMTP error occurred while sending email to {recipient}: {e}", exc_info=True)
    except socket.gaierror as e: # DNS resolution error
        logger.error(f"Network error (DNS resolution) connecting to SMTP server {server}: {e}", exc_info=True)
    except socket.timeout:
        logger.error(f"Timeout connecting/sending via SMTP server {server}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending email: {e}", exc_info=True)
    finally: # Ensures smtp.quit() is called if smtp object was created
        if smtp:
            try:
                smtp.quit()
                logger.debug("Closed SMTP connection.")
            except Exception as e:
                logger.warning(f"Error during SMTP quit: {e}", exc_info=True)
    
    return False