import os
import math
import json
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class TextEmbedder:
    def __init__(self, model: str = "text-embedding-3-small", cache_path: str = ".embeddings_cache.json"):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.cache_path = cache_path
        self.cache = self._load_cache()

    def _load_cache(self):
        if not self.cache_path:
            return {}
        try:
            with open(self.cache_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cache(self):
        if not self.cache_path:
            return
        try:
            with open(self.cache_path, "w") as f:
                json.dump(self.cache, f)
        except Exception:
            pass

    def embed(self, text: str):
        if text in self.cache:
            return self.cache[text]
        vecs = self.embed_batch([text])
        return vecs[0] if vecs else []

    def embed_batch(self, texts: list, batch_size: int = 100):
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY missing; set it in .env or environment.")

        results = [None] * len(texts)
        to_fetch = []
        to_fetch_idx = []

        for i, t in enumerate(texts):
            if t in self.cache:
                results[i] = self.cache[t]
            else:
                to_fetch.append(t)
                to_fetch_idx.append(i)

        for batch_start in range(0, len(to_fetch), batch_size):
            batch = to_fetch[batch_start:batch_start + batch_size]
            payload = {"model": self.model, "input": batch}
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.post(
                "https://api.openai.com/v1/embeddings", json=payload, headers=headers, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            for item in data:
                idx_in_batch = item["index"]
                embedding = item["embedding"]
                norm = math.sqrt(sum(v * v for v in embedding)) or 1.0
                vec = [v / norm for v in embedding]
                original_idx = to_fetch_idx[batch_start + idx_in_batch]
                original_text = texts[original_idx]
                self.cache[original_text] = vec
                results[original_idx] = vec

        self._save_cache()
        return results

    @staticmethod
    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b))


class TextSimilarity:
    def __init__(self, threshold: float = 0.45, model: str = "text-embedding-3-small"):
        self.embedder = TextEmbedder(model=model)
        self.threshold = threshold

    def is_similar(self, a: str, b: str):
        va = self.embedder.embed(a or "")
        vb = self.embedder.embed(b or "")
        score = self.embedder.cosine(va, vb)
        return score >= self.threshold, score

