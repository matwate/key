import chromadb
from sentence_transformers import SentenceTransformer

COLLECTIONS = ["products", "food_storage", "products_spanish", "products_foodkeeper_es"]


class FoodDatabaseQuery:
    def __init__(
        self,
        db_path: str = "./chroma_db",
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ):
        self.client = chromadb.PersistentClient(path=db_path)
        self.model = SentenceTransformer(model_name)
        self.collections = {}
        for name in COLLECTIONS:
            try:
                self.collections[name] = self.client.get_collection(name=name)
            except:
                self.collections[name] = None
        loaded = {k: v is not None for k, v in self.collections.items()}
        print(f"[DATABASE] Loaded collections: {loaded}")

    def query(self, collection_name, query_text, n_results=5, filters=None):
        collection = self.collections.get(collection_name)
        if not collection:
            return None
        embedding = self.model.encode([query_text], convert_to_numpy=True)
        return collection.query(
            query_embeddings=embedding.tolist(),
            n_results=n_results,
            where=filters,
        )

    def query_all(self, query_text, n_results=5, filters=None):
        return {
            name: self.query(name, query_text, n_results, filters)
            for name in COLLECTIONS
        }
