import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pathlib import Path
import json


class EmbeddingFAISSManager:
    """Handles embedding creation and FAISS index management for different types of data."""

    def __init__(self, model_name="sentence-transformers/all-MiniLM-L12-v2"):
        self.embedding_model = SentenceTransformer(model_name)
        self.faiss_index = None
        self.lookup = []
        self.index_path = None  # Path for saving/loading FAISS index

    def create_embedding(self, text):
        """Generate text embeddings using Sentence Transformers."""
        return self.embedding_model.encode(text, convert_to_numpy=True)

    def create_faiss_index_for_us_code(self, us_code_data, index_path="faiss_indexes/faiss_us_code.index"):
        """
        Creates and saves a FAISS index specifically for U.S. Code data.

        :param us_code_data: Dictionary where each key is a section ID, and the value contains a "content" field.
        :param index_path: Path to save the FAISS index.
        """
        self.index_path = Path(index_path)

        # Check if FAISS index already exists
        if self.index_path.exists():
            print(f"📂 FAISS index already exists at {self.index_path}. Loading existing index...")
            self.load_faiss_index(index_path)
            return

        print(f"Creating FAISS index for U.S. Code at {self.index_path}...")

        embeddings = []
        self.lookup = []

        for i, (section_id, details) in enumerate(us_code_data.items(), start=1):  
            if "content" in details and isinstance(details["content"], str):
                text = details["content"]
                embeddings.append(self.create_embedding(text).astype("float32"))
                self.lookup.append(section_id)

                if i % 50 == 0:  # ✅ Now using `i`, which is an integer
                    print(f"  🔹 Processed {i}/{len(us_code_data)} sections...")

        if not embeddings:
            raise ValueError("No valid 'content' found in U.S. Code data.")


        # Create FAISS index
        dimension = embeddings[0].shape[0]
        self.faiss_index = faiss.IndexFlatL2(dimension)
        self.faiss_index.add(np.array(embeddings))

        # Save FAISS index and lookup
        self.save_faiss_index()
        print(f"AISS index for U.S. Code created and saved.")

    def create_faiss_index_for_demographics(self, demographic_data, index_path="faiss_indexes/faiss_demographics.index"):
        """
        Creates and saves a FAISS index specifically for demographic data.

        :param demographic_data: Dictionary where keys are categories, and values contain subcategories with lists of related terms.
        :param index_path: Path to save the FAISS index.
        """
        self.index_path = Path(index_path)

        # Check if FAISS index already exists
        if self.index_path.exists():
            print(f"📂 FAISS index already exists at {self.index_path}. Loading existing index...")
            self.load_faiss_index(index_path)
            return

        print(f"🔄 Creating FAISS index for Demographics at {self.index_path}...")

        embeddings = []
        self.lookup = []

        for category, subcategories in demographic_data.items():
            for group, related_terms in subcategories.items():
                if isinstance(related_terms, list) and len(related_terms) > 0:
                    avg_embedding = np.mean([self.create_embedding(term) for term in related_terms], axis=0)
                    embeddings.append(avg_embedding)
                    self.lookup.append(f"{category} - {group}")  # Example: "Race - White"

        if not embeddings:
            raise ValueError("No valid demographic terms found in demographic data.")

        # Create FAISS index
        dimension = embeddings[0].shape[0]
        self.faiss_index = faiss.IndexFlatL2(dimension)
        self.faiss_index.add(np.array(embeddings))

        # Save FAISS index and lookup
        self.save_faiss_index()
        print(f"FAISS index for Demographics created and saved.")

    def save_faiss_index(self):
        """Saves FAISS index and lookup table."""
        if self.index_path:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.faiss_index, str(self.index_path))

            # Save lookup list
            lookup_path = self.index_path.with_suffix(".json")
            with open(lookup_path, "w", encoding="utf-8") as f:
                json.dump(self.lookup, f, indent=4)

            print(f"FAISS index and lookup saved to {self.index_path}")

    def load_faiss_index(self, index_path):
        """Loads FAISS index from a file."""
        self.index_path = Path(index_path)

        if self.index_path.exists():
            self.faiss_index = faiss.read_index(str(self.index_path))
            lookup_path = self.index_path.with_suffix(".json")

            if lookup_path.exists():
                with open(lookup_path, "r", encoding="utf-8") as f:
                    self.lookup = json.load(f)

            print(f"FAISS index loaded from {self.index_path}")
        else:
            raise FileNotFoundError(f"FAISS index not found at {self.index_path}")

    def search_faiss(self, query_text, top_k=3):
        """Finds the most relevant matches from the FAISS index."""
        if self.faiss_index is None:
            raise ValueError("FAISS index is not initialized.")

        query_embedding = self.create_embedding(query_text).astype("float32")
        distances, indices = self.faiss_index.search(np.array([query_embedding]), top_k)

        results = []
        for i, index in enumerate(indices[0]):
            if index < 0 or index >= len(self.lookup):
                continue

            identifier = self.lookup[index]
            similarity_score = 1 / (1 + distances[0][i])
            results.append((identifier, similarity_score))

        return sorted(results, key=lambda x: x[1], reverse=True)



# ----------------------------
# **Create the embeddings, then FAISS indexes for demographics data dict and U.S. code sections **
# ----------------------------

if __name__ == "__main__":
    # Load U.S. Code Data
    us_code_path = "data_output/processed_uscode_sections.json"
    with open(us_code_path, "r", encoding="utf-8") as f:
        us_code_data = json.load(f)

    # Create FAISS index for U.S. Code
    manager = EmbeddingFAISSManager()
    manager.create_faiss_index_for_us_code(us_code_data, "faiss_indexes/faiss_us_code.index")

    demographic_path = "data/demographic_data.json"
    with open(demographic_path, "r", encoding="utf-8") as f:
        demographic_data = json.load(f)

    # Create FAISS index for Demographics
    manager.create_faiss_index_for_demographics(demographic_data, "faiss_indexes/faiss_demographics.index")

