import xml.etree.ElementTree as ET
import json
import re
import unicodedata
import io
from pathlib import Path
from typing import Dict, List, Optional


# Google Drive Folder ID where the processed JSON will be uploaded
# OUTPUT_FOLDER_ID = "1BHYjqTsIVZ0rt3shFIdrl0sVuB6DpAc1"  # Update this with your Google Drive folder ID

LOCAL_XML_DIR = Path(__file__).resolve().parent / "data" / "code_xml"


class USCodeParser:
    """
    Handles parsing raw XML files of U.S. code and outputing sections we care about.
    Only needs to be run one time.
    """
    def __init__(self):
        self.ns = {'default': 'http://xml.house.gov/schemas/uslm/1.0'}

    def clean_text(self, text: Optional[str]) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)

        replacements = {
            "\u2014": "-", "\u2013": "-", "\u201c": '"', "\u201d": '"',
            "\u2018": "'", "\u2019": "'",
        }
        for key, value in replacements.items():
            text = text.replace(key, value)

        text = re.sub(r'\s+', ' ', text.strip())
        text = re.sub(r'[-.]', '', text)
        text = re.sub(r'"?SECTION\s+|"?SEC\s+', '', text, flags=re.IGNORECASE)
        return text

    def parse_xml_from_file(self, xml_file: Path) -> Dict[str, Dict]:
        """Parses an XML file and returns a list of extracted sections."""
        sections_data = {}
        try:
            print(f"📖 Processing: {xml_file.name}")
            tree = ET.parse(xml_file)
            root = tree.getroot()

            title_elem = root.find('.//default:title', self.ns)
            if title_elem is None:
                print(f"Warning: No title element found in {xml_file.name}")
                return sections_data

            title_info = {
                'title_number': self.safe_extract_text(title_elem, 'default:num').replace('Title', '').strip(),
                'title_name': self.safe_extract_text(title_elem, 'default:heading')
            }

            for chapter in root.findall('.//default:chapter', self.ns):
                chapter_info = {
                    **title_info,
                    'chapter_number': self.safe_extract_text(chapter, 'default:num').replace('CHAPTER', '').strip(),
                    'chapter_name': self.safe_extract_text(chapter, 'default:heading')
                }

                for section in chapter.findall('.//default:section', self.ns):
                    try:
                        section_data = self.parse_section(section, chapter_info)
                        if section_data['content']:
	                        section_key = section_data['section_identifier_full']  # Use section_identifier_full as key
	                        sections_data[section_key] = section_data
                    except Exception as e:
                        print(f"Warning: Error parsing section in {xml_file.name}: {str(e)}")

        except Exception as e:
            print(f"Error processing {xml_file.name}: {str(e)}")

        return sections_data


    def safe_extract_text(self, element: Optional[ET.Element], xpath: str) -> str:
        """Safely extract text from an element."""
        if element is None:
            return ""
        found_elem = element.find(xpath, self.ns)
        return self.clean_text(found_elem.text if found_elem is not None else "")

    def extract_section_content(self, section: ET.Element) -> str:
        """Extract all text content from a section."""
        text_parts = []
        try:
            for content in section.findall('.//default:content', self.ns):
                for elem in content.iter():
                    if elem.text:
                        text_parts.append(self.clean_text(elem.text))
                    if elem.tail:
                        text_parts.append(self.clean_text(elem.tail))
        except Exception as e:
            print(f"Warning: Error extracting content from section: {str(e)}")

        return ' '.join(filter(None, text_parts))

    def parse_section(self, section: ET.Element, context_info: Dict) -> Dict:
        """Parse section metadata and content."""
        section_num = self.safe_extract_text(section, 'default:num')
        if section_num.startswith('§'):
            section_num = section_num.replace('§', '').strip()

        section_num = re.sub(r'[\[\]]', '', section_num)

        return {
            'title_number': context_info.get('title_number', ''),
            'title_name': context_info.get('title_name', ''),
            'chapter_number': context_info.get('chapter_number', ''),
            'chapter_name': context_info.get('chapter_name', ''),
            'act_name': context_info.get('act_name', ''),
            'section_number': section_num,
            'section_name': self.safe_extract_text(section, 'default:heading'),
            'content': self.extract_section_content(section),
            'status': section.get('status', ''),
            'section_identifier_full': f"Title {context_info.get('title_number', '')}, Section {section_num} - {self.safe_extract_text(section, 'default:heading')}"
        }


def process_all_xml_files(local_xml_dir):
    """Processes all XML files in a local directory and saves the results to a local folder."""
    parser = USCodeParser()
    all_sections = {}

    # Ensure the local XML directory exists
    if not local_xml_dir.exists():
        print(f"Error: XML directory '{local_xml_dir}' does not exist!")
        return

    xml_files = list(local_xml_dir.glob("*.xml"))
    print(f"📂 Found {len(xml_files)} XML files in 'data/' folder.")

    for xml_file in xml_files:
    	sections = parser.parse_xml_from_file(xml_file)
    	all_sections.update(sections)

    # Ensure the output directory exists
    output_dir = Path(__file__).parent / "data_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define output file path
    output_file = output_dir / "processed_uscode_sections.json"

    # Save to JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_sections, f, indent=2)

    print(f"\nProcessing complete. Extracted {len(all_sections)} sections.")
    print(f"📂 Results saved to {output_file}")



# Run the processor
if __name__ == "__main__":
    process_all_xml_files(LOCAL_XML_DIR)


