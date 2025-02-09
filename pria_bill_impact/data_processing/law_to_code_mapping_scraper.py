import requests
from bs4 import BeautifulSoup
import json
import re

# URL of the U.S. Code Classification Table for the 118th Congress
URL = "https://uscode.house.gov/classification/tbl118pl_2nd.htm"

def scrape_classification_table(url):
    """Scrapes the classification table from the U.S. Code website."""
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to retrieve page. Status Code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    
    # 🔍 Find the <pre> tag that contains the classification data
    pre_tag = soup.find("pre")

    if not pre_tag:
        print("Classification table not found on the page!")
        return None

    table_text = pre_tag.get_text()
    print(table_text)  # Print the first 1000 characters to inspect

    return table_text

def parse_classification_table(table_text):
    """Parses the scraped classification table text into structured data."""
    extracted_rows = []
    
    # Corrected Regex to Capture U.S. Code → Public Law
    pattern = re.compile(r"^\s*(\d+)\s+([\w\d\(\)\-]+)\s+(.*?)\s+(\d+)-(\d+)", re.MULTILINE)
    
    for match in pattern.finditer(table_text):
        title = match.group(1)  # U.S. Code Title (Column 1)
        section = match.group(2)  # U.S. Code Section (Column 2)
        description = match.group(3).strip()  # Metadata (e.g., "nt", "new")
        public_law = f"{match.group(4)}-{match.group(5)}"  # Public Law (correct column)
        
        extracted_rows.append({
            "Title": title,
            "Section": section,
            "Description": description,
            "Public_Law": public_law
        })

    return extracted_rows


def process_classification_data(extracted_rows):
    """Processes extracted table rows into structured JSON format."""
    public_law_to_us_code = {}

    metadata_types = ["nt", "prec", "new", "repealed"]

    for row in extracted_rows:
        try:
            public_law_number = row["Public_Law"]
            title_number = row["Title"]
            section_number = row["Section"]
            meta_tag = row["Description"]

            # Ensure public law is a key in dictionary
            if public_law_number not in public_law_to_us_code:
                public_law_to_us_code[public_law_number] = {
                    "title": f"Public Law {public_law_number}",
                    "us_code_sections": [],
                    "metadata": []
                }

            # Separate Metadata (nt, prec, new, repealed)
            if meta_tag in metadata_types:
                public_law_to_us_code[public_law_number]["metadata"].append({
                    "type": meta_tag,
                    "title": int(title_number),
                    "section": section_number
                })
            else:
                # Append the U.S. Code mapping
                public_law_to_us_code[public_law_number]["us_code_sections"].append({
                    "title": int(title_number),
                    "section": section_number
                })

        except Exception as e:
            print(f"Error processing row {row}: {e}")

    return public_law_to_us_code

def save_to_json(data, filename="public_law_to_us_code_mapping.json"):
    """Saves the structured data to a JSON file."""
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Saved Public Law → U.S. Code mappings to {filename}")

# 🔥 Run the scraper and parser
print("🔍 Scraping classification table...")
table_text = scrape_classification_table(URL)

if table_text:
    print("Successfully retrieved classification table.")
    
    print("🔍 Parsing table data...")
    extracted_rows = parse_classification_table(table_text)
    
    print(f"Extracted {len(extracted_rows)} rows.")

    print("🔍 Processing data into structured format...")
    structured_data = process_classification_data(extracted_rows)

    print("💾 Saving to JSON file...")
    save_to_json(structured_data)
    
    #print(structured_data['118-42']['us_code_sections'])