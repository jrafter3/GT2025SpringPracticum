"""

This processor is really poorly written and formatted, and needs to be constantly fixed due to API errors
and timeouts.

"""

import requests
import time
import re
import json
from pathlib import Path
from lxml import html
from datetime import datetime
from typing import Dict, List, Optional

# Constants
API_KEY = "pfzSh7rlXaccGCDuMyhWGejcSFqIBkFKHWkxphlo"
BASE_URL = "https://api.congress.gov/v3"

# File Paths
OUTPUT_DIR = Path(__file__).parent / "data_output"
PROCESSED_BILLS_FILE = OUTPUT_DIR / "processed_bills.json"
BILL_DATA_FILE = OUTPUT_DIR / "bill_data_118.json"
OFFSET_FILE = OUTPUT_DIR / "last_offset.json"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class CongressAPIClient:
    """Client for interacting with Congress.gov API"""

    def __init__(self, api_key: str, offset_limit=100, max_bills=100):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.headers = {"X-API-Key": api_key}

        self.offset_limit = offset_limit  # User-defined API request limit
        self.max_bills = max_bills  # User-defined max bills to fetch

        self.last_offset = self.load_last_offset()
        self.new_offset = self.last_offset

    def load_last_offset(self):
        """Load the last used API offset from a file."""
        try:
            with open(OFFSET_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("last_offset", 0))
        except (FileNotFoundError, ValueError, TypeError):
            return 0  # Default to 0 if no file or invalid data

    def save_last_offset(self, offset):
        """Save the last used API offset to a file."""
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_offset": offset}, f, indent=4)

    def _make_request(self, method: str, url: str, max_retries=10):
        """Makes an API request with robust retry handling to prevent crashes."""
        attempt = 0
        wait_time = 2  # Start with 2 seconds

        while attempt < max_retries:
            try:
                response = requests.request(method, url, headers=self.headers, timeout=10)

                if response.status_code == 429:  # Handle API rate limit
                    retry_after = int(response.headers.get("Retry-After", wait_time))
                    print(f"Rate limit hit. Retrying in {retry_after} seconds...")
                    time.sleep(retry_after)
                    attempt += 1
                    continue

                response.raise_for_status()  # Raise exception if HTTP error occurs
                return response  # Successful response

            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                print(f"Timeout/Connection error on {url}. Retrying in {wait_time} seconds...")
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")

            # ⏳ Exponential backoff to avoid hammering the API
            time.sleep(wait_time)
            wait_time = min(wait_time * 2, 60)  # Max wait time is 60 sec
            attempt += 1

        print(f"Skipping request permanently: {url} after {max_retries} failed attempts.")
        return None  # Fail gracefully, don't crash

    def load_processed_bills(self):
        """Load processed bill keys (their numbers) from a JSON file."""
        try:
            with open(PROCESSED_BILLS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f).get("processed_bills", []))
        except FileNotFoundError:
            return set()

    def load_existing_bill_data(self):
        """Load existing bill full data from JSON to avoid overwriting."""
        try:
            with open(BILL_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def get_all_bills_from_congress(self, congress=118):
        """Retrieve all HR and S bills from a specific Congress session."""
        bills = []
        endpoint = f"{self.base_url}/bill/{congress}"

        while len(bills) < self.max_bills:
            response = self._make_request("GET", f"{endpoint}?offset={self.new_offset}&limit={self.offset_limit}")
            if not response or response.status_code != 200:
                break  

            data = response.json()
            new_bills = data.get("bills", [])
            num_bills_fetched = len(new_bills)

            print(f"Retrieved {num_bills_fetched} bills at offset {self.new_offset}")

            if not new_bills:
                break  

            for bill in new_bills:
                bill_type = bill.get("type", "").upper()
                bill_number = bill.get("number")

                if bill_type in ["HR", "S"] and bill_number:
                    bills.append((congress, bill_type.lower(), bill_number))

            self.new_offset += self.offset_limit

        print(f"FINAL TOTAL: Retrieved {len(bills)} HR and S bills from Congress {congress}.")
        return bills, self.new_offset

    def get_bill_details(self, congress: int, bill_type: str, bill_number: int):
        """Fetch bill details, actions, and text versions efficiently."""
        base_url = f"{self.base_url}/bill/{congress}/{bill_type}/{bill_number}"

        metadata_response = self._make_request("GET", base_url)

        if not metadata_response or metadata_response.status_code != 200:
            return None

        try:
            metadata = metadata_response.json().get("bill", {})
        except Exception as e:
            return None

        title = metadata.get("title", "N/A")

        actions_response = self._make_request("GET", f"{base_url}/actions")
        
        public_law_number = None
        became_law = False

        if actions_response and actions_response.status_code == 200:
            actions = actions_response.json().get("actions", [])
            for action in actions:
                if "BecameLaw" in action.get("type", "") and "Became Public Law" in action.get("text", ""):
                    public_law_number = action["text"].split()[-1].strip(".")
                    became_law = True
                    break  

        text_response = self._make_request("GET", f"{base_url}/text")

        bill_text_url = None
        if text_response and text_response.status_code == 200:
            text_versions = text_response.json().get("textVersions", [])
            for version in text_versions:
                for format_info in version.get("formats", []):
                    if format_info.get("type") in ["HTML", "Formatted Text"]:
                        bill_text_url = format_info.get("url")
                        break
                if bill_text_url:
                    break  

        return {
            "congress": congress,
            "bill_type": bill_type,
            "bill_number": bill_number,
            "title": title,
            "became_law": became_law,
            "public_law_number": public_law_number,
            "bill_text_url": bill_text_url
        }

    def clean_bill_text(self, text):
        """Cleans bill text by handling \n characters and reducing extra spaces."""
        
        text = re.sub(r"\n+", " ", text)  # Replace multiple newlines with a space
        text = re.sub(r"\s{2,}", " ", text)  # Replace multiple spaces with a single space
        text = text.replace("\xa0", " ")  # Remove non-breaking spaces
        return text.strip()

    def extract_bill_raw_text(self, bill_text_url):
        """Extracts plain text from the bill's HTML version."""
        if not bill_text_url:
            return None

        response = self._make_request("GET", bill_text_url)
        if not response:
            return None

        try:
            tree = html.fromstring(response.content)
            return tree.text_content().strip()
        except Exception as e:
            print(f"Error extracting text from {bill_text_url}: {e}")
            return None

    def gather_bill_data(self):
        """Fetch bill data efficiently, skipping already processed bills, and saving progress every 10 bills."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}]\n")

        existing_bill_data = self.load_existing_bill_data()
        processed_bills = self.load_processed_bills()
        bills, last_offset_temp = self.get_all_bills_from_congress(118)

        structured_bill_data = existing_bill_data.copy()
        processed_bills_temp = processed_bills.copy()

        bills_processed_since_last_save = 0

        for congress, bill_type, bill_number in bills:
            bill_key = f"{congress}_{bill_type}_{bill_number}"

            if bill_key in processed_bills:
                print(f"Skipping {bill_key} (Already Processed)")
                continue  

            print(f"Processing {bill_key}...")
            bill_data = self.get_bill_details(congress, bill_type, bill_number)

            if not bill_data or not bill_data["bill_text_url"]:
                continue  

            #take the urls of the text and get the raw text

            bill_text_raw = self.extract_bill_raw_text(bill_data["bill_text_url"])
            if not bill_text_raw:
                continue

            # Clean bill text
            bill_text_raw = self.clean_bill_text(bill_text_raw)

            structured_bill_data[bill_key] = {
                "congress": bill_data["congress"],
                "bill_type": bill_data["bill_type"],
                "bill_number": bill_data["bill_number"],
                "title": bill_data["title"],
                "became_law": bill_data["became_law"],
                "public_law_number": bill_data["public_law_number"],
                "bill_text_raw": bill_text_raw
            }

            processed_bills_temp.add(bill_key)
            bills_processed_since_last_save += 1

            # Save every 10 processed bills since been having a lot of timeouts, so progress is saved
            # every 10 bills.

            if bills_processed_since_last_save % 10 == 0:
                self.save_bill_data_to_files(structured_bill_data, processed_bills_temp, last_offset_temp)
                bills_processed_since_last_save = 0

        return structured_bill_data, processed_bills_temp

    def save_bill_data_to_files(self, structured_bill_data, processed_bills_temp, last_offset_temp):
        """Saves bill data, processed bills, and offset to prevent data loss."""
        with open(BILL_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(structured_bill_data, f, indent=4)

        with open(PROCESSED_BILLS_FILE, "w", encoding="utf-8") as f:
            json.dump({"processed_bills": list(processed_bills_temp)}, f, indent=4)

        self.save_last_offset(last_offset_temp)


# Run the Script
client = CongressAPIClient(API_KEY, offset_limit=10, max_bills=100)
client.gather_bill_data()
