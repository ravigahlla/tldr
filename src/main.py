import os
import json

import email
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
from email import policy

import json
import requests  # to be able to check the given token limits
import tiktoken  # to count tokens, deal with token limits
import openai
from openai import OpenAI


open_ai_model = "gpt-4"
#open_ai_model = "text-embedding-3-large"
#llm_token_limit = 1000 # for testing purposes
llm_token_limit = 8192


def load_api_key(key):
    """
    Get the value from the key in the hidden .config file
    Args:
        key: what you're trying to look up

    Returns: the value in the key-value pair from the config file

    """
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the absolute path to the .config file
    config_path = os.path.join(script_dir, '../.config')

    with open(config_path, 'r') as file:
        config = json.load(file)
        return config[key]

# fetch the emails


def check_if_file_exists(file):
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the absolute path to the .config file
    file_path = os.path.join(script_dir, file)

    if os.path.exists(file_path):
        print(f"{file} exists")
        try:
            with open(file_path, 'r') as file:
                config = json.load(file)
                print(f"{file} loaded successfully")
        except Exception as e:
            print(f"Error reading {file}: {e}")
    else:
        print(f"{file} does not exist")


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



def count_tokens(text):
    encoding = tiktoken.encoding_for_model(open_ai_model)
    number_of_tokens = len(encoding.encode(text))
    return number_of_tokens


def chunk_text(text_body, max_tokens, extra_tokens):
    """
    Chunk the given text so that each chunk has fewer than `max_tokens`,
    considering `extra_score` required for the role and response.

    Args:
    text_body (str): The text to be chunked.
    max_tokens (int): Maximum number of tokens allowed per chunk.
    extra_tokens (int): Tokens required for additional elements like role, response.

    Returns:
    list: A list of text chunks.
    """
    words = text_body.split()
    current_chunk = []
    current_length = 0
    chunks = []

    # Calculate the actual maximum tokens per chunk considering the extras
    effective_max_tokens = max_tokens - extra_tokens

    for word in words:
        word_tokens = count_tokens(word)  # Assume this function is accurate
        if current_length + word_tokens > effective_max_tokens:
            # When adding another word exceeds the effective max tokens, save the current chunk
            if current_chunk:  # Ensure we don't append an empty chunk
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
        current_chunk.append(word)
        current_length += word_tokens

    # Add the last chunk if there's remaining content
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def summarizer(chunks):
    '''
    takes a list of strings below the LLM token limit, traverse the list, and aggregate a summary
    :param chunks: the list of chunked strings
    :return: a summary string of the entire chunked strings
    '''

    client = OpenAI(api_key=load_api_key('openai_api_key'))

    end_summary = ''  # initial value of the summary will be empty

    for chunk in chunks:
        # print(f"orig = {chunk}") # for debugging
        # print(f"resp = {callLLM(chunk)}")

        try:
            completion = client.chat.completions.create(
            model=open_ai_model,  # Make sure you have access to this model
            messages=[
            {"role": "system", "content": "You are a helpful assistant that summarizes text into a readable format."},
            {"role": "user",
             "content": f"Summarize the text between triple exclamation marks \
                Return the summary in HTML formatting, for better readability \
                Have a section that states the exact name of this article, and the date of the article, \
                Have a section for 1 to 2 sentence executive summary, \
                Have a section called keywords, and list the key concepts from the summary in this section. \
                Then have a section that displays a 1 to 3 paragraph summary. Look for particular content which \
                showcases emerging strategic trends in the technology industry, or emerging technologies. \
                If the following background context in triple backticks isn't empty, then include this background \
                context in your analysis. \
                Background context: ```{end_summary}``` \
                Original text: !!!{chunk}!!!"
            }
            ],
            temperature = 0.7,
                # max_tokens=llm_token_limit,
            top_p = 1.0,
            frequency_penalty = 0.0,
            presence_penalty = 0.0
            )

            end_summary = completion.choices[0].message.content

        #except openai.error.RateLimitError as e:
        #    print(f"Error: {e.error['message']}")

        except openai.BadRequestError as e:
            print(f"Error: {e['message']}")

        #except openai.error.AuthenticationError as e:
        #    print(f"Error: {e.error['message']}")

        #except openai.error.PermissionDeniedError as e:
        #    print(f"Error: {e.error['message']}")

        except Exception as e:
            print(f"An unexpected error occurred: {str(e)}")

        # print(f"resp = {end_summary}")

    return end_summary


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


if __name__ == '__main__':
    # test load_api_key
    #print(load_api_key('test_email_subject')) # test method

    # check if .config exists
    #check_if_file_exists('../.config')

    emails = fetch_emails(load_api_key('gmail_user'), load_api_key('gmail_app_pass'), load_api_key('sender_email'))

    #print(f'number of emails = {len(emails)}')
    #print(f'llm_token_limit = {llm_token_limit}')

    # go through each email
    for email in emails:
        #print(f"From = {email['From']}")
        print(f"Summarizing: {email['Subject']}")

        print("calling get_email_content()...")
        email_body = get_email_content(email)  # Get the plain text content
        #print(body)  # Print the body of the email

        # test if token count works
        #print(f"number of tokens in email body = {count_tokens(email['body'])}")

        # splice up the email content into chunks below the llm token limit (e.g., 4096)
        print("calling chunk_text()...")
        chunks = chunk_text(email_body, llm_token_limit, 200)

        # test if chunked array is populated
        #print(f'number of chunks = {len(chunks)}')

        # now summarize the email
        print("calling summarizer()...")
        summary = summarizer(chunks)

        #print(f"resp = {summary}")

        # email the summary back to me
        print("calling send_email()...")
        send_email(1, load_api_key('gmail_user'), load_api_key('gmail_app_pass'), load_api_key('gmail_user'), email['Subject'], summary, email)