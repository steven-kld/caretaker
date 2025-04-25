import os
import json
import faiss
import numpy as np
from pathlib import Path
import openai

# --- CONFIG ---
OPENAI_API_KEY = "sk-proj-..."
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

INSTRUCTIONS_DIR = Path("instructions")
VECTOR_DIR = Path("vector")
VECTOR_DIR.mkdir(exist_ok=True)

INDEX_FILE = VECTOR_DIR / "task_index.faiss"
META_FILE = VECTOR_DIR / "task_meta.json"

# --- TEXT EMBEDDING FUNCTION ONLY ---
def get_text_vector(text: str) -> np.ndarray:
    """Get text embedding vector using OpenAI ADA model (1536-dim)"""
    embedding = openai_client.embeddings.create(
        input=[text],
        model="text-embedding-ada-002"
    )
    return np.array(embedding.data[0].embedding, dtype="float32")

def build_task_vector(task_json: dict) -> np.ndarray:
    """Build vector for task using only title + intro text"""
    base_text = task_json["title"] + "\n" + task_json["intro"]
    return get_text_vector(base_text)  # Returns 1536-dim vector

def run():
    vectors = []
    metadata = []

    for task_folder in INSTRUCTIONS_DIR.iterdir():
        if not task_folder.is_dir():
            continue

        json_file = task_folder / "structured_output.json"
        if not json_file.exists():
            print(f"⚠️ Skipping {task_folder.name}: no structured_output.json")
            continue

        with open(json_file, encoding="utf-8") as f:
            task = json.load(f)

        try:
            vec = build_task_vector(task)
            vectors.append(vec)
            metadata.append({
                "task_id": task["task_id"],
                "title": task["title"],
                "intro": task["intro"],
                "steps": task["steps"]
            })
            print(f"✅ Embedded: {task['title']}")
        except Exception as e:
            print(f"❌ Failed on {task_folder.name}: {e}")

    if not vectors:
        print("❌ No valid tasks found. Exiting.")
        return

    dim = vectors[0].shape[0]
    print(f"Index dimension: {dim}")
    if dim != 1536:
        raise ValueError(f"Expected 1536-dim embeddings, got {dim}")

    index = faiss.IndexFlatL2(dim)
    index.add(np.stack(vectors))

    faiss.write_index(index, str(INDEX_FILE))
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Index saved to {INDEX_FILE}")
    print(f"✅ Metadata saved to {META_FILE}")

if __name__ == "__main__":
    run()
