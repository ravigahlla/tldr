import imaplib
import smtplib
import email
from email.mime.text import MIMEText
import json
import requests  # to be able to check the given token limits
import tiktoken  # to count tokens, deal with token limits
import openai
from openai import OpenAI

open_ai_model = "gpt-4"
#open_ai_model = "text-embedding-3-large"
#llm_token_limit = 1000 # for testing purposes
llm_token_limit = 8192

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


def count_tokens(text):
    encoding = tiktoken.encoding_for_model(open_ai_model)
    number_of_tokens = len(encoding.encode(text))
    return number_of_tokens


def chunk_text(text_body, max_tokens, extra_tokens):
    """
    Chunk the given text so that each chunk has fewer than `max_tokens`,
    considering `extra_tokens` required for the role and response.

    Args:
    text (str): The text to be chunked.
    max_tokens (int): Maximum number of tokens allowed per chunk including extras.
    extra_tokens (int): Tokens required for additional elements like role, response.

    Returns:
    list: A list of text chunks.
    """
    words = text_body.split()
    current_chunk = []
    current_length = 0
    chunks = []

    for word in words:
        word_tokens = count_tokens(word)
        if current_length + word_tokens + extra_tokens > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(word)
        current_length += word_tokens

    # Don't forget to add the last chunk if there's remaining content.
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
            {"role": "system", "content": "You are a helpful assistant that summarizes text."},
            {"role": "user",
             "content": f"Summarize the following text between triple exclamation marks !!!{chunk}!!!. \
                State the name of this article, the date of the article, a one sentence executive summary, \
                and then the rest of the summary below. Use headings or other formatting, in order to \
                better present the information. \
                Before stating the summary, display a section called keywords, and list the key concepts \
                from the summary you will be displaying \
                Highlight any particular content that showcases emerging strategic trends in the \
                technology industry, or key technologies. \
                If the following in triple backticks isn't empty, then include this background context \
                in your summary '''{end_summary}'''"}
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
            print(f"Error: {e.error['message']}")

        #except openai.error.AuthenticationError as e:
        #    print(f"Error: {e.error['message']}")

        #except openai.error.PermissionDeniedError as e:
        #    print(f"Error: {e.error['message']}")

        except Exception as e:
            print(f"An unexpected error occurred: {str(e)}")

        # print(f"resp = {end_summary}")

    return end_summary


def send_email(user: object, password: object, recipient: object, subject: object, body: object, server: object = 'smtp.gmail.com', port: object = 587) -> object:
    '''

    Args:
        user: email of user
        password: email app password for user
        recipient: email of recipient
        subject: subject of email
        body: body of email
        server:
        port:

    Returns:

    '''

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = user
    msg['To'] = recipient

    with smtplib.SMTP(server, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


if __name__ == '__main__':
    # test load_api_key
    #print(load_api_key('test_email_subject')) # test method

    emails = fetch_emails(load_api_key('gmail_user'), load_api_key('gmail_app_pass'), load_api_key('sender_email'))

    #print(f'number of emails = {len(emails)}')
    print(f'llm_token_limit = {llm_token_limit}')

    # go through each email
    for email in emails:
        print(f"From = {email['from']}")
        print(f"Subject = {email['subject']}")
        #print(f"{email['body']}")

        # test if token count works
        #print(f"number of tokens in email body = {count_tokens(email['body'])}")

        # splice up the email content into chunks below the llm token limit (e.g., 4096)
        chunks = chunk_text(email['body'], llm_token_limit, 50)

        # test if chunked array is populated
        #print(f'number of chunks = {len(chunks)}')

        # now summarize the email
        summary = summarizer(chunks)

        #print(f"resp = {summary}")

        # email the summary back to me
        send_email(
            load_api_key('gmail_user'),
            load_api_key('gmail_app_pass'),
            'ravigahlla@gmail.com',
            f"Your ChatGPT summary of {email['subject']}",
            summary
        )