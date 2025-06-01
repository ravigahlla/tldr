import sys
import openai # For the OpenAI client and its specific exceptions

# Initialize logger as the first thing
# Assuming tldr_logger.py is in the same directory (src)
# and logger instance is created there.
try:
    from .tldr_logger import logger
except ImportError: # Fallback for running script directly in src for dev
    from tldr_logger import logger
    logger.warning("Running main.py with fallback logger import. Ensure PYTHONPATH is correct for module execution.")


# Import helper modules and custom exceptions
try:
    from . import tldr_email_helper
    from . import tldr_openai_helper
    from . import tldr_system_helper
    from .tldr_system_helper import ConfigError # Specific exception for config issues
    from .tldr_email_helper import EmailConnectionError, EmailFetchingError, EmailSendingError
    from .tldr_openai_helper import OpenAIError, OpenAITokenizerError, OpenAIAPIError
except ImportError: # Fallback for running script directly in src
    import tldr_email_helper
    import tldr_openai_helper
    import tldr_system_helper
    from tldr_system_helper import ConfigError
    from tldr_email_helper import EmailConnectionError, EmailFetchingError, EmailSendingError
    from tldr_openai_helper import OpenAIError, OpenAITokenizerError, OpenAIAPIError
    logger.warning("Running main.py with fallback helper imports.")


# Configuration constants (consider moving more to .config if they change often)
DEFAULT_IMAP_HOST = "imap.gmail.com"
DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT_SSL = 465 # For SMTP_SSL
DEFAULT_SMTP_PORT_TLS = 587 # For SMTP with STARTTLS
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS_PER_CHUNK = 4000 # Max tokens for each text chunk before sending to LLM
DEFAULT_CHUNK_OVERLAP_TOKENS = 200  # Overlap between chunks
DEFAULT_SYSTEM_PROMPT = "You are an expert assistant that summarizes articles into a well-structured HTML format."
# The detailed user prompt is now constructed within tldr_openai_helper.summarize_text_chunks


def main_process():
    """
    Main orchestration function for the TLDR newsletter summarizer.
    """
    logger.info("====================================================")
    logger.info("Starting tldr summarization process...")
    
    configs = None # Initialize to None
    imap_connection = None # Initialize IMAP connection variable

    try:
        # 1. Load Configuration
        logger.info("Loading configurations...")
        # Load critical configurations first
        critical_configs = tldr_system_helper.load_critical_configs() # This will raise ConfigError if critical ones are missing

        # Load other configurations with defaults
        # These keys should match what's in your .config or have sensible defaults
        configs = {
            **critical_configs, # Merge critical configs
            "imap_host": tldr_system_helper.load_key_from_config_file("imap_host", default=DEFAULT_IMAP_HOST),
            "smtp_host": tldr_system_helper.load_key_from_config_file("smtp_host", default=DEFAULT_SMTP_HOST),
            "smtp_port": int(tldr_system_helper.load_key_from_config_file("smtp_port", default=str(DEFAULT_SMTP_PORT_SSL))), # Default to SSL port
            "openai_model_name": tldr_system_helper.load_key_from_config_file("openai_model_name", default=DEFAULT_OPENAI_MODEL),
            "max_tokens_per_chunk": int(tldr_system_helper.load_key_from_config_file("max_tokens_per_chunk", default=str(DEFAULT_MAX_TOKENS_PER_CHUNK))),
            "chunk_overlap_tokens": int(tldr_system_helper.load_key_from_config_file("chunk_overlap_tokens", default=str(DEFAULT_CHUNK_OVERLAP_TOKENS))),
            "system_prompt": tldr_system_helper.load_key_from_config_file("system_prompt", default=DEFAULT_SYSTEM_PROMPT),
            # "forward_original_email": tldr_system_helper.load_key_from_config_file("forward_original_email", default="true").lower() == 'true',
            # prompt_focus is loaded within summarize_text_chunks in tldr_openai_helper
        }

        # Handle forward_original_email separately to correctly interpret boolean or string "true"/"false"
        forward_email_config_value = tldr_system_helper.load_key_from_config_file("forward_original_email", default="true")
        if isinstance(forward_email_config_value, bool):
            configs["forward_original_email"] = forward_email_config_value
        else: # Assume string if not bool
            configs["forward_original_email"] = str(forward_email_config_value).lower() == 'true'
        
        logger.info("Configurations loaded successfully.")
        logger.debug(f"Effective configurations: { {k: ('******' if 'password' in k or 'key' in k else v) for k, v in configs.items()} }")

        # 2. Initialize OpenAI Client
        logger.info(f"Initializing OpenAI client for model: {configs['openai_model_name']}")
        try:
            openai_client = openai.OpenAI(api_key=configs["openai_api_key"])
            # Quick test call (optional, but good for early failure detection)
            # openai_client.models.list() 
            # logger.info("OpenAI client initialized and connection tested successfully.")
        except openai.AuthenticationError as e: # Though load_critical_configs should catch missing key
            logger.critical(f"OpenAI Authentication Error during client initialization: {e}. API Key might be invalid despite being present.", exc_info=True)
            raise OpenAIAPIError(f"OpenAI Authentication Failed: {e}") from e # Re-raise specific error
        except Exception as e:
            logger.critical(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            raise OpenAIError(f"OpenAI client initialization failed: {e}") from e

        # 3. Establish IMAP Connection
        logger.info(f"Establishing IMAP connection to {configs['imap_host']} for user {configs['gmail_user']}")
        imap_connection = tldr_email_helper.connect_to_imap(
            email_user=configs["gmail_user"],
            email_password=configs["gmail_app_pass"], # Assuming this is the correct key
            server=configs["imap_host"]
            # port can be added if configurable, otherwise uses default from helper
        )
        # connect_to_imap will raise EmailConnectionError if it fails, caught by outer try-except

        # 4. Email Fetching (using the established connection)
        logger.info(f"Attempting to fetch emails from sender: {configs['stratechery_sender_email']}")
        # fetch_emails now returns List[Tuple[uid_bytes, email_message_object]]
        fetched_email_data = tldr_email_helper.fetch_emails(
            mail_conn=imap_connection, # Pass the active connection
            sender_email=configs["stratechery_sender_email"]
        )

        if not fetched_email_data:
            logger.info("No new unread emails found to process.")
            # No "return" here yet, as we need to ensure logout in finally
        else:
            logger.info(f"Fetched {len(fetched_email_data)} email(s) for processing.")

            uids_to_mark_read = [] # Collect UIDs of successfully processed emails

            # 5. Process Each Email
            for uid_bytes, email_msg_obj in fetched_email_data:
                email_subject = email_msg_obj.get('Subject', f"Email UID {uid_bytes.decode()} (No Subject)")
                logger.info(f"--- Processing email UID {uid_bytes.decode()}: '{email_subject}' ---")

                try:
                    email_body_text = tldr_email_helper.get_email_content(email_msg_obj)
                    if not email_body_text:
                        logger.warning(f"Could not extract text content from email: '{email_subject}'. Skipping.")
                        continue
                    logger.debug(f"Extracted email body. Length: {len(email_body_text)} chars.")

                    # Chunking the text
                    logger.info(f"Chunking email body for '{email_subject}'...")
                    text_chunks = tldr_openai_helper.chunk_text(
                        text_body=email_body_text,
                        model_name=configs["openai_model_name"], # For token counting
                        max_tokens_per_chunk=configs["max_tokens_per_chunk"],
                        overlap_tokens=configs["chunk_overlap_tokens"]
                    )

                    if not text_chunks:
                        logger.warning(f"Email body for '{email_subject}' resulted in no chunks. Skipping.")
                        continue
                    logger.info(f"Email body chunked into {len(text_chunks)} parts for '{email_subject}'.")

                    # Summarization
                    logger.info(f"Starting summarization for '{email_subject}' using model {configs['openai_model_name']}...")
                    # The detailed user prompt is now constructed within summarize_text_chunks
                    # based on its internal logic and 'prompt_focus' from config.
                    summary_html = tldr_openai_helper.summarize_text_chunks(
                        chunks=text_chunks,
                        client=openai_client,
                        model_to_use=configs["openai_model_name"],
                        system_prompt=configs["system_prompt"],
                        user_prompt_template="" # This is not directly used if summarize_text_chunks builds its own full user prompt.
                                              # Keep for future flexibility or pass specific parts if helper is refactored.
                    )

                    if not summary_html:
                        logger.error(f"Failed to generate summary for '{email_subject}'. Skipping this email.")
                        continue
                    logger.info(f"Successfully generated summary for '{email_subject}'. Summary length: {len(summary_html)} chars.")

                    # Email Sending
                    summary_email_subject = f"tldr Summary: {email_subject}"
                    logger.info(f"Sending summary email for '{email_subject}' to {configs['target_email']}")
                    
                    send_success = tldr_email_helper.send_email(
                        is_forward_orig_email=configs["forward_original_email"],
                        user=configs["gmail_user"],
                        password=configs["gmail_app_pass"],
                        recipient=configs["target_email"],
                        subject=summary_email_subject,
                        body_html=summary_html,
                        original_email_msg=email_msg_obj if configs["forward_original_email"] else None,
                        server=configs["smtp_host"],
                        port=configs["smtp_port"]
                    )

                    if send_success:
                        logger.info(f"Summary email for '{email_subject}' (UID {uid_bytes.decode()}) sent successfully.")
                        uids_to_mark_read.append(uid_bytes) # Add UID to mark as read
                    else:
                        logger.error(f"Failed to send summary email for '{email_subject}' (UID {uid_bytes.decode()}). Original email will not be marked as read.")
                
                except OpenAITokenizerError as e:
                    logger.error(f"Tokenizer error processing email UID {uid_bytes.decode()} '{email_subject}': {e}. Skipping.", exc_info=True)
                except OpenAIAPIError as e:
                    logger.error(f"OpenAI API error processing email UID {uid_bytes.decode()} '{email_subject}': {e}. Skipping.", exc_info=True)
                except OpenAIError as e:
                    logger.error(f"OpenAI related error processing email UID {uid_bytes.decode()} '{email_subject}': {e}. Skipping.", exc_info=True)
                except EmailSendingError as e:
                     logger.error(f"Failed to send summary email for UID {uid_bytes.decode()} '{email_subject}' due to: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"An unexpected error occurred while processing email UID {uid_bytes.decode()} '{email_subject}': {e}. Skipping.", exc_info=True)
                finally:
                    logger.info(f"--- Finished processing email UID {uid_bytes.decode()}: '{email_subject}' ---")

            # After processing all emails, mark the successfully processed ones as read
            if uids_to_mark_read:
                logger.info(f"Attempting to mark {len(uids_to_mark_read)} emails as read.")
                mark_success = tldr_email_helper.mark_emails_as_read(imap_connection, uids_to_mark_read)
                if mark_success:
                    logger.info("Successfully marked processed emails as read.")
                else:
                    logger.warning("Failed to mark some or all processed emails as read. They might be picked up again in the next run.")
            else:
                logger.info("No emails were successfully processed to be marked as read.")


    except ConfigError as e:
        logger.critical(f"Halting: Critical configuration error: {e}", exc_info=True)
        sys.exit(1) # Exit if critical configs are missing/invalid
    except EmailConnectionError as e: # Catches error from connect_to_imap
        logger.critical(f"Halting: Could not connect to email server: {e}", exc_info=True)
        sys.exit(1)
    except EmailFetchingError as e: # Catches error from fetch_emails (if it re-raises critical ones)
        logger.critical(f"Halting: Error fetching emails: {e}", exc_info=True)
        sys.exit(1)
    except (OpenAIAPIError, OpenAIError) as e: # From OpenAI client init or other pre-loop OpenAI issues
        logger.critical(f"Halting: An OpenAI related error occurred: {e}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user (KeyboardInterrupt). Shutting down.")
        # Logout will be handled by finally
        sys.exit(0)
    except Exception as e:
        logger.critical(f"An unhandled critical error occurred in the main process: {e}", exc_info=True)
        # Logout will be handled by finally
        sys.exit(1) # Exit for any other unhandled critical errors
    finally:
        if imap_connection:
            logger.info("Closing IMAP connection.")
            tldr_email_helper.close_imap_connection(imap_connection)
        
        if not fetched_email_data and imap_connection : # Check if we exited early due to no emails
             logger.info("tldr process finished: No new emails.")

        logger.info("tldr summarization process finished.")
        logger.info("====================================================")

if __name__ == '__main__':
    main_process()