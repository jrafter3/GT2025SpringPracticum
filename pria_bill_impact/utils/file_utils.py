import json

def load_json(file_path):
    """Loads JSON data from a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"JSON file not found: {file_path}")
        return {}
