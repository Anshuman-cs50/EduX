import requests
import json
import logging
from typing import Dict, Optional, Union, List, Any
import time
import re

logger = logging.getLogger(__name__)

class LLMHandler:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.temperature = 0.7
        self.max_tokens = 500
        self.timeout = 120  # 2 minutes
        self.max_retries = 2
        self.retry_delay = 5
        self.server_available = self._verify_connection()

    def _verify_connection(self) -> bool:
        """Verify Ollama is running with increased timeout"""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.timeout
            )
            if response.status_code != 200:
                logger.error("Ollama connection failed - is the service running?")
                return False
            logger.info("Connected to Ollama successfully")
            return True
        except Exception as e:
            logger.warning(f"Ollama connection error: {str(e)}")
            return False

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
        if not self.server_available:
            logger.warning("Ollama server is not available. Cannot generate response.")
            return "The AI service is currently unavailable. Please try again later."

        for attempt in range(self.max_retries + 1):
            try:
                # Verify model is available first
                response = requests.get(
                    f"{self.base_url}/api/tags",
                    timeout=self.timeout
                )
                response.raise_for_status()
                tags_data = response.json()
                
                # Improved model availability check
                available_models = []
                if 'models' in tags_data:
                    available_models = [m['name'] for m in tags_data['models']]
                
                # More flexible model name matching
                model_base_name = model.split(":")[0]
                
                # Log model information for debugging
                logger.debug(f"Requested model: {model}, base name: {model_base_name}")
                logger.debug(f"Available models: {available_models}")
                
                # First try exact match
                if model in available_models:
                    model_available = True
                    logger.debug(f"Exact model match found for {model}")
                # Then try base name match
                elif any(m.startswith(model_base_name) for m in available_models):
                    matching_models = [m for m in available_models if m.startswith(model_base_name)]
                    logger.debug(f"Base name matches found: {matching_models}")
                    # If no exact match but base name matches, use the first matching model
                    model = matching_models[0]
                    model_available = True
                    logger.info(f"Using model {model} as match for requested {model_base_name}")
                else:
                    model_available = False
                
                if not model_available:
                    if available_models:
                        # Fall back to first available model
                        fallback_model = available_models[0]
                        logger.warning(
                            f"Model {model} not available. Falling back to: {fallback_model}"
                        )
                        model = fallback_model
                    else:
                        raise ValueError(f"No models available in Ollama")

                # Generate the response with the selected model
                logger.info(f"Generating response using model: {model}")
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
                    timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                logger.debug(f"Ollama raw result: {result}")
                
                # Extract response text
                if isinstance(result, dict):
                    text = result.get('response') or result.get('message') or result.get('output') or str(result)
                else:
                    text = str(result)
                    
                return self._process_educational_response(text)

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    logger.error(f"LLM API request failed after {self.max_retries} attempts: {str(e)}")
                    return "The AI service is taking longer than usual to respond. Please try again later."
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"LLM generation failed: {str(e)}")
                return "An error occurred while generating the response. Please try again."

    def _process_educational_response(self, text: str) -> str:
        """Process response for educational content - improved to handle various formats"""
        try:
            logger.debug(f"Processing response text: {text[:100]}...")
            
            # Check if the text appears to be teaching instructions
            instruction_indicators = [
                "Step 1:", "Step 2:", "Step 3:", "Step 4:",
                "Remember, the goal is to", 
                "== this type of response",
                "teacher should",
                "should not be seen to student"
            ]
            
            if any(indicator in text for indicator in instruction_indicators):
                logger.warning("Detected teaching instructions in response that should not be shown to students")
                
                # Extract the intended student-facing content if possible
                # Look for actual content between instruction steps
                content_parts = []
                lines = text.split('\n')
                in_content = False
                
                for line in lines:
                    # Skip obvious instruction lines
                    if any(line.strip().startswith(i) for i in ["Step ", "Remember,", "=="]):
                        continue
                        
                    # Include lines that seem like actual content
                    if line.strip() and not any(i in line for i in instruction_indicators):
                        content_parts.append(line)
                
                if content_parts:
                    return "\n".join(content_parts)
                else:
                    # Fallback if we couldn't extract good content
                    return "I'd be happy to help with that! Could you please ask your question again?"
            
            # Try to parse as JSON for structured content
            try:
                json_obj = json.loads(text)
                
                # For quiz content, keep the JSON structure
                if 'question' in json_obj or 'options' in json_obj:
                    return json.dumps(json_obj)
                    
                # For chat responses, extract relevant text fields
                if 'response' in json_obj:
                    return json_obj['response']
                elif 'content' in json_obj:
                    return json_obj['content']
                else:
                    return json.dumps(json_obj)  # Return properly formatted JSON
                    
            except json.JSONDecodeError:
                # Not JSON, return cleaned text content
                return text
                
        except Exception as e:
            logger.error(f"Response processing failed: {str(e)}")
            return text