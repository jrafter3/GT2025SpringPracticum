import re
import json
from typing import Any, Dict

def parse_textblock(textblock: Any) -> Dict[str, Any]:
    """
    Parses a TextBlock object into a proper dictionary. This is used for when Anthropic
    outputs a textblock during our LLM call and we want to return a dictionary for our
    output.

    Args:
        textblock (Any): The TextBlock object or a list containing it.

    Returns:
        Dict[str, Any]: A dictionary representation of the parsed JSON output.
    """
    try:
        if isinstance(textblock, list) and len(textblock) > 0:
            textblock = textblock[0]  # Extract first element if it's a list

        if hasattr(textblock, "text"):
            raw_text = textblock.text.strip()
            raw_text = raw_text.replace("\n", "").replace("\r", "").strip()

            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not json_match:
                raise ValueError("No valid JSON found in TextBlock.text.")

            return json.loads(json_match.group(0))

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
    except Exception as e:
        print(f"Unexpected error parsing TextBlock: {e}")

    return {"error": "Failed to parse TextBlock", "raw_text": str(textblock)}

