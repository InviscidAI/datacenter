# chatbot/mock_chatbot.py

import json
import re

class MockChatBot:
    """
    An enhanced mock chatbot that mimics a real LLM's conversational
    abilities and structured data output for testing purposes.
    """
    def __init__(self, model_name, schema, openai_api_key='EMPTY', port=8000):
        # The signature is kept the same for drop-in compatibility.
        self.messages = []
        print("--- CHATBOT INITIALIZED IN ENHANCED MOCK MODE ---")

    def send_user_message(self, message, stream=False):
        """
        Parses the user message for keywords and returns a pre-defined
        JSON structure that includes both a conversational reply ('speak')
        and the necessary data ('action') for the application.
        """
        message = message.lower()
        response = self._get_response(message)
        # The bot must always return a JSON-encoded string, which the
        # backend API will then load and jsonify.
        return json.dumps(response)

    def _get_response(self, message):
        """Generates a response based on rules."""
        # --- Greetings and Help ---
        if any(word in message for word in ["hello", "hi", "hey"]):
            return {
                "speak": "Hello! How can I help you with the data center simulation today?"
            }
        
        if "help" in message or "what can you do" in message:
            return {
                "speak": "I can help you modify the simulation setup. Try asking me to:\n- 'Set all CRAC temperatures to 295K'\n- 'What if rack 3 fails?'\n- 'Change the power of rack 1 to 7kW'"
            }

        # --- Rule for "set temp" ---
        if "set" in message and ("temp" in message or "temperature" in message):
            match = re.search(r'(\d+(\.\d+)?)', message)
            if match:
                temp = float(match.group(0))
                temp_k = temp # Assume Kelvin unless specified
                speak_temp = f"{temp_k}K"

                return {
                    "speak": f"Okay, I'm setting the supply temperature for all CRAC units to {speak_temp}.",
                    "action": "update",
                    "target_type": "crac",
                    "target_name": "all",
                    "parameters": { "supply_temp_K": round(temp_k, 2) }
                }
            else:
                return {"speak": "I can set the temperature, but you need to tell me what to set it to. For example: 'Set the temp to 300K'."}

        # --- Rule for "break down" or "fails" ---
        if any(word in message for word in ["break", "fail", "remove", "delete"]):
            target_type_match = re.search(r'(crac|cooler|rack)', message)
            target_num_match = re.search(r'(\d+)', message)

            if target_type_match and target_num_match:
                sim_type = 'crac' if 'crac' in target_type_match.group(1) or 'cooler' in target_type_match.group(1) else 'rack'
                num = target_num_match.group(1)
                name = f"{sim_type}_{num}"
                
                return {
                    "speak": f"Understood. Removing {sim_type.capitalize()} {num} from the simulation scenario.",
                    "action": "delete",
                    "target_type": sim_type,
                    "target_name": name
                }
            else:
                return {"speak": "I can simulate a component failure, but I need to know which one. For example: 'What if CRAC 2 fails?'"}

        # --- Rule for changing rack power ---
        if "power" in message and "rack" in message:
            name_match = re.search(r'rack[\s_]?(\d+)', message)
            power_match = re.search(r'(\d+(\.\d+)?)\s?(kw|watts|w)', message)

            if not name_match:
                return {"speak": "Which rack's power should I change? Please specify a number, like 'rack 3'."}
            if not power_match:
                return {"speak": "What should I set the power to? Please specify a value in kW or Watts."}
            
            name = f"rack_{name_match.group(1)}"
            power_val = float(power_match.group(1))
            power_unit = power_match.group(3) if len(power_match.groups()) > 2 else 'w'

            if power_unit == 'kw':
                power_watts = power_val * 1000
                speak_power = f"{power_val}kW"
            else: # 'w' or 'watts'
                power_watts = power_val
                speak_power = f"{power_watts} Watts"

            return {
                "speak": f"Alright, setting the power of {name.replace('_', ' ')} to {speak_power}.",
                "action": "update",
                "target_type": "rack",
                "target_name": name,
                "parameters": { "power_watts": power_watts }
            }

        # --- Fallback for any unrecognized command ---
        return {
            "speak": "I'm sorry, I don't understand that request. I am a mock chatbot. Try asking for 'help' to see what I can do."
        }