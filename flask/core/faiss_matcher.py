import faiss
import numpy as np
import json
from pathlib import Path
from utils.embed import embed_query
from dataclasses import dataclass
from enum import Enum

from core.session_manager import SessionManager

class MatchAction(Enum):
    LOCKED_NEW_TASK = "LOCKED_NEW_TASK"
    CONTINUING_TASK = "CONTINUING_TASK"
    MISMATCH_UNLOCK = "MISMATCH_UNLOCK"
    TASK_COMPLETED_UNLOCK = "TASK_COMPLETED_UNLOCK"
    NO_MATCH_FOUND = "NO_MATCH_FOUND"

@dataclass
class MatchResult:
    action: MatchAction
    task: dict = None
    step: int = 0
    message: str = ""
    step_info: dict = None

class FaissMatcher:
    def __init__(self, index_path: Path, meta_path: Path, dim: int = 1536):
        self.index = faiss.read_index(str(index_path))
        self.dim = dim
        with open(meta_path, encoding="utf-8") as f:
            self.meta = json.load(f)

    def match_task(self, logger, user_input: str, client):
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

    def match_task_or_continue(self, session_id, text, openai_client, logger):
        task_match = SessionManager.get_matched_task(session_id)
        logger.info(f"--------- MATCH OR CONTINUE ---------")
        if not task_match:
            logger.info(f"no match found for user {session_id}")
            task_match, confidence = self.match_task(logger, text, openai_client)
            if not task_match:
                return MatchResult(action=MatchAction.NO_MATCH_FOUND, message="No task found.")
            SessionManager.set_matched_task(session_id, task_match)
            SessionManager.set_current_step(session_id, 0)
            return MatchResult(action=MatchAction.LOCKED_NEW_TASK, task=task_match, step=0)

        logger.info("MATCH")
        logger.info(task_match)
        current_step = SessionManager.get_current_step(session_id)

        # --- 🔥 TRY TO MATCH USER TO STEP FIRST ---
        matched_step_num, matched_step_info = self.match_step_in_task(task_match, text, openai_client)
        logger.info("MATCH STEP")
        logger.info(matched_step_info)

        if matched_step_num is not None:
            logger.info(f"Matched inside task to step {matched_step_num}")
            SessionManager.set_current_step(session_id, matched_step_num)
            return MatchResult(
                action=MatchAction.CONTINUING_TASK,
                task=task_match,
                step=matched_step_num,
                step_info=matched_step_info
            )

        # --- 🧠 IF NO GOOD STEP MATCH, CHECK IF USER CHANGED TOPIC ---
        if self.user_says_mismatch(text, openai_client, task_match, current_step):
            SessionManager.unlock_task(session_id)
            return MatchResult(action=MatchAction.MISMATCH_UNLOCK, message="Mismatch detected.")

        # --- ✅ Otherwise just go to next sequential step ---
        if current_step >= self.count_steps(task_match):
            SessionManager.unlock_task(session_id)
            return MatchResult(action=MatchAction.TASK_COMPLETED_UNLOCK, message="Task completed.")

        SessionManager.set_current_step(session_id, current_step + 1)
        return MatchResult(
            action=MatchAction.CONTINUING_TASK,
            task=task_match,
            step=current_step + 1,
            step_info=None
        )

    def match_step_in_task(self, task_match, user_input, openai_client):
        """
        Matches user's input to the most relevant step inside the locked task.
        Returns best step number and step info.
        """
        steps = task_match.get('steps', [])
        if not steps:
            return None, None

        # You can embed user_input, embed all steps' keywords/text, then FAISS or cosine match
        # Or for start, simple GPT:
        step_candidates = "\n\n".join(
            f"Step {i}: {step.get('text', '')}" for i, step in enumerate(steps)
        )

        context = f"User input: {user_input}\nSteps:\n{step_candidates}\n\nIdentify which step best matches the user's input. Reply ONLY with 'step X' where X is the number."

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are matching user requests to steps in a process."},
                {"role": "user", "content": context}
            ]
        )

        result = response.choices[0].message.content.strip().lower()
        if "step" in result:
            try:
                step_num = int(result.replace("step", "").strip())
                if 0 <= step_num < len(steps):
                    return step_num, steps[step_num]
            except:
                pass

        return None, None
    
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


    def count_steps(self, task_match: dict) -> int:
        """
        Count number of steps inside the matched task.
        Assuming task_match has 'steps' field as a list.
        """
        if not task_match:
            return 0
        return len(task_match.get('steps', []))