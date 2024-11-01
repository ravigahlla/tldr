from tldr_system_helper import load_key_from_config_file

import requests  # to be able to check the given token limits
import tiktoken  # to count tokens, deal with token limits
import openai
from openai import OpenAI

open_ai_model = "gpt-4o"
#open_ai_model = "text-embedding-3-large"
#llm_token_limit = 1000 # for testing purposes
llm_token_limit = 8192

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
                Have a section for 1 to 2 sentence high-level summary, \
                Have a section called keywords, and list horizontally the key concepts from the summary. \
                Then a section for the 1 to 3 paragraph summary itself. {prompt_focus}. \
                If the following background context delimited by {delimiter} isn't empty, include this information \
                in your overall analysis. It is not a separate section, just additional information. \
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

        except openai.RateLimitError as e:
            print(f"Error: {e['message']}")

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
