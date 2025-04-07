from models.embedder_and_faiss_indexer import EmbeddingFAISSManager

class USCodeMatcher:
    def __init__(self, us_code_data):
        """
        Initialize FAISS search for U.S. Code similarity.
        The FAISS index needs to be created before this, using embedder_and_faiss_indexer.
        """
        print("🔄 Loading FAISS index for U.S. Code matching...")
        self.us_code_faiss = EmbeddingFAISSManager()
        self.us_code_faiss.load_faiss_index("faiss_indexes/faiss_us_code.index")
        self.us_code_data = us_code_data

    def search_similar_sections(self, bill_text, top_k=3):
        """
        Finds the most similar U.S. Code sections for a given bill text using FAISS.

        Args:
            bill_text (str): The text of the bill.
            top_k (int): Number of closest U.S. Code sections to retrieve.

        Returns:
            List[Dict]: A list of dictionaries, each containing:
                - "section": U.S. Code section identifier
                - "similarity_score": Float score
                - "match_type": "faiss_semantic_match"
        """
        print(f"🔍 Searching FAISS for similar U.S. Code sections...")

        faiss_results = self.us_code_faiss.search_faiss(bill_text, top_k)

        results = []

        for section_id, score in faiss_results:
            us_code = self.us_code_data.get(section_id, {})
            title_number = us_code.get("title_number")
            section_number = us_code.get("section_number")
            us_code_text = us_code.get("content", "No original text available.")

            results.append({
                "section_id": section_id,
                "title_number": title_number,
                "section_number": section_number,
                "us_code_text": us_code_text,
                "similarity_score": float(score),
                "match_type": "faiss_semantic_match"
            })

        print(f"✅ Found {len(results)} similar U.S. Code sections via FAISS.")
        return results

