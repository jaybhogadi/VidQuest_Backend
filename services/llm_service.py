import asyncio
from utils.threadpool_exxecutor import EXECUTOR
from utils.settings import settings
from utils.log_details import logger
import re
import json
from Models.data_models import MCQQuestion,Option
from typing import List


# --------- LLM Service ---------
class LLMService:
    def __init__(self) -> None:
        self._llm = None
        self._lock = asyncio.Lock()

    def _initialize_sync(self) -> None:
        provider = settings.provider()
        logger.info(f"Initializing LLM provider: {provider}")
        if provider == "groq":
            from langchain_groq import ChatGroq

            self._llm = ChatGroq(api_key=settings.GROQ_API_KEY, model_name=settings.GROQ_MODEL)
        else:
            from langchain_groq import ChatGroq

            self._llm = ChatGroq(api_key=settings.GROQ_API_KEY, model_name=settings.GROQ_MODEL)
        
        logger.info("LLM initialized")

    async def ensure_llm(self) -> None:
        if self._llm is None:
            async with self._lock:
                if self._llm is None:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(EXECUTOR, self._initialize_sync)

    def _prompt(self, transcript: str, n: int) -> str:
        str1=f"""
You are an expert teacher. Based on the transcript below, generate {n} multiple-choice questions.

Transcript:
{transcript}

Rules for each question:
1) Clear, concise question based on facts from transcript
2) 4 options with IDs A, B, C, D
3) Indicate the correct answer (A-D)
4) One-sentence explanation for why the answer is correct

Return STRICT JSON as an array like this:
[
  {{
    "question": "...",
    "options": [
      {{"id":"A","text":"..."}},
      {{"id":"B","text":"..."}},
      {{"id":"C","text":"..."}},
      {{"id":"D","text":"..."}}
    ],
    "correct_answer": "A",
    "explanation": "..."
  }}
]
Only output the JSON array, nothing else.
"""
        return str1
    
    import json, re

    def _extract_json_array(self,text: str) -> str:
        m = re.search(r"```(?:json)?\s*(\[\s*{[\s\S]*?}\s*\])\s*```", text, re.I)
        if m: return m.group(1)
        m = re.search(r"\[\s*{[\s\S]*?}\s*\]", text)
        return m.group(0) if m else text.strip()

    def _repair_json(self,raw: str) -> str:
        # keep only the first JSON array window
        print("raw content is",raw)
        # m = re.search(r"\[\s*{[\s\S]*?}\s*\]", raw)
        # if m: raw = m.group(0)

        # # 1) remove invalid backslash escapes of apostrophes
        # raw = raw.replace("\\'", "'")

        # # 2) remove trailing commas before ] or }
        # raw = re.sub(r",\s*([\]}])", r"\1", raw)

        # # 3) insert missing commas between adjacent objects
        # raw = re.sub(r"}\s*{", "},{", raw)

        return raw

    def _safe_json_loads(self,text: str):
        raw = self._extract_json_array(text)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            fixed = self._repair_json(raw)
            return json.loads(fixed)

    def _generate_mcqs_sync(self, transcript: str, n: int) -> List[MCQQuestion]:
        assert self._llm is not None, "LLM not initialized"
        prompt = self._prompt(transcript, n)
        # `invoke` may return an object with `.content`
        resp = self._llm.invoke(prompt)
        print("resp",resp)
        content = getattr(resp, "content", str(resp))
        json_match = re.search(r'\[\s*{.*}\s*\]', content, re.DOTALL)
        print("after json match",json_match)
        if json_match:
            json_str = json_match.group(0)
            mcq_data = json.loads(json_str)
        else:
            # Fallback if JSON extraction fails
            logger.warning("Failed to extract JSON from LLM response, using fallback parsing")
            mcq_data = self._parse_non_json_response(content)
        
        # Convert to MCQQuestion objects
        mcqs = []
        for item in mcq_data:
            print("item is",item)
        for item in mcq_data:
            mcq = MCQQuestion(
                question=item["question"],
                options=[Option(**opt) for opt in item["options"]],
                correct_answer=item["correct_answer"],
                explanation=item.get("explanation", "")
            )
            mcqs.append(mcq)
        
        logger.info(f"Successfully generated {len(mcqs)} MCQs")
        return mcqs

        
        # # Extract JSON array robustly
        # json_match = re.search(r"\[\s*{[\s\S]*?}\s*\]", content)
        # if not json_match:
        #     print("LLM did not return JSON array")
        #     raise RuntimeError("LLM did not return JSON array")
        # # data = json.loads(json_match.group(0))
        # # data=self._safe_json_loads(json_match.group(0))

        # mcqs: List[MCQQuestion] = []
        # for item in resp:
        #     # Normalize options to dicts with id+text
        #     opts_in = item.get("options", [])
        #     norm_opts: List[Option] = []
        #     for opt in opts_in:
        #         if isinstance(opt, dict):
        #             norm_opts.append(Option(id=str(opt.get("id")), text=str(opt.get("text"))))
        #         else:
        #             # if plain strings are returned, map sequentially
        #             idx = ["A", "B", "C", "D"][len(norm_opts)] if len(norm_opts) < 4 else "A"
        #             norm_opts.append(Option(id=idx, text=str(opt)))
        #     q = MCQQuestion(
        #         question=str(item.get("question")),
        #         options=norm_opts,
        #         correct_answer=str(item.get("correct_answer")).strip(),
        #         explanation=str(item.get("explanation", "")),
        #     )
        #     mcqs.append(q)
        # return mcqs

    def _parse_non_json_response(self, content: str) -> List[dict]:
        """Fallback parser for non-JSON responses"""
        # Simple regex-based parser for when the LLM doesn't return proper JSON
        questions = []
        current_q = None
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            
            # New question starts
            if re.match(r'^(\d+\.|\*)\s*.*\?', line):
                if current_q:
                    questions.append(current_q)
                current_q = {"question": re.sub(r'^(\d+\.|\*)\s*', '', line), "options": [], "correct_answer": "", "explanation": ""}
            
            # Option line
            elif current_q and re.match(r'^[A-D]\.', line):
                opt_id = line[0]
                opt_text = re.sub(r'^[A-D]\.\s*', '', line)
                current_q["options"].append({"id": opt_id, "text": opt_text})
            
            # Correct answer line
            elif current_q and re.search(r'correct\s+answer', line.lower()):
                match = re.search(r'[A-D]', line)
                if match:
                    current_q["correct_answer"] = match.group(0)
            
            # Explanation line
            elif current_q and re.search(r'explanation', line.lower()):
                current_q["explanation"] = re.sub(r'^explanation\s*:?\s*', '', line, flags=re.IGNORECASE)
        
        # Add the last question
        if current_q:
            questions.append(current_q)
        
        return questions
    
    async def generate_mcqs(self, transcript: str, n: int) -> List[MCQQuestion]:
        await self.ensure_llm()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(EXECUTOR, self._generate_mcqs_sync, transcript, n)

llm_service = LLMService()