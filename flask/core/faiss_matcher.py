import faiss
import numpy as np
import json
from pathlib import Path
from utils.embed import embed_query, embed_batch
from dataclasses import dataclass
from enum import Enum

from core.session_manager import SessionManager

class MatchStatus(Enum):
    NO_TASK_MATCH = "NO_TASK_MATCH"
    NO_STEP_MATCH = "NO STEP MATCH"
    MATCHED = "MATCHED"

@dataclass
class MatchResult:
    status: MatchStatus
    task: dict = None
    step: dict = None

class FaissMatcher:
    def __init__(self, index_path: Path, meta_path: Path, dim: int = 1536):
        self.index = faiss.read_index(str(index_path))
        self.dim = dim
        with open(meta_path, encoding="utf-8") as f:
            self.meta = json.load(f)

    def set_step_vectors(self, match_result, client, logger, session_id):
        steps = match_result.get('steps')
        if not steps or not isinstance(steps, list):
            raise ValueError("❌ Invalid or missing steps in task metadata.")

        # Filter steps with non-empty text
        step_texts = [
            (step.get("text", "") + " " + " ".join(step.get("keywords", []))).strip()
            for step in steps
        ]
        step_texts = [text for text in step_texts if text]

        if not step_texts:
            raise ValueError("❌ No valid step texts to embed.")

        # Try batch embedding
        try:
            vectors = embed_batch(step_texts, client, logger, silent=True)
            if not vectors:
                raise ValueError("❌ Embedding failed: no vectors returned.")

            vectors = np.stack(vectors)
            SessionManager.set_step_vectors(session_id, vectors)

        except Exception as e:
            logger.error("❌ Failed to set step vectors:", e)
            raise e

    def process(self, session_id, query, client, logger):
        logger.info("🔍 Processing user input for task or step matching.")

        query_embedding = embed_query(query, client, logger)

        current_task = SessionManager.get_matched_task(session_id)

        if not current_task or self.user_says_mismatch(query, client, current_task, SessionManager.get_current_step(session_id)):
            logger.info("No active task. Trying to match a new task.")
            match = self.match_task(query_embedding, logger)
            if match is not None:
                SessionManager.set_matched_task(session_id, match)
                self.set_step_vectors(match, client, logger, session_id)
            else:
                return MatchResult(
                    MatchStatus.NO_TASK_MATCH
                )

        current_task = SessionManager.get_matched_task(session_id)

        current_step = self.match_step_in_task(current_task, query_embedding, logger, session_id)
        if current_step is not None:
            SessionManager.set_current_step(session_id, current_step)
        else:
            return MatchResult(
                MatchStatus.NO_STEP_MATCH,
                task=current_task
            )

        return MatchResult(
            MatchStatus.MATCHED,
            task=current_task,
            step=current_step
        )

    def user_says_mismatch(self, text: str, openai_client, task_match=None, current_step_num=None) -> bool:
        try:
            current_step = ""
            if task_match and current_step_num is not None:
                steps = task_match.get('steps', [])
                if 0 <= current_step_num < len(steps):
                    current_step = steps[current_step_num].get('text', '')

            prompt_context = f"Task title: {task_match.get('title', '')}\nCurrent step description: {current_step}\nUser's latest message: {text}"

            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are helping determine if the user's latest message fits into the current task and step context. If it fits, reply ONLY 'confirm'. If it is a new unrelated topic, reply ONLY 'reject'."},
                    {"role": "user", "content": prompt_context}
                ]
            )
            result = response.choices[0].message.content.strip().lower()
            return result == "reject"

        except Exception as e:
            print(f"⚠️ AI mismatch detection failed: {e}")
            return False
        
    def match_task(self, query_embedding, logger):
        D, I = self.index.search(np.array([query_embedding]), k=1)
        best_distance = D[0][0]
        best_idx = I[0][0]

        if 0 <= best_idx < len(self.meta) and best_distance <= 0.40:
            best_task = self.meta[best_idx]
            logger.info(f"\n✅ Task matched: {best_task['title']}")
            logger.info(f"📏 Task distance: {best_distance:.4f}")
            return best_task
        else:
            logger.info("❌ No task match found.")
            return None
        
    def match_step_in_task(self, task_meta: dict, query_embedding, logger, session_id: str):
        steps = task_meta.get("steps", [])
        if not steps:
            logger.info("❌ No steps found in task.")
            return None

        # 🧠 Get precomputed step vectors
        step_vectors = SessionManager.get_step_vectors(session_id)
        if step_vectors is None:
            logger.error("❌ Step vectors missing.")
            return None

        # Build a temporary FAISS index
        index = faiss.IndexFlatL2(step_vectors.shape[1])
        index.add(step_vectors)

        # Search
        D, I = index.search(np.array([query_embedding]), k=1)

        best_distance = D[0][0]
        best_idx = I[0][0]

        if 0 <= best_idx < len(steps) and best_distance <= 0.40:
            best_step = steps[best_idx]
            logger.info(f"\n✅ Step matched: Step {best_step.get('step_num', best_idx)}")
            logger.info(f"📝 {best_step.get('text', '')}")
            logger.info(f"📏 Step distance: {best_distance:.4f}")
            return best_step
        else:
            logger.info("❌ No step match found.")
            return None


