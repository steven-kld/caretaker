import numpy as np

class Embedder:
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger

    def embed(self, text: str) -> np.ndarray:
        result = self.client.embeddings.create(
            input=[text],
            model="text-embedding-ada-002"
        )
        vec = np.array(result.data[0].embedding, dtype="float32")
        self.logger.log_time(f"Generated embedding of length {len(vec)}")
        return vec
