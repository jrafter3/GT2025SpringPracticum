
import re
import json
from typing import Any, Dict

import json
import re
from typing import Any, Dict

def parse_textblock(textblock: Any) -> Dict[str, Any]:
    """
    Attempts to parse a TextBlock object, dictionary, or raw string into a dictionary.
    Compatible with LangChain-style TextBlock objects and stringified versions from LLM output.
    Tries cleaning control characters if initial parsing fails.
    """
    try:
        # Unwrap from list if needed
        if isinstance(textblock, list) and textblock:
            textblock = textblock[0]

        # Extract raw text
        if hasattr(textblock, "text"):  # LangChain TextBlock
            raw_text = textblock.text.strip()
        elif isinstance(textblock, dict) and "text" in textblock:  # LangChain dict format
            raw_text = textblock["text"].strip()
        elif isinstance(textblock, str):  # Stringified version
            match = re.search(r"text='(.+?)'(?:,\s*type='text')?\)?$", textblock, re.DOTALL)
            if not match:
                raise ValueError("Could not extract 'text' field from TextBlock string.")
            raw_text = match.group(1)
            raw_text = bytes(raw_text, "utf-8").decode("unicode_escape")
        else:
            raise TypeError(f"Unsupported type for textblock: {type(textblock)}")

        

        # Extract JSON body
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON content found within the extracted text.")

        json_string = json_match.group(0)

        # Try raw parse
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error (raw): {e}")
            print("🔧 Raw response from model:")
            print(raw_text)

        # Clean control characters and retry
        cleaned_json_string = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_string)
        #print("\n🧼 Cleaned response:")
        #print(cleaned_json_string)

        return json.loads(cleaned_json_string)

    except Exception as e:
        print(f"❌ Unexpected error parsing TextBlock: {e}")
        return {"error": "Failed to parse TextBlock", "raw_text": str(textblock)}



def extract_us_code_mentions(text):
    """
    Extracts U.S. Code references from bill text in multiple formats.
    
    Matches:
    1. Standard: "5 U.S.C. 8401"
    2. Bill citation: "Section 8401 of Title 5, United States Code"
    3. Parenthetical: "(42 U.S.C. 1320e-1(e))"
    
    Returns:
        List[Dict]: [{"title_number": "5", "section_number": "8401"}, ...]
    """

    # Standard citation: 5 U.S.C. 8401
    standard_pattern = r"\b(\d{1,3})\s+U\.S\.C\.\s+(\d{1,5})\b"

    # Bill-style citation: Section 8401 of Title 5, United States Code
    bill_style_pattern = r"\b[Ss]ection\s+(\d{1,5})\s+of\s+[Tt]itle\s+(\d{1,3}),?\s+United\s+States\s+Code\b"

    # Parenthetical citation: (42 U.S.C. 1320e-1(e))
    parenthetical_pattern = r"\(\s*(\d{1,3})\s+U\.S\.C\.\s+(\d{1,5})"

    # Find all matches
    matches = (
        re.findall(standard_pattern, text)
        + re.findall(bill_style_pattern, text)
        + re.findall(parenthetical_pattern, text)
    )

    # Convert to unique list of dictionaries
    extracted_sections = []
    seen = set()

    for title, section in matches:
        key = (title, section)  # Ensures uniqueness
        if key not in seen:
            extracted_sections.append({"title_number": title, "section_number": section})
            seen.add(key)

    return extracted_sections


def clean_section_number(section_number: str) -> str:
    """
    Cleans section numbers by removing any trailing alphabet characters or extra symbols.
    Example:
    - "101c" → "101"
    - "102(a)(1)" → "102"
    """
    match = re.match(r"(\d+)", section_number)
    return match.group(1) if match else section_number  # Extracts only numeric part






