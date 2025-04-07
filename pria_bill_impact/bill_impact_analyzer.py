import time
import json
from pathlib import Path
from models.us_code_matcher import USCodeMatcher
from llm.anthropic_client import ClaudeLLM
from utils.file_utils import load_json
from models.embedder_and_faiss_indexer import EmbeddingFAISSManager
from models.us_code_matcher import USCodeMatcher
from llm.anthropic_client import ClaudeLLM
from utils.file_utils import load_json
from utils.text_utils import parse_textblock
from models.demographic_matcher import DemographicMatcher
from utils.text_utils import extract_us_code_mentions  


# File Paths
OUTPUT_DIR = Path("data_output")
PROCESSED_BILLS_FILE = OUTPUT_DIR / "processed_bills_list_for_impact_analysis.json"
BILL_IMPACT_FILE = OUTPUT_DIR / "bill_impact_analysis_haiku.json"


TARGET_BILLS = [
    (118,"hr",1046), 
    (118,"hr",8194), 
    (118,"hr",10001), 
    (118,"hr",1606), 
    (119,"hr",1618), 
    (118,"hr",1661), 
    (117,"hr",1711), 
    (118,"hr",1783), 
    (118,"hr",2676), 
    (118,"hr",2727), 
    (118,"hr",9993),
    (118,"hr",9958),
    (118,"hr",9956),
    (118,"hr",9946),
    (118,"hr",9937),
    (118,"hr",9935),
    (118,"hr",9930),
    (118,"hr",9904),
    (118,"hr",9890),
    (118,"hr",9881)
]

class BillTextAnalyzer:
    """Processes and analyzes Bill vs Code for impact assessment. Main Class for assignment"""

    def __init__(self):
        """Initialize components for bill-to-code matching and LLM processing."""
        print("Initializing LegalTextProcessor")



        # Load LLM Client for Summarization
        self.llm_client = ClaudeLLM()

        # Load Data Files
        self.public_law_mapping = load_json("data_output/public_law_to_us_code_mapping.json")
        self.bills = load_json("data_processing/data_output/bill_data_output.json")
        self.us_code_sections = load_json("data_processing/data_output/processed_uscode_sections.json")
        self.us_code_matcher = USCodeMatcher(self.us_code_sections)

        self.demographic_matcher = DemographicMatcher()

        #load processed bills log
        self.processed_bills = self.load_processed_bills()

    def load_processed_bills(self):
        """Loads previously analyzed bills to avoid duplication."""
        try:
            with open(PROCESSED_BILLS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f).get("processed_bills", []))  # Store as a set for fast lookup
        except FileNotFoundError:
            return set()


    def save_processed_bill(self, bill_id):
        """Saves a bill ID to the processed log file."""
        self.processed_bills.add(bill_id)
        with open(PROCESSED_BILLS_FILE, "w", encoding="utf-8") as f:
            json.dump({"processed_bills": list(self.processed_bills)}, f, indent=4)

    def get_exact_us_code_sections_for_passed_bills(self):
        """
        Matches bills with valid public law numbers to their corresponding U.S. Code sections.
        
        Returns:
            dict: A mapping of {bill_id: {"public_law_number": X, "us_code_sections": [...]}}
        """
        bill_to_us_code = {}

        for bill_id, bill_data in self.bills.items():
            public_law_number = bill_data.get("public_law_number")

            if public_law_number and public_law_number in self.public_law_mapping:
                us_code_sections = self.public_law_mapping[public_law_number].get("us_code_sections", [])

                bill_to_us_code[bill_id] = {
                    "public_law_number": public_law_number,
                    "us_code_sections": us_code_sections
                }

        return bill_to_us_code


    def find_similar_us_code_sections(self, bill_id, bill_text, top_k=2):
        """
        Finds the most relevant U.S. Code sections for a bill.

        - If the bill has been passed into law, it directly uses the mapped U.S. Code sections from get_exact_us_code_sections_for_passed_bills.
        - If it has not, first, checks if the bill explicitly mentions U.S. Code sections in the text.
        - If no direct mentions, uses FAISS similarity search.

        Returns:
            List[Dict]: List of dictionaries with:
                - "section": U.S. Code section identifier
                - "similarity_score": Confidence score (1.0 if direct mention)
                - "match_type": "direct_match" or "faiss_semantic_match"
        """
        # First, check if the bill has a Public Law mapping
        bill_mappings = self.get_exact_us_code_sections_for_passed_bills()

        matched_sections = []

        if bill_id in bill_mappings:
            # Direct mapping found
            us_code_sections = bill_mappings[bill_id]["us_code_sections"]

            for sec in us_code_sections:
                title_number = sec.get("title")
                section_number = clean_section_number(sec.get("section"))  # ✅ Clean section number

                # 🔍 Try to find exact match in U.S. Code database
                for us_code_key, us_code_data in self.us_code_sections.items():
                    if (
                        str(us_code_data.get("title_number")) == str(title_number) and
                        str(us_code_data.get("section_number")) == str(section_number)
                    ):
                        matched_sections.append({
                            "section_id": f"{title_number} U.S.C. {section_number}",
                            "title_number": title_number,
                            "section_number": section_number,
                            "us_code_text": us_code_data.get("content", "No original text available."),  # ✅ Extract text
                            "similarity_score": 1.0,  # ✅ Exact match gets full confidence
                            "match_type": "passed_law_direct_mapping"
                        })


        # Second, check mentions of U.S. Code sections directly in bill text    
        mentioned_sections = extract_us_code_mentions(bill_text)

        for mention in mentioned_sections:
            title_number = mention["title_number"]
            section_number = mention["section_number"]

            # 🔍 Try to find exact match in U.S. Code database
            for us_code_key, us_code_data in self.us_code_sections.items():
                if (
                    str(us_code_data.get("title_number")) == str(title_number) and
                    str(us_code_data.get("section_number")) == str(section_number)
                ):
                    matched_sections.append({
                        "section_id": f"{title_number} U.S.C. {section_number}",
                        "title_number": title_number,
                        "section_number": section_number,
                        "us_code_text": us_code_data.get("content", "No original text available."),  # ✅ Extract text directly
                        "similarity_score": 1.0,  # ✅ Exact match gets full confidence
                        "match_type": "mentioned_in_bill_mapping"
                    })


        # Third, If no direct matches found, fallback to FAISS search
        if not matched_sections:
            matched_sections = self.us_code_matcher.search_similar_sections(bill_text, top_k=top_k)

        return matched_sections[:top_k]


    def analyze_modifications(self, bill_id, bill_text):
        """Finds relevant U.S. Code sections and analyzes the impact of the bill."""

        similar_sections = self.find_similar_us_code_sections(bill_id, bill_text)

        became_law = self.bills.get(bill_id, {}).get("became_law", False)

        modification_summaries = []
        
        for section_info in similar_sections:
            section_id = section_info["section_id"]
            similarity_score = section_info["similarity_score"]
            match_type = section_info["match_type"]
            original_text = section_info["us_code_text"]


            if not original_text or original_text == "No original text available.":
                print(f"⚠️ No official U.S. Code text found for {section_id}.")
                


            # Analyze modifications using LLM
            summary = self.llm_client.summarize_modification(
                original_text, bill_text, section_id, became_law
            )

            parsed_summary = parse_textblock(summary)

            modification_summaries.append({
                "us_code_section": section_id,
                "similarity_score": similarity_score,
                "match_type": match_type,
                "modification_summary": parsed_summary
            })

        bill_title = self.bills.get(bill_id, {}).get("title", "Unknown Title")
        became_law = self.bills.get(bill_id, {}).get("became_law", "Unknown Title")


        # ✅ New: Let Claude determine affected demographic groups
        print(f"🔎 Asking LLM to determine affected demographics for {bill_id}...")
        demographic_results = self.llm_client.identify_affected_demographics(
            bill_text, similar_sections
        )

        parsed_demographic_results = parse_textblock(demographic_results)

        return {
            "title": bill_title,
            "became_law": became_law, 
            "legal_modifications": modification_summaries,
            "matched_demographics": parsed_demographic_results
        }
        # Match bill to demographics
        #print("🔎 Finding relevant demographic groups for bill...")
        #demographic_matches = self.demographic_matcher.find_similar_demographic_groups(bill_text, top_k=5)

        #matched_demographics = [{"group": group, "similarity_score": float(score)} for group, score in demographic_matches]

        #print(f"Demographics matched: {matched_demographics}")

        #print(f"⏳ Bill analysis completed in {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    processor = BillTextAnalyzer()

    results = {}
    bill_limit = 20  
    bill_count = 0  

    # Load previous analysis results if available
    try:
        with open(BILL_IMPACT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    except FileNotFoundError:
        results = {}

    for congress, bill_type, bill_number in TARGET_BILLS:
        bill_id = f"{congress}_{bill_type}_{bill_number}"

        if bill_id in processor.processed_bills:
            print(f"🚫 Skipping {bill_id}, already analyzed.")
            continue  

        print(f"\n🔍 Processing Bill: {bill_id}")

        bill_data = processor.bills.get(bill_id, {})
        bill_text = bill_data.get("bill_text_raw", "")

        if not bill_text:
            print(f"Skipping {bill_id}, no bill text available.")
            continue

        results[bill_id] = processor.analyze_modifications(bill_id, bill_text)
        processor.save_processed_bill(bill_id)  # Log bill as processed
        print(f"Finished analyzing Bill: {bill_id}")

        bill_count += 1  

        # Save progress every 10 bills in case of API errors
        if bill_count % 10 == 0:
            print(" Saving progress...")
            with open(BILL_IMPACT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=4)

    # Final save after processing
    with open(BILL_IMPACT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"\nAnalysis complete! Results saved to {BILL_IMPACT_FILE}")




