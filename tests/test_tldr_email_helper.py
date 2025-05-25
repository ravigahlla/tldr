import pytest
import imaplib
import smtplib
import socket # For socket.gaierror, socket.timeout
from email.message import EmailMessage
from unittest.mock import MagicMock, patch, call # import call for checking multiple calls

# Adjust import path
try:
    from src.tldr_email_helper import (
        fetch_emails, get_email_content, send_email,
        EmailConnectionError, EmailFetchingError, EmailSendingError
    )
    from src.tldr_logger import logger # For caplog access if needed
except ImportError:
    import sys, os
    PROJECT_ROOT_FOR_TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT_FOR_TESTS not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)
    from src.tldr_email_helper import (
        fetch_emails, get_email_content, send_email,
        EmailConnectionError, EmailFetchingError, EmailSendingError
    )
    from src.tldr_logger import logger


# Patch where imaplib.IMAP4_SSL is looked up (i.e., in tldr_email_helper module)
@patch('src.tldr_email_helper.imaplib.IMAP4_SSL')
def test_fetch_emails_success(mock_imap_ssl_constructor, caplog):
    mock_mail_instance = MagicMock()
    mock_imap_ssl_constructor.return_value = mock_mail_instance

    mock_mail_instance.login = MagicMock(return_value=('OK', [b'Login successful']))
    mock_mail_instance.select = MagicMock(return_value=('OK', [b'Inbox selected']))
    mock_mail_instance.search = MagicMock(return_value=('OK', [b'1 2'])) # Two email IDs as bytes
    mock_mail_instance.logout = MagicMock()

    email_data_1_bytes = b'Subject: Test Email 1\r\n\r\nBody 1'
    email_data_2_bytes = b'Subject: Test Email 2\r\n\r\nBody 2'
    mock_mail_instance.fetch.side_effect = [
        ('OK', [(b'1 (RFC822 {len(email_data_1_bytes)})', email_data_1_bytes)]), # RFC822 response format
        ('OK', [(b'2 (RFC822 {len(email_data_2_bytes)})', email_data_2_bytes)])
    ]

    emails = fetch_emails("user", "pass", "sender@example.com", server="my.imap.server")
    
    assert len(emails) == 2
    assert isinstance(emails[0], EmailMessage)
    assert emails[0]['Subject'] == 'Test Email 1'
    assert emails[1]['Subject'] == 'Test Email 2'
    assert "Successfully logged into IMAP server" in caplog.text
    mock_imap_ssl_constructor.assert_called_once_with("my.imap.server")
    mock_mail_instance.login.assert_called_once_with("user", "pass")
    mock_mail_instance.select.assert_called_once_with('inbox', readonly=True)
    mock_mail_instance.search.assert_called_once_with(None, '(UNSEEN FROM "sender@example.com")')
    assert mock_mail_instance.fetch.call_count == 2
    mock_mail_instance.fetch.assert_any_call(b'1', '(RFC822)') # Check calls with bytes
    mock_mail_instance.fetch.assert_any_call(b'2', '(RFC822)')
    mock_mail_instance.logout.assert_called_once()


@patch('src.tldr_email_helper.imaplib.IMAP4_SSL')
def test_fetch_emails_login_failure(mock_imap_ssl_constructor, caplog):
    mock_mail_instance = MagicMock()
    mock_imap_ssl_constructor.return_value = mock_mail_instance
    mock_mail_instance.login = MagicMock(return_value=('NO', [b'Authentication credentials invalid']))
    mock_mail_instance.logout = MagicMock()

    with pytest.raises(EmailConnectionError) as excinfo:
        fetch_emails("user", "wrongpass", "sender@example.com")
    
    assert "IMAP login failed" in str(excinfo.value)
    assert "Authentication credentials invalid" in str(excinfo.value)
    assert "IMAP login failed for user user" in caplog.text
    assert "Server response: Authentication credentials invalid" in caplog.text
    mock_mail_instance.logout.assert_called_once()


@patch('src.tldr_email_helper.imaplib.IMAP4_SSL')
def test_fetch_emails_no_emails_found(mock_imap_ssl_constructor, caplog):
    mock_mail_instance = MagicMock()
    mock_imap_ssl_constructor.return_value = mock_mail_instance
    mock_mail_instance.login.return_value = ('OK', [b'Login successful'])
    mock_mail_instance.select.return_value = ('OK', [b'Inbox selected'])
    mock_mail_instance.search.return_value = ('OK', [b'']) # Empty byte string for no emails

    emails = fetch_emails("user", "pass", "sender@example.com")
    assert len(emails) == 0
    assert "No new unread emails found from: sender@example.com" in caplog.text
    mock_mail_instance.logout.assert_called_once()

# Add more tests for fetch_emails: select fails, search fails, individual fetch fails, network errors etc.

def test_get_email_content_plain_text_preferred():
    msg = EmailMessage()
    msg.set_content("This is plain text.") # This creates a text/plain part
    msg.add_alternative("<html><body>This is HTML</body></html>", subtype='html')
    
    content = get_email_content(msg)
    assert content == "This is plain text.\n"

def test_get_email_content_html_fallback():
    msg = EmailMessage()
    # Only HTML part, no plain text. set_content can create html directly
    msg.set_content("<html><body><b>HTML</b> only</body></html>", subtype='html')
    
    content = get_email_content(msg)
    assert content == "<html><body><b>HTML</b> only</body></html>\n"

def test_get_email_content_multipart_mixed_plain_first():
    msg = EmailMessage()
    msg['Subject'] = 'Multipart Mixed Test'
    msg.add_header('Content-Type', 'multipart/mixed')
    
    text_part = EmailMessage()
    text_part.set_content('This is the main plain text.')
    msg.attach(text_part)
    
    html_part = EmailMessage()
    html_part.set_content('<html><body>HTML here</body></html>', subtype='html')
    msg.attach(html_part)
    
    content = get_email_content(msg)
    assert content == 'This is the main plain text.\n'

# Add more get_email_content tests: no suitable content, specific charsets, attachments.

@patch('src.tldr_email_helper.smtplib.SMTP_SSL')
@patch('src.tldr_email_helper.get_config_info', return_value="Model: Test<br><br>") # Mock helper
def test_send_email_success_ssl(mock_get_config, mock_smtp_ssl_constructor, caplog):
    mock_smtp_server = MagicMock()
    mock_smtp_ssl_constructor.return_value = mock_smtp_server

    mock_smtp_server.login = MagicMock()
    mock_smtp_server.send_message = MagicMock()
    mock_smtp_server.quit = MagicMock()

    success = send_email(
        is_forward_orig_email=False, user="sender@example.com", password="app_password",
        recipient="receiver@example.com", subject="Summary Subject", body_html="<p>Summary Body</p>",
        server="smtp.example.com", port=465 # SSL Port
    )
    assert success is True
    mock_smtp_ssl_constructor.assert_called_once_with("smtp.example.com", 465, timeout=30)
    mock_smtp_server.login.assert_called_once_with("sender@example.com", "app_password")
    mock_smtp_server.send_message.assert_called_once() # Check that some message was sent
    mock_smtp_server.quit.assert_called_once()
    assert "Email successfully sent to: receiver@example.com" in caplog.text


@patch('src.tldr_email_helper.smtplib.SMTP') # For STARTTLS
@patch('src.tldr_email_helper.get_config_info', return_value="Model: Test<br><br>")
def test_send_email_auth_failure_starttls(mock_get_config, mock_smtp_constructor, caplog):
    mock_smtp_server = MagicMock()
    mock_smtp_constructor.return_value = mock_smtp_server
    
    mock_smtp_server.starttls = MagicMock()
    mock_smtp_server.login = MagicMock(side_effect=smtplib.SMTPAuthenticationError(535, b"Authentication credentials invalid"))
    mock_smtp_server.quit = MagicMock()

    success = send_email(
        is_forward_orig_email=False, user="sender@example.com", password="wrong_password",
        recipient="receiver@example.com", subject="Test Auth Fail", body_html="<p>Body</p>",
        server="smtp.example.com", port=587 # STARTTLS Port
    )
    assert success is False
    mock_smtp_constructor.assert_called_once_with("smtp.example.com", 587, timeout=30)
    mock_smtp_server.starttls.assert_called_once()
    mock_smtp_server.login.assert_called_once_with("sender@example.com", "wrong_password")
    assert "SMTP authentication failed for user sender@example.com" in caplog.text
    assert "535" in caplog.text # Check for error code
    assert "Authentication credentials invalid" in caplog.text # Check for server message
    mock_smtp_server.quit.assert_called_once()


# Add more tests for send_email: socket errors, other SMTP exceptions, forwarding logic. 