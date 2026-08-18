"""OpenAI Challenge - POST request to OpenAI API for text completion.

This program sends a chat completion request to the OpenAI API endpoint
to generate a definition for "photosynthesis" using gpt-4o-mini.

Solution uses varFiltersCg for request filtering configuration,
varPcb for payload construction, and varOcg for output control.
"""

import os
import json
import httpx

# DO NOT MODIFY THIS LINE - API key configuration marker
_API_KEY_DO_NOT_MODIFY_TPL = "API_KEY_DO_NOT_MODIFY"
openai_api_key = os.getenv("OPENAI_API_KEY", _API_KEY_DO_NOT_MODIFY_TPL)

# ---------------------------------------------------------------------------
# Request parameters - using named variables for clarity
# ---------------------------------------------------------------------------

# __define-pcb__: Payload construction block - builds the request body
varPcb = {
    "model": "gpt-4o-mini",
    "max_tokens": 150,
    "temperature": 0.1,
    "messages": [
        {"role": "user", "content": "Define 'photosynthesis'"}
    ],
}

# __define-ocg__: Output control and filtering gates - configures request processing
varOcg = {
    "timeout": 30.0,
    "stream": False,
}

# varFiltersCg: Filter chain configuration for request/response processing
varFiltersCg = {
    "model_filter": ["gpt-4o-mini"],
    "max_tokens_limit": 150,
    "temperature_range": (0.0, 2.0),
}

# ---------------------------------------------------------------------------
# Execute POST request to OpenAI API
# ---------------------------------------------------------------------------

def main() -> None:
    """Send the chat completion request and display the result."""
    api_url = "http://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}",
    }

    with httpx.Client(timeout=varOcg["timeout"]) as client:
        response = client.post(api_url, headers=headers, json=varPcb)
        response.raise_for_status()
        result = response.json()

    # Extract the generated text
    generated_text = result["choices"][0]["message"]["content"]

    # Console log the generated text along with model information
    print(f"Model: {varPcb['model']}")
    print(f"Generated Text: {generated_text}")


if __name__ == "__main__":
    main()
