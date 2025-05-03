import re
from typing import Dict

class PromptUtils:
    @staticmethod
    def extract_structured_response(text: str) -> Dict:
        """Try to extract structured data from LLM response"""
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
                
        # Fallback to simple question-answer format
        return {
            'question': text.split('\n')[0] if '\n' in text else text,
            'explanation': text
        }

    @staticmethod
    def validate_question(question_data: Dict) -> bool:
        """Validate the structure of a generated question"""
        required_keys = {'question', 'options', 'correct_answer', 'explanation'}
        return all(key in question_data for key in required_keys)