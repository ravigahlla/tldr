from tldr_system_helper import load_key_from_config_file, ConfigError
from tldr_logger import logger

import requests  # to be able to check the given token limits
import tiktoken  # to count tokens, deal with token limits
import openai
from openai import OpenAI

# --- Global variables - Consider making these configurable ---
# These should ideally be loaded from config or passed to functions.
# For now, keeping them but logging their use.
# open_ai_model_name = "gpt-4o" # Renamed for clarity
# llm_token_limit = 8192 # Example, might be model specific

# This variable is accessed by tldr_email_helper.py's get_config_info()
# It's better if main.py fetches this and passes it around.
# For now, we'll load it here to maintain current behavior, but flag it for refactoring.
try:
    open_ai_model = load_key_from_config_file("openai_model", default="gpt-4o")
    logger.info(f"OpenAI model set to: {open_ai_model} (from config or default)")
except ConfigError:
    open_ai_model = "gpt-4o" # Fallback if config loading itself fails catastrophically here
    logger.warning(f"Could not load 'openai_model' from config. Defaulting to {open_ai_model}.")

# Custom OpenAI related exceptions
class OpenAIError(Exception):
    """Base exception for OpenAI related errors in this module."""
    pass

class OpenAITokenizerError(OpenAIError):
    """Exception for errors during tokenization."""
    pass

class OpenAIAPIError(OpenAIError):
    """Exception for errors interacting with the OpenAI API."""
    pass

def count_tokens(text: str, model_name: str):
    """
    Counts the number of tokens in a given text string for a specific model.
    """
    if not text: # Handle empty string case
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model_name)
        number_of_tokens = len(encoding.encode(text))
        logger.debug(f"Counted {number_of_tokens} tokens for text (first 50 chars: '{text[:50]}...') using model {model_name}.")
        return number_of_tokens
    except KeyError as e: # tiktoken raises KeyError for unknown models
        logger.error(f"Unknown model name '{model_name}' for tiktoken encoding: {e}")
        raise OpenAITokenizerError(f"Failed to get encoding for model '{model_name}'. Is it a valid model for tiktoken?") from e
    except Exception as e:
        logger.error(f"An unexpected error occurred in count_tokens with model {model_name}: {e}", exc_info=True)
        raise OpenAITokenizerError(f"Token counting failed for model {model_name}.") from e


def chunk_text(text_body: str, model_name: str, max_tokens_per_chunk: int, overlap_tokens: int = 50):
    """
    Chunks text into pieces, each not exceeding max_tokens_per_chunk.
    Allows for overlapping tokens between chunks to maintain context.

    Args:
        text_body (str): The text to be chunked.
        model_name (str): The OpenAI model name (for token counting).
        max_tokens_per_chunk (int): Maximum number of tokens for each chunk.
        overlap_tokens (int): Number of tokens to overlap between chunks.

    Returns:
        list: A list of text chunks.
    """
    if not text_body:
        logger.info("chunk_text received empty text_body, returning empty list.")
        return []

    logger.info(f"Starting to chunk text. Total length: {len(text_body)} chars. Max tokens/chunk: {max_tokens_per_chunk}. Overlap: {overlap_tokens}.")
    
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError as e:
        logger.error(f"Cannot chunk text: Unknown model '{model_name}' for tiktoken: {e}")
        raise OpenAITokenizerError(f"Failed to get encoding for model '{model_name}' during chunking.") from e

    tokens = encoding.encode(text_body)
    total_tokens = len(tokens)
    logger.debug(f"Total tokens in text_body: {total_tokens}")

    if total_tokens == 0:
        logger.info("Text body resulted in zero tokens. Returning empty list of chunks.")
        return []
    
    if total_tokens <= max_tokens_per_chunk:
        logger.info("Text body is within a single chunk limit.")
        return [text_body]

    chunks = []
    current_pos = 0
    chunk_num = 1
    while current_pos < total_tokens:
        end_pos = min(current_pos + max_tokens_per_chunk, total_tokens)
        chunk_tokens = tokens[current_pos:end_pos]
        chunk_text_content = encoding.decode(chunk_tokens)
        chunks.append(chunk_text_content)
        
        logger.debug(f"Created chunk {chunk_num}: {len(chunk_tokens)} tokens, {len(chunk_text_content)} chars (approx). Current pos: {current_pos}, End pos: {end_pos}")
        
        if end_pos == total_tokens: # Reached the end
            break
        
        # Move current_pos, considering overlap
        # We want the next chunk to start 'overlap_tokens' before the end of the current one,
        # but ensure we make progress.
        advance_by = max_tokens_per_chunk - overlap_tokens
        if advance_by <= 0 : # Ensure progress if overlap is too large
            logger.warning("Overlap tokens >= max_tokens_per_chunk. Advancing by a small fixed amount to prevent infinite loop.")
            advance_by = max_tokens_per_chunk // 2 if max_tokens_per_chunk > 1 else 1

        current_pos += advance_by
        chunk_num += 1
        if current_pos >= total_tokens: # Ensure we don't start past the end
             break


    logger.info(f"Text chunking complete. Produced {len(chunks)} chunks.")
    return chunks


def summarize_text_chunks(chunks: list, client: openai.OpenAI, model_to_use: str, system_prompt: str, user_prompt_template: str, initial_context: str = ""):
    """
    Summarizes a list of text chunks using a cumulative approach.

    Args:
        chunks (list): List of text strings (chunks).
        client (openai.OpenAI): Initialized OpenAI client.
        model_to_use (str): The OpenAI model for summarization.
        system_prompt (str): The system message for the LLM.
        user_prompt_template (str): User message template, should accept {article_chunk} and {current_summary}.
        initial_context (str): Optional initial context to start the summarization.

    Returns:
        str: The final aggregated summary, or None if summarization fails.
    """
    if not chunks:
        logger.info("No chunks provided to summarize_text_chunks.")
        return initial_context or "" # Return empty or initial context if no chunks

    cumulative_summary = initial_context
    logger.info(f"Starting summarization for {len(chunks)} chunks using model {model_to_use}.")

    for i, chunk in enumerate(chunks):
        logger.info(f"Summarizing chunk {i+1}/{len(chunks)}. Chunk length: {len(chunk)} chars.")
        logger.debug(f"Current cumulative summary length for context: {len(cumulative_summary)} chars.")
        
        # Ensure user_prompt_template can handle both keys if they are distinct
        # Or adjust the template to combine them as needed.
        # For example, your original summarizer prompt combined background_context and original_text
        # This example assumes user_prompt_template has placeholders like:
        # "Background: {current_summary}\n\nSummarize this: {article_chunk}"
        # Adapt as per your actual prompt structure.
        
        # Formatted prompt including current cumulative summary as context
        # Assuming your original summarizer function's prompt is the base
        delimiter = "####" # From your original prompt
        try:
            prompt_focus = load_key_from_config_file('prompt_focus', default="")
        except ConfigError:
            logger.warning("Could not load 'prompt_focus' from config for summarizer. Using empty default.")
            prompt_focus = ""

        # Reconstruct a prompt similar to your original 'summarizer' function's logic
        # This is a direct adaptation. Consider simplifying the prompt or making it more configurable.
        current_user_prompt = (
            f"Summarize the text delimited using the following identifier: {delimiter}\n"
            f"Return the summary in HTML formatting.\n"
            f"Have a section that states the exact name and date of this article (if discernible).\n"
            f"Have a section for 1 to 2 sentence high-level executive summary.\n"
            f"Have a section for keywords, and list horizontally the key concepts from the summary.\n"
            f"Then a section for the 1 to 3 paragraph summary itself. {prompt_focus}\n"
            f"If the following background context delimited by {delimiter} isn't empty, include this information "
            f"in your overall analysis. It is not a separate section, just additional information.\n"
            f"Background context: {delimiter}{cumulative_summary}{delimiter}\n"
            f"Original text for this chunk: {delimiter}{chunk}{delimiter}"
        )

        try:
            logger.debug(f"Sending request to OpenAI for chunk {i+1}. System prompt: '{system_prompt[:100]}...', User prompt starts with: '{current_user_prompt[:100]}...'")
            
            completion = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": current_user_prompt}
                ],
                temperature=0.7, # Consider making these configurable
                # max_tokens=llm_token_limit, # This is often an output token limit, not input context.
                                              # The input context window is inherent to the model.
                                              # If needed, set based on expected summary length.
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            chunk_summary = completion.choices[0].message.content.strip()
            if not chunk_summary:
                logger.warning(f"OpenAI returned an empty summary for chunk {i+1}. Using previous summary as context for next.")
            else:
                logger.info(f"Received summary for chunk {i+1}. Length: {len(chunk_summary)} chars.")
                cumulative_summary = chunk_summary # The new summary becomes the context for the next chunk

            # Optional: Add a small delay if you're processing many chunks to respect rate limits
            # import time
            # time.sleep(1) # 1 second delay

        except openai.APIConnectionError as e:
            logger.error(f"OpenAI API Connection Error for chunk {i+1}: {e}", exc_info=True)
            # Decide: retry, skip chunk, or abort. For now, abort this summarization.
            raise OpenAIAPIError(f"API Connection Error during summarization of chunk {i+1}: {e}") from e
        except openai.RateLimitError as e:
            logger.warning(f"OpenAI Rate Limit Exceeded for chunk {i+1}: {e}. Consider implementing backoff/retry or reducing request frequency.", exc_info=True)
            # Decide: retry, skip, or abort.
            raise OpenAIAPIError(f"Rate Limit Error during summarization of chunk {i+1}: {e}") from e
        except openai.AuthenticationError as e: # This is critical
            logger.error(f"OpenAI Authentication Error: {e}. Check your API key configuration.", exc_info=True)
            raise OpenAIAPIError(f"Authentication Error: {e}") from e # Re-raise critical error
        except openai.BadRequestError as e: # Often due to prompt issues or exceeding context window
            # The new API (v1.x) provides more structured error details.
            # e.g. e.body might contain {'error': {'message': '...', 'type': '...', 'param': '...', 'code': '...'}}
            error_body = e.body if hasattr(e, 'body') and e.body else {}
            error_message = error_body.get('error', {}).get('message', str(e))
            logger.error(f"OpenAI Bad Request Error for chunk {i+1}: {error_message}. This could be due to prompt length or content issues.", exc_info=True)
            # This might indicate the cumulative summary + new chunk is too large.
            # Consider strategies: use previous summary, shorten context, or abort.
            raise OpenAIAPIError(f"Bad Request Error (possibly token limit) for chunk {i+1}: {error_message}") from e
        except openai.APIError as e: # Catch other specific API errors from OpenAI
            logger.error(f"OpenAI API Error for chunk {i+1}: Status Code={e.status_code}, Error Type={e.type}, Message={e.message}", exc_info=True)
            raise OpenAIAPIError(f"Generic API Error for chunk {i+1}: {e}") from e
        except Exception as e:
            logger.exception(f"An unexpected error occurred during OpenAI call for chunk {i+1}: {e}")
            # Abort summarization for this set of chunks
            raise OpenAIError(f"Unexpected error during summarization of chunk {i+1}: {e}") from e

    logger.info("Successfully completed summarization of all chunks.")
    return cumulative_summary
