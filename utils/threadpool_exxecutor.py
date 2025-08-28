from concurrent.futures import ThreadPoolExecutor
import os

# ThreadPool for blocking work (transcribe, LLM calls)
EXECUTOR = ThreadPoolExecutor(max_workers=max(4, os.cpu_count() or 4))
