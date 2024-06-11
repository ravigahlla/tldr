import os
import json

import tldr_email_helper
import tldr_openai_helper
import tldr_system_helper


if __name__ == '__main__':
    # test load_api_key
    #print(load_api_key('test_email_subject')) # test method

    # check if .config exists
    #check_if_file_exists('../.config')


    emails = tldr_email_helper.fetch_emails(tldr_system_helper.load_key_from_config_file('gmail_user'),
                                            tldr_system_helper.load_key_from_config_file('gmail_app_pass'),
                                            tldr_system_helper.load_key_from_config_file('sender_email'))

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
        chunks = tldr_openai_helper.chunk_text(email_body, tldr_openai_helper.llm_token_limit, 100)

        # test if chunked array is populated
        #print(f'number of chunks = {len(chunks)}')

        # now summarize the email
        print("calling summarizer()...")
        summary = tldr_openai_helper.summarizer(chunks)

        #print(f"resp = {summary}")

        # email the summary back to me
        print("calling send_email()...")
        tldr_email_helper.send_email(1,
                                     tldr_system_helper.load_key_from_config_file('gmail_user'),
                                     tldr_system_helper.load_key_from_config_file('gmail_app_pass'),
                                     tldr_system_helper.load_key_from_config_file('gmail_user'),
                                     email['Subject'],
                                     summary,
                                     email)