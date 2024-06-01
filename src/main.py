import os
import json

import tldr_email_helper

import requests  # to be able to check the given token limits
import tiktoken  # to count tokens, deal with token limits
import openai
from openai import OpenAI

open_ai_model = "gpt-4"
#open_ai_model = "text-embedding-3-large"
#llm_token_limit = 1000 # for testing purposes
llm_token_limit = 8192


def load_key_from_config_file(key):
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

    client = OpenAI(api_key=load_key_from_config_file('openai_api_key'))

    end_summary = ''  # initial value of the summary will be empty

    for chunk in chunks:
        # print(f"orig = {chunk}") # for debugging
        # print(f"resp = {callLLM(chunk)}")

        delimiter = "####"
        try:
            prompt_focus = load_key_from_config_file('prompt_focus')
            #print("prompt specifier exists")
        except KeyError:
            prompt_focus = ""
            #print("prompt specifier doesn't exist")

        try:
            completion = client.chat.completions.create(
            model=open_ai_model,  # Make sure you have access to this model
            messages=[
            {"role": "system", "content": "You are an assistant that summarizes text into a readable format."},
            {"role": "user",
             "content": f"Summarize the text delimited using the following identifier: {delimiter}  \
                Return the summary in HTML formatting, for better readability \
                Have a section that states the exact name of this article, and the date of the article, \
                Have a section for 1 to 2 sentence executive summary, \
                Have a section called keywords, and list the key concepts from the summary in this section. \
                Then a section for a 1 to 3 paragraph summary. {prompt_focus}. \
                If the following background context delimited by {delimiter} isn't empty, then include this background \
                context in your analysis. \
                Background context: {delimiter}{end_summary}{delimiter} \
                Original text: {delimiter}{chunk}{delimiter}"
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


if __name__ == '__main__':
    # test load_api_key
    #print(load_api_key('test_email_subject')) # test method

    # check if .config exists
    #check_if_file_exists('../.config')


    emails = tldr_email_helper.fetch_emails(load_key_from_config_file('gmail_user'), load_key_from_config_file('gmail_app_pass'), load_key_from_config_file('sender_email'))

    #print(f'number of emails = {len(emails)}')
    #print(f'llm_token_limit = {llm_token_limit}')

    # go through each email
    for email in emails:
        #print(f"From = {email['From']}")
        print(f"Summarizing: {email['Subject']}")

        print("calling get_email_content()...")
        email_body = tldr_email_helper.get_email_content(email)  # Get the plain text content
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
        tldr_email_helper.send_email(1, load_key_from_config_file('gmail_user'), load_key_from_config_file('gmail_app_pass'), load_key_from_config_file('gmail_user'), email['Subject'], summary, email)