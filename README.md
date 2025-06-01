# Project: tldr - AI-Powered Newsletter Summarizer

**Are you drowning in daily newsletters? "tldr" is your personal AI assistant to reclaim your time.**

{{## Note for AI Code Assistants (e.g., Cursor)
This `README.md` file is designed to be the primary source of truth for understanding the "tldr" project. Please analyze its contents thoroughly to grasp the project's scope, context, architecture, current state, and future roadmap before providing assistance or making suggestions.
}}

This project leverages the power of OpenAI's GPT models to automatically fetch, summarize, and deliver concise digests of content-rich newsletters, starting with Stratechery. Get the key insights without sifting through every word.

## The Problem
High-value newsletters like [Stratechery](https://stratechery.com/) provide excellent analysis but can quickly accumulate, leading to a backlog of unread content and missed insights.

## The Solution
"tldr" automates the process:
1.  **Monitors Your Inbox:** Checks for new unread emails from specified senders (e.g., Stratechery).
2.  **AI-Powered Summarization:** Utilizes OpenAI's API (currently `gpt-4o`) to generate comprehensive summaries.
3.  **Delivers Key Information:** Sends you an email containing:
    *   An executive summary.
    *   Key takeaways/keywords.
    *   The main summary.
    *   (Optional) The original email content for reference.

## Key Features
*   **Automated Workflow:** Set it up once, and get summaries delivered automatically.
*   **Intelligent Summarization:** Leverages advanced LLMs for high-quality, context-aware summaries.
*   **Customizable Prompts:** Tailor the summarization focus and output format via configuration.
*   **Handles Long Content:** Implements text chunking to process articles exceeding LLM token limits.
*   **Email Integration:** Seamlessly works with Gmail (via IMAP for fetching, SMTP for sending).
*   **Modular Design:** Code is organized into helpers for email, OpenAI interaction, and system utilities.
*   **Robust Logging & Error Handling:** Comprehensive logging to console and rotating files, with improved error management.

## How it Works (Technical Overview)
For a visual representation, see the [tldr-v1-workflow diagram](docs/tldr-v1-workflow.pdf).

The core process involves:
1.  **Configuration (`.config` file):** Securely stores API keys, email credentials, sender details, and custom summarization prompts.
2.  **Email Fetching (`src/tldr_email_helper.py`):**
    *   Connects to the specified Gmail account using `imaplib`.
    *   Searches for unread emails from the designated sender.
    *   Parses email content, extracting plain text or HTML.
3.  **Content Processing & Summarization (`src/tldr_openai_helper.py`):**
    *   Counts tokens using `tiktoken` for the configured OpenAI model (e.g., `gpt-4o`).
    *   If content exceeds token limits, it's split into manageable chunks.
    *   Each chunk (or the whole content if short enough) is sent to the OpenAI API with a structured prompt requesting specific summary components (executive summary, keywords, detailed summary).
    *   A cumulative summarization strategy is used for chunked content, where the summary of previous chunks informs the summarization of the current one.
4.  **Email Sending (`src/tldr_email_helper.py`):**
    *   Constructs a new email with the generated summary.
    *   Optionally appends the original email content.
    *   Sends the summary email to your target address using `smtplib`.
5.  **Execution (`src/main.py`):** Orchestrates the above steps. Designed to be run periodically (e.g., via a cron job).
6.  **Logging (`src/tldr_logger.py`):** All operations are logged to both the console and a rotating file (`tldr_app.log`) for easier debugging and monitoring.

## Requirements
*   A paid OpenAI account with API access.
*   A Gmail account with an [App Password](https://support.google.com/mail/answer/185833?hl=en) enabled (for security and to bypass 2FA for the script).
*   Python 3.9+ (as per current venv setup)
*   Ability to run Python scripts, potentially on an external server or Raspberry Pi for continuous operation.

## Setup & Configuration
1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd tldr
    ```
2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    ```
3.  **Install Dependencies:**
    *   Ensure you have `pip` installed and updated (`python3 -m pip install --upgrade pip`).
    *   Install required packages from `requirements.txt`:
    ```bash
    python3 -m pip install -r requirements.txt
    ```
4.  **Create Configuration File:**
    *   The project includes a template file named `.config.template` which lists all necessary and optional configuration keys.
    *   To create your personal `.config` file from this template, run one of the provided setup scripts from the project root directory (it will only copy if `.config` doesn't already exist):
        *   **Using the Python script:**
            ```bash
            python3 setup_config.py
            ```
        *   **Or, using the shell script (make executable first):**
            ```bash
            chmod +x setup_config.sh
            ./setup_config.sh
            ```
    *   **After running the script, it is CRUCIAL that you open the newly created `.config` file and carefully replace all placeholder values (e.g., "YOUR_GMAIL_USERNAME@gmail.com", "sk-YOUR_OPENAI_API_KEY") with your actual credentials and desired settings.**
        The `.config` file must be valid JSON. Refer to `.config.template` for the required structure and keys.
5.  **Set Permissions for `.config` (Important for security):**
    On Unix-like systems (macOS, Linux), restrict access to your `.config` file:
    ```bash
    chmod 600 .config
    ```
    This restricts read/write access to the owner only, protecting your credentials.
6.  **Run the Application:**
    From the project root directory:
    ```bash
    python3 -m src.main
    ```
    Consider setting this up as a cron job for automated daily execution.

## Running Tests
The project includes a suite of unit tests to ensure functionality and catch regressions.
1.  **Ensure Test Dependencies are Installed:**
    The `requirements.txt` file includes `pytest` and `pytest-mock`. If you followed the setup instructions, these should already be installed.
2.  **Run Tests:**
    From the project root directory, execute:
    ```bash
    python3 -m pytest
    ```
    You should see output indicating the number of tests run and their status (passed, failed, skipped).

## Technologies Used
*   **Language:** Python 3
*   **AI:** OpenAI API (GPT-4o)
*   **Email:** `imaplib` (fetching), `smtplib` (sending)
*   **Tokenization:** `tiktoken`
*   **Configuration:** JSON
*   **Logging:** Python's built-in `logging` module
*   **Testing:** `pytest`, `pytest-mock`
*   **Dependencies:** `openai`, `tiktoken`, `pytest`, `pytest-mock` (see `requirements.txt` for specific versions)

## Future Enhancements & Roadmap
*   **Test Mode Flag:** Implement an environment variable (e.g., `TLDR_ENV=TEST`) to use test data/accounts, smaller articles, or less expensive models, reducing costs during development and testing.
*   **Advanced Error Handling & Logging:** Integrated Python's `logging` module for robust error tracking and different log levels, outputting to a file for easier debugging of cron jobs. **(Completed)**
*   **Interactive Mode:** Allow users to reply to summary emails with questions, triggering further LLM interaction for deeper dives into the content.
*   **LLM Agnosticism:** Abstract the LLM interface to support other models/providers (e.g., Llama, Gemini, DeepSeek).
*   **Asynchronous Summarization:** Explore `asyncio` for concurrent processing of multiple emails to improve throughput.
*   **Web Interface (Potential Long-Term):** A simple web UI for configuration or viewing past summaries.
*   **Expanded Email Provider Support:** Allow configuration for email providers beyond Gmail.
*   **Enhanced Rich Content Parsing:** Improve extraction from complex HTML emails or explore ways to note/link to non-text media.