def embed_query(text, client, logger, silent=False):
    try:
        if not silent:
            logger.log_time("Generated embedding of length 1536")
        
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        embedding = response.data[0].embedding
        return embedding
    except Exception as e:
        logger.error("Embedding failed", e)
        raise e
    
def embed_batch(texts, client, logger, silent=False):
    try:
        if not silent:
            logger.log_time(f"Batch embedding {len(texts)} texts")

        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts  # <--- Batch list
        )
        vectors = [item.embedding for item in response.data]
        return vectors

    except Exception as e:
        logger.error("Batch embedding failed", e)
        raise e