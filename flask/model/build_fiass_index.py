import os
import json
import faiss
import numpy as np
from pathlib import Path
import openai

# --- CONFIG ---
OPENAI_API_KEY="sk-proj-..."
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

INSTRUCTIONS_DIR = Path("instructions")
VECTOR_DIR = Path("vector")
VECTOR_DIR.mkdir(exist_ok=True)

TASK_INDEX_FILE = VECTOR_DIR / "task_index.faiss"
TASK_META_FILE = VECTOR_DIR / "task_meta.json"

# --- EMBEDDING FUNCTION ---
def get_text_vector(text: str) -> np.ndarray:
    """Get text embedding vector using OpenAI ADA model (1536-dim)"""
    embedding = openai_client.embeddings.create(
        input=[text],
        model="text-embedding-ada-002"
    )
    return np.array(embedding.data[0].embedding, dtype="float32")

# --- BUILD GLOBAL TASK VECTOR ---
def build_task_vector(task_json: dict) -> np.ndarray:
    base_text = task_json["title"] + "\n" + task_json["intro"]
    return get_text_vector(base_text)

# --- BUILD PER-TASK STEP VECTORS ---
def build_step_vectors(task_json: dict):
    steps = task_json.get("steps", [])
    vectors = []
    meta = []

    for step in steps:
        text = step.get("text", "").strip()
        if not text:
            continue

        vec = get_text_vector(text)
        vectors.append(vec)
        meta.append({
            "step_num": step.get("step_num", 0),
            "text": text,
            "keywords": step.get("keywords", []),
            "images": step.get("images", [])
        })

    return vectors, meta

# --- MAIN RUN ---
def run():
    task_vectors = []
    task_metadata = []

    for task_folder in INSTRUCTIONS_DIR.iterdir():
        if not task_folder.is_dir():
            continue

        json_file = task_folder / "structured_output.json"
        if not json_file.exists():
            print(f"⚠️ Skipping {task_folder.name}: no structured_output.json")
            continue

        with open(json_file, encoding="utf-8") as f:
            task = json.load(f)

        # --- Build Global Task Vector ---
        try:
            task_vec = build_task_vector(task)
            task_vectors.append(task_vec)
            task_metadata.append({
                "task_id": task["task_id"],
                "title": task["title"],
                "intro": task["intro"],
                "steps": task["steps"]
            })
            print(f"✅ Embedded TASK: {task['title']}")
        except Exception as e:
            print(f"❌ Failed task embedding {task_folder.name}: {e}")
            continue

        # --- Build Step-level FAISS ---
        try:
            step_vectors, step_meta = build_step_vectors(task)
            if not step_vectors:
                print(f"⚠️ No steps found for {task['task_id']}")
                continue

            step_index = faiss.IndexFlatL2(1536)
            step_index.add(np.stack(step_vectors))

            step_faiss_path = VECTOR_DIR / f"steps_{task['task_id']}.faiss"
            step_meta_path = VECTOR_DIR / f"steps_{task['task_id']}_meta.json"

            faiss.write_index(step_index, str(step_faiss_path))
            with open(step_meta_path, "w", encoding="utf-8") as f:
                json.dump(step_meta, f, ensure_ascii=False, indent=2)

            print(f"✅ Embedded STEPS for {task['task_id']}")

        except Exception as e:
            print(f"❌ Failed step embedding for {task_folder.name}: {e}")
            continue

    # --- Save Global TASK FAISS ---
    if not task_vectors:
        print("❌ No valid tasks found. Exiting.")
        return

    dim = task_vectors[0].shape[0]
    if dim != 1536:
        raise ValueError(f"Expected 1536-dim embeddings, got {dim}")

    task_index = faiss.IndexFlatL2(dim)
    task_index.add(np.stack(task_vectors))

    faiss.write_index(task_index, str(TASK_INDEX_FILE))
    with open(TASK_META_FILE, "w", encoding="utf-8") as f:
        json.dump(task_metadata, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Global TASK index saved to {TASK_INDEX_FILE}")
    print(f"✅ Global TASK metadata saved to {TASK_META_FILE}")

if __name__ == "__main__":
    run()
