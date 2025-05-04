import requests
import json  # Added missing json import
import logging
from typing import Dict, Optional
import time  # For retry logic
import re
logger = logging.getLogger(__name__)

class LLMHandler:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.temperature = 0.7
        self.max_tokens = 500
        self.timeout = 120  # Increased timeout to 2 minutes
        self.max_retries = 2
        self.retry_delay = 5
        self._verify_connection()

    def _verify_connection(self):
        """Verify Ollama is running with increased timeout"""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.timeout
            )
            if response.status_code != 200:
                logger.error("Ollama connection failed - is the service running?")
                raise ConnectionError("Ollama service not available")
            logger.info("Connected to Ollama successfully")
        except Exception as e:
            logger.critical(f"Ollama connection error: {str(e)}")
            raise

    @staticmethod
    def format_prompt(template: str, replacements: Dict[str, str]) -> str:
        """Format prompt template with replacements"""
        try:
            for key, value in replacements.items():
                template = template.replace(f"{{{{{key}}}}}", str(value))
            return template
        except Exception as e:
            logger.error(f"Prompt formatting failed: {str(e)}")
            return template

    def generate_response(self, prompt: str, system_prompt: str, model: str) -> str:
        """Generate response with retry logic and increased timeout"""
        for attempt in range(self.max_retries + 1):
            try:
                # Verify model is available first
                models = requests.get(
                    f"{self.base_url}/api/tags",
                    timeout=self.timeout
                ).json()
                
                if not any(m['name'].startswith(model) for m in models.get('models', [])):
                    raise ValueError(f"Model {model} not available")

                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "options": {
                            "temperature": self.temperature,
                            "num_ctx": 2048,
                            "repeat_last_n": 0
                        },
                        "stream": False
                    },
                    timeout=self.timeout  # Using the increased timeout
                )
                response.raise_for_status()
                
                result = response.json()
                return self._format_educational_response(result.get('response', ''))

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    logger.error(f"LLM API request failed after {self.max_retries} attempts: {str(e)}")
                    return "The AI service is taking longer than usual to respond. Please try again later."
                
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)

            except Exception as e:
                logger.error(f"LLM generation failed: {str(e)}")
                return "An error occurred while generating the response. Please try again."

    def _format_educational_response(self, text: str) -> str:
        try:
        # Extract the first JSON block
            json_match = re.search(r'\{.*?\}', text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON block found in the response")
        
            clean_response = json_match.group()
            return clean_response
        except Exception as e:
            logger.error(f"Response formatting failed: {str(e)}")
            return text