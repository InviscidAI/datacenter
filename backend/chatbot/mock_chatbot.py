import json
import re

class MockChatBot:
    """
    A mock chatbot that mimics the real ChatBot's interface but returns
    hard-coded JSON responses for testing without a real LLM.
    """
    def __init__(self, model_name, schema, openai_api_key='EMPTY', port=8000):
        # We don't need any of the real init parameters, but we keep the
        # signature the same so it's a perfect drop-in replacement.
        self.messages = []
        print("--- CHATBOT INITIALIZED IN MOCK MODE ---")

    def send_user_message(self, message, stream=False):
        """
        Parses the user message for keywords and returns a pre-defined
        JSON structure, just like the real LLM is supposed to.
        """
        message = message.lower()
        
        # Rule for "set temp"
        if "set" in message and "temp" in message:
            # Try to find a number (integer or float)
            match = re.search(r'\d+(\.\d+)?', message)
            temp = float(match.group(0)) if match else 300.0 # Default to 300K
            return json.dumps({
                "action": "update",
                "target_type": "crac",
                "target_name": "all",
                "parameters": { "supply_temp_K": temp }
            })

        # Rule for "break down" or "fails"
        elif "break" in message or "fail" in message:
            # Try to find the name like "crac_3" or "cooler 3"
            match = re.search(r'(crac|cooler)[\s_]?(\d+)', message)
            if match:
                name = f"crac_{match.group(2)}"
                return json.dumps({
                    "action": "delete",
                    "target_type": "crac",
                    "target_name": name
                })

        # Rule for changing rack power
        elif "power" in message and "rack" in message:
            name_match = re.search(r'rack[\s_]?(\d+)', message)
            power_match = re.search(r'(\d+)\s?kw', message)
            if name_match and power_match:
                name = f"rack_{name_match.group(1)}"
                power = float(power_match.group(1)) * 1000 # Convert kW to W
                return json.dumps({
                    "action": "update",
                    "target_type": "rack",
                    "target_name": name,
                    "parameters": { "power_watts": power }
                })

        # Fallback for any unrecognized command
        return json.dumps({
            "raw_text": "I am a mock chatbot. I only understand commands like 'set temp to 300K', 'cooler 3 fails', or 'set power of rack 2 to 6kW'."
        })