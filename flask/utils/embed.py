import numpy as np

def embed_query(text: str, client, logger) -> np.ndarray:
    result = client.embeddings.create(
        input=[text],
        model="text-embedding-ada-002"
    )
    vec = np.array(result.data[0].embedding, dtype="float32")
    logger.log_time(f"Generated embedding of length {len(vec)}")
    return vec