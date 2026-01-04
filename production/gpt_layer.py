import os
import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


class GPTMarketJudge:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.cache = {}

    def _chat(self, k_title: str, p_title: str):
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY missing; set it in .env or environment.")

        prompt = (
            "Decide if these two market titles refer to the same underlying event. "
            "Answer with a single word: Yes or No.\n\n"
            f"Market A: {k_title}\n"
            f"Market B: {p_title}\n"
            "Answer:"
        )
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=20
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip().lower()

    def is_same_market(self, k_title: str, p_title: str):
        key = (k_title, p_title)
        if key in self.cache:
            return self.cache[key]
        try:
            ans = self._chat(k_title, p_title)
            decision = ans.startswith("y")
        except Exception:
            decision = True  # fail-open to avoid over-filtering
        self.cache[key] = decision
        return decision

