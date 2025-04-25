import faiss
import numpy as np
import json
from pathlib import Path
from utils.embed import embed_query

class FaissMatcher:
    def __init__(self, index_path: Path, meta_path: Path, dim: int = 1536):
        self.index = faiss.read_index(str(index_path))
        self.dim = dim
        with open(meta_path, encoding="utf-8") as f:
            self.meta = json.load(f)

    def match_task(self, logger, user_input: str, client):
        logger.info(f"Received user input: {user_input}")
        
        try:
            # Step 1: Get 1536-dim text embedding
            vec = embed_query(user_input, client, logger)
            logger.info(f"Text embedding generated: {vec[:10]}...")

            # Step 2: Dimension check
            if len(vec) != self.index.d:
                logger.error(f"FAISS dimension mismatch: index.d = {self.index.d}, embedding length = {len(vec)}")
                raise ValueError(f"FAISS dimension mismatch: index.d = {self.index.d}, embedding length = {len(vec)}")

            # Step 3: FAISS search
            D, I = self.index.search(np.array([vec]), k=1)
            logger.info(f"FAISS search results: Distance={D[0][0]}, Index={I[0][0]}")

            if D[0][0] > 0.45:
                logger.info("No confident match found.")
                return None, D[0][0]

            # Step 4: Load matched task
            top_index = I[0][0]
            if 0 <= top_index < len(self.meta):
                match = self.meta[top_index]
            else:
                match = {"id": top_index, "title": "Unknown"}

            logger.log_time(f"Match found: {match['title']}")
            return match, D[0][0]

        except Exception as e:
            logger.error("Error in match_task")
            raise e
