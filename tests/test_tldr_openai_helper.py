import pytest
import openai # For openai specific error classes
from unittest.mock import MagicMock, patch, call

# Adjust import path
try:
    from src.tldr_openai_helper import (
        count_tokens, chunk_text, summarize_text_chunks,
        OpenAITokenizerError, OpenAIAPIError, OpenAIError, open_ai_model as global_open_ai_model # For checking default model
    )
    from src.tldr_system_helper import load_key_from_config_file # If directly used or for mocking
    from src.tldr_logger import logger # For caplog
except ImportError:
    import sys, os
    PROJECT_ROOT_FOR_TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT_FOR_TESTS not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)
    from src.tldr_openai_helper import (
        count_tokens, chunk_text, summarize_text_chunks,
        OpenAITokenizerError, OpenAIAPIError, OpenAIError, open_ai_model as global_open_ai_model
    )
    from src.tldr_system_helper import load_key_from_config_file
    from src.tldr_logger import logger


# Test count_tokens
def test_count_tokens_success():
    # This test directly uses tiktoken. It's more of an integration test for tiktoken itself.
    # A pure unit test would mock `tiktoken.encoding_for_model().encode`.
    assert count_tokens("hello world", "gpt-4o") == 2
    assert count_tokens("", "gpt-4o") == 0 # Empty string

def test_count_tokens_unknown_model_raises_error():
    with pytest.raises(OpenAITokenizerError) as excinfo:
        count_tokens("test text", "nonexistent-model-for-tiktoken")
    assert "Failed to get encoding for model 'nonexistent-model-for-tiktoken'" in str(excinfo.value)

# Test chunk_text
# Mocking tiktoken for more controlled chunk_text tests
@patch('src.tldr_openai_helper.tiktoken.encoding_for_model')
def test_chunk_text_basic_scenario(mock_encoding_for_model):
    # Setup mock encoder
    mock_encoder = MagicMock()
    # Simulate tokenization: each word is a token
    mock_encoder.encode.side_effect = lambda text: text.split() if text else []
    # Simulate detokenization: join tokens with space
    mock_encoder.decode.side_effect = lambda tokens: " ".join(tokens)
    mock_encoding_for_model.return_value = mock_encoder

    text_body = "one two three four five six seven eight nine ten" # 10 "tokens"
    model_name = "gpt-4o" # Or any model name, as tiktoken is mocked
    max_tokens_chunk = 4
    overlap = 1

    chunks = chunk_text(text_body, model_name, max_tokens_chunk, overlap_tokens=overlap)
    
    assert mock_encoding_for_model.called_once_with(model_name)
    assert len(chunks) == 3 # (10 tokens) / (4 - 1 effective advance) = 10/3 -> 3 full, 1 partial
                           # Chunk1: 1 2 3 4 (len 4) -> next starts at 1+4-1 = 4th token (index 3)
                           # Chunk2: 4 5 6 7 (len 4) -> next starts at 4+4-1 = 7th token (index 6)
                           # Chunk3: 7 8 9 10 (len 4)
    assert chunks[0] == "one two three four"
    assert chunks[1] == "four five six seven" # Overlap of "four"
    assert chunks[2] == "seven eight nine ten"  # Overlap of "seven"

@patch('src.tldr_openai_helper.tiktoken.encoding_for_model')
def test_chunk_text_no_chunking_needed(mock_encoding_for_model):
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = ["short", "text"] # 2 tokens
    mock_encoder.decode.return_value = "short text"
    mock_encoding_for_model.return_value = mock_encoder

    text_body = "short text"
    chunks = chunk_text(text_body, "gpt-4o", max_tokens_per_chunk=5, overlap_tokens=1)
    assert len(chunks) == 1
    assert chunks[0] == "short text"

@patch('src.tldr_openai_helper.tiktoken.encoding_for_model')
def test_chunk_text_empty_input(mock_encoding_for_model):
    # mock_encoder will not be called if text_body is empty first
    chunks = chunk_text("", "gpt-4o", 5, 1)
    assert len(chunks) == 0
    mock_encoding_for_model.assert_not_called()


# Test summarize_text_chunks
@patch('src.tldr_openai_helper.load_key_from_config_file', return_value="Test Prompt Focus") # Mock config loading
def test_summarize_text_chunks_success(mock_load_cfg, mocker, caplog):
    mock_openai_client = MagicMock(spec=openai.OpenAI)
    
    # Simulate two chunks, each getting a summary
    mock_completion1 = MagicMock()
    mock_completion1.choices = [MagicMock(message=MagicMock(content="Summary of chunk 1."))]
    
    mock_completion2 = MagicMock()
    mock_completion2.choices = [MagicMock(message=MagicMock(content="Final summary incorporating chunk 1 and 2."))]
    
    mock_openai_client.chat.completions.create.side_effect = [mock_completion1, mock_completion2]

    chunks_to_summarize = ["This is the first chunk of text.", "This is the second piece of text."]
    system_prompt_text = "You are a summarizer."
    
    final_summary = summarize_text_chunks(
        chunks_to_summarize, mock_openai_client, "gpt-4o-test", system_prompt_text, user_prompt_template=""
    )

    assert final_summary == "Final summary incorporating chunk 1 and 2."
    assert mock_openai_client.chat.completions.create.call_count == 2
    
    # Check first call's user prompt
    first_call_args = mock_openai_client.chat.completions.create.call_args_list[0][1] # kwargs of first call
    assert "Background context: ####" in first_call_args['messages'][1]['content'] # Empty initial context
    assert "####This is the first chunk of text.####" in first_call_args['messages'][1]['content']
    assert "Test Prompt Focus" in first_call_args['messages'][1]['content']


    # Check second call's user prompt (should include summary of chunk 1)
    second_call_args = mock_openai_client.chat.completions.create.call_args_list[1][1] # kwargs of second call
    assert "Background context: ####Summary of chunk 1.####" in second_call_args['messages'][1]['content']
    assert "####This is the second piece of text.####" in second_call_args['messages'][1]['content']
    assert "Test Prompt Focus" in second_call_args['messages'][1]['content']

    assert "Successfully completed summarization of all chunks." in caplog.text


@patch('src.tldr_openai_helper.load_key_from_config_file', return_value="") # Mock config
def test_summarize_text_chunks_openai_api_error(mock_load_cfg, mocker, caplog):
    mock_openai_client = MagicMock(spec=openai.OpenAI)
    # Simulate an API error from OpenAI
    mock_openai_client.chat.completions.create.side_effect = openai.RateLimitError(
        message="Rate limit hit", response=MagicMock(), body={"error": {"message": "Rate limit"}}
    )

    chunks_to_summarize = ["A single chunk that will fail."]
    with pytest.raises(OpenAIAPIError) as excinfo:
        summarize_text_chunks(chunks_to_summarize, mock_openai_client, "gpt-4o-test", "System", "")
    
    assert "Rate Limit Error" in str(excinfo.value)
    assert "OpenAI Rate Limit Exceeded for chunk 1" in caplog.text


@patch('src.tldr_openai_helper.load_key_from_config_file', return_value="")
def test_summarize_text_chunks_empty_chunks_list(mock_load_cfg, mocker, caplog):
    mock_openai_client = MagicMock(spec=openai.OpenAI)
    summary = summarize_text_chunks([], mock_openai_client, "gpt-4o-test", "System", "", initial_context="Initial.")
    assert summary == "Initial." # Should return initial context
    assert "No chunks provided to summarize_text_chunks." in caplog.text
    mock_openai_client.chat.completions.create.assert_not_called()

# Add more tests for summarize_text_chunks: different API errors (Auth, BadRequest), empty summary from API, etc. 