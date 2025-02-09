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



class BillTextAnalyzer:
    """Processes and analyzes Bill vs Code for impact assessment. Main Class for assignment"""

    def __init__(self):
        """Initialize components for bill-to-code matching and LLM processing."""
        print("Initializing LegalTextProcessor")

        # Load FAISS + U.S. Code Matcher
        self.us_code_matcher = USCodeMatcher()

        # Load LLM Client for Summarization
        self.llm_client = ClaudeLLM()

        # Load Data Files
        self.public_law_mapping = load_json("data_output/public_law_to_us_code_mapping.json")
        self.bills = load_json("data_processing/data_output/bill_data_118.json")
        self.us_code_sections = load_json("data_processing/data_output/processed_uscode_sections.json")

        self.demographic_matcher = DemographicMatcher()


    def get_us_code_sections_for_passed_bills(self):
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

    def find_similar_us_code_sections(self, bill_id, bill_text, top_k=3):
        """
        Finds the most relevant U.S. Code sections for a bill.

        - If the bill has been passed into law, it directly uses the mapped U.S. Code sections.
        - If the bill is NOT passed into law, it uses FAISS similarity search.

        Returns:
            List[Dict]: List of dictionaries with:
                - "section": U.S. Code section identifier
                - "similarity_score": Confidence score
                - "match_type": "direct_mapping" or "faiss_semantic_match"
        """

        # First, check if the bill has a Public Law mapping
        bill_mappings = self.get_us_code_sections_for_passed_bills()
        if bill_id in bill_mappings:
            # Direct mapping found
            us_code_sections = bill_mappings[bill_id]["us_code_sections"]

            return [{
                "section": f"{sec['title']} U.S.C. {sec['section']}",
                "similarity_score": float(1.0),
                "match_type": "direct_mapping"
            } for sec in us_code_sections]

        # No direct mapping, fallback to FAISS search
        return self.us_code_matcher.search_similar_sections(bill_text, top_k)

    def analyze_modifications(self, bill_text):
        """Finds relevant U.S. Code sections and analyzes the impact of the bill."""

        similar_sections = self.find_similar_us_code_sections(bill_id, bill_text)

        modification_summaries = []
        
        for section_info in similar_sections:
            section_id = section_info["section"]
            similarity_score = section_info["similarity_score"]
            match_type = section_info["match_type"]

            # Get original U.S. Code text
            original_text = self.us_code_sections.get(section_id, {}).get("content", "No original text available.")

            # Analyze modifications using LLM
            summary = self.llm_client.summarize_modification(original_text, bill_text, section_id)

            parsed_summary = parse_textblock(summary)


            modification_summaries.append({
                "section": section_id,
                "similarity_score": similarity_score,
                "match_type": match_type,
                "modification_summary": parsed_summary
            })

                # Match bill to demographics
        print("🔎 Finding relevant demographic groups for bill...")
        demographic_matches = self.demographic_matcher.find_similar_demographic_groups(bill_text, top_k=5)

        matched_demographics = [{"group": group, "similarity_score": float(score)} for group, score in demographic_matches]

        print(f"Demographics matched: {matched_demographics}")

        #print(f"⏳ Bill analysis completed in {time.time() - start_time:.2f} seconds.")

        return {
            "legal_modifications": modification_summaries,
            "matched_demographics": matched_demographics  # Include demographic matches in results
        }


if __name__ == "__main__":
    processor = BillTextAnalyzer()

    results = {}
    bill_limit = 50  
    bill_count = 0  

    for bill_id, bill_data in processor.bills.items():
        if bill_count >= bill_limit:
            break  

        print(f"\n🔍 Processing Bill: {bill_id}")
        bill_text = bill_data.get("bill_text_raw", "")

        if not bill_text:
            print(f"Skipping {bill_id}, no bill text available.")
            continue

        results[bill_id] = processor.analyze_modifications(bill_text)
        print(f"Finished analyzing Bill: {bill_id}")

        bill_count += 1  

    # Save results
    output_file = Path("data_output/bill_impact_analysis.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"\nAnalysis complete. Results saved to {output_file}")




