import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
from email import policy

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

def fetch_emails(email_user, email_password, sender_email, server='imap.gmail.com'):
    """
    Fetches unread emails from a specific sender.

    Returns:
        A list of email.message.EmailMessage objects or an empty list if errors occur.
    """
    emails = []
    mail = None # Initialize mail to None for the finally block
    try:
        logger.info(f"Attempting to connect to IMAP server: {server} for user: {email_user}")
        mail = imaplib.IMAP4_SSL(server)
        
        # Set a timeout for the login operation (e.g., 30 seconds)
        # Note: imaplib itself doesn't directly support timeout on login in a clean way.
        # For more robust timeout, consider libraries like 'imapclient' or handling at socket level if critical.
        # For now, we rely on default socket timeouts or catch general exceptions.
        
        rc, resp = mail.login(email_user, email_password)
        if rc != 'OK':
            # resp usually contains the error message from the server
            error_message = resp[0].decode() if isinstance(resp[0], bytes) else str(resp[0])
            logger.error(f"IMAP login failed for user {email_user}. Server response: {error_message}")
            raise EmailConnectionError(f"IMAP login failed: {error_message}")
        logger.info(f"Successfully logged into IMAP server for user: {email_user}")

        logger.debug("Selecting INBOX.")
        status, _ = mail.select('inbox', readonly=True) # readonly=True if you don't intend to change flags here
        if status != 'OK':
            logger.error("Failed to select INBOX.")
            raise EmailFetchingError("Failed to select INBOX.")

        search_criteria = f'(UNSEEN FROM "{sender_email}")'
        logger.info(f"Searching for emails with criteria: {search_criteria}")
        typ, search_data = mail.search(None, search_criteria)
        if typ != 'OK':
            logger.error(f"Failed to search for emails. Status: {typ}, Data: {search_data}")
            raise EmailFetchingError("Email search failed.")

        email_ids_bytes = search_data[0].split()
        if not email_ids_bytes:
            logger.info(f"No new unread emails found from: {sender_email}")
            return []
        
        logger.info(f"Found {len(email_ids_bytes)} unread email(s) from {sender_email}.")

        for num, email_id_bytes in enumerate(email_ids_bytes):
            email_id_str = email_id_bytes.decode()
            logger.debug(f"Fetching email ID: {email_id_str} ({num+1}/{len(email_ids_bytes)})")
            try:
                # Fetch the email by ID
                typ, data = mail.fetch(email_id_bytes, '(RFC822)')
                if typ != 'OK':
                    logger.warning(f"Failed to fetch email ID {email_id_str}. Status: {typ}")
                    continue # Skip this email

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email, policy=policy.default)
                emails.append(msg)
                logger.debug(f"Successfully parsed email ID: {email_id_str}, Subject: {msg.get('Subject', 'N/A')}")
            except Exception as e:
                logger.error(f"Error processing email ID {email_id_str}: {e}", exc_info=True)
                # Optionally, mark as seen or move to an error folder here if desired
                continue # Continue to the next email

    except imaplib.IMAP4.error as e: # Catches various IMAP errors
        logger.error(f"IMAP operational error for user {email_user}: {e}", exc_info=True)
        # Consider raising a more specific custom exception if needed by the caller
    except EmailConnectionError as e: # Custom exception already logged
        raise # Re-raise to be handled by caller
    except EmailFetchingError as e: # Custom exception already logged
        # Decide if to raise or return empty list, based on desired caller behavior
        pass # Logged, returning empty list by default
    except socket.gaierror as e: # DNS resolution error
        logger.error(f"Network error (DNS resolution) connecting to IMAP server {server}: {e}", exc_info=True)
    except socket.timeout:
        logger.error(f"Timeout connecting to IMAP server {server}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during email fetching for {email_user}: {e}", exc_info=True)
    finally:
        if mail:
            try:
                mail.logout()
                logger.info(f"Logged out from IMAP server for user: {email_user}")
            except Exception as e:
                logger.warning(f"Error during IMAP logout for {email_user}: {e}", exc_info=True)
    return emails


def get_email_content(email_message: email.message.EmailMessage):
    """
    Extracts plain text or HTML content from an EmailMessage object.
    Prefers plain text.
    """
    if not isinstance(email_message, email.message.EmailMessage):
        logger.warning("get_email_content received an invalid object type.")
        return ""

    # Try to get plain text first
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == 'text/plain' and 'attachment' not in content_disposition.lower():
                try:
                    logger.debug("Found text/plain part.")
                    return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                except (UnicodeDecodeError, AttributeError) as e:
                    logger.warning(f"Could not decode text/plain part with charset {part.get_content_charset()}: {e}. Falling back or skipping.")
                    # Could try a raw decode if specific charset fails:
                    # return part.get_payload(decode=True).decode('utf-8', errors='replace')

    # If no plain text found, try HTML (could also be in multipart)
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == 'text/html' and 'attachment' not in content_disposition.lower():
                try:
                    logger.debug("Found text/html part (no plain text was suitable).")
                    # You might want to strip HTML tags here to get plain text
                    # For now, returning raw HTML.
                    return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                except (UnicodeDecodeError, AttributeError) as e:
                    logger.warning(f"Could not decode text/html part with charset {part.get_content_charset()}: {e}.")
    else: # Not multipart
        content_type = email_message.get_content_type()
        if content_type == 'text/plain':
            try:
                logger.debug("Found non-multipart text/plain content.")
                return email_message.get_payload(decode=True).decode(email_message.get_content_charset() or 'utf-8', errors='replace')
            except (UnicodeDecodeError, AttributeError) as e:
                logger.warning(f"Could not decode non-multipart text/plain part: {e}")
        elif content_type == 'text/html': # Fallback for non-multipart HTML
             try:
                logger.debug("Found non-multipart text/html content.")
                return email_message.get_payload(decode=True).decode(email_message.get_content_charset() or 'utf-8', errors='replace')
             except (UnicodeDecodeError, AttributeError) as e:
                logger.warning(f"Could not decode non-multipart text/html part: {e}")


    logger.warning(f"No suitable plain text or HTML content found in email with subject: {email_message.get('Subject', 'N/A')}")
    return ""

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