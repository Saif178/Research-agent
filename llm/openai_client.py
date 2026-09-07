import os
from openai import OpenAI

class OpenAIClient:
    def __init__(self):
        key=os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        self.client=OpenAI(api_key=key, timeout=float(os.getenv("OPENAI_TIMEOUT", "45")))
        self.model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def chat(self, prompt, system=None, temperature=0):
        messages=[]
        if system:
            messages.append({"role":"system","content":system})
        messages.append({"role":"user","content":prompt})
        r=self.client.chat.completions.create(model=self.model,messages=messages,temperature=temperature,max_tokens=int(os.getenv("OPENAI_MAX_TOKENS","700")))
        out=r.choices[0].message.content
        if not out or not out.strip():
            raise RuntimeError("OpenAI returned an empty response.")
        return out.strip()

    def complete(self, prompt, system=None):
        return self.chat(prompt, system=system, temperature=0)


    # Compatibility alias used by the research engine.
