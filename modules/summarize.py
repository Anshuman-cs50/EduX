import requests
import json

class Summarizer:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
        self.temperature = 0.7
        self.max_tokens = 500
        self.timeout = 120

    def summarize(self, text, max_length=50):
        """Summarize the given text using the mistral:7b-instruct model."""
        prompt = f"Summarize the following text to {max_length} words: {text}"
        response = self._generate_response(prompt, "mistral:7b-instruct")
        return response

    def _generate_response(self, prompt, model):
        """Generate response with retry logic."""
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "options": {
                            "temperature": self.temperature,
                            "num_ctx": 2048,
                            "repeat_last_n": 0
                        },
                        "stream": False
                    },
                    timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                return result.get('response', '')
            except requests.exceptions.RequestException as e:
                if attempt == 2:
                    raise ConnectionError("Failed to connect to the AI service after retries") from e
                continue
            except Exception as e:
                raise Exception("Failed to generate response") from e