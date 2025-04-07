from models.embedder_and_faiss_indexer import EmbeddingFAISSManager

class DemographicMatcher:
    """
    Handles finding similar demographic groups for a given bill text using FAISS.
    The FAISS index needs to be created before this, using embedder_and_faiss_indexer.
    """

    def __init__(self, faiss_index_path="faiss_indexes/faiss_demographics.index"):
        """
        Initializes the FAISS manager for demographics matching. In other words,
        """
        self.demographic_faiss = EmbeddingFAISSManager()
        self.demographic_faiss.load_faiss_index(faiss_index_path)

    def find_similar_demographic_groups(self, bill_text, top_k=5):
        """Finds the most relevant demographic groups for a given bill text  FAISS.
        
        Args:
            bill_text (str): The full text of the bill.
            top_k (int): Number of similar demographic groups to retrieve.

        Returns:
            List[Tuple[str, float]]: List of demographic groups and their similarity scores.
        """
        results = self.demographic_faiss.search_faiss(bill_text, top_k)
        return [(demographic, float(score)) for demographic, score in results]  # Ensure JSON serializable scores
