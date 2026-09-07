import os
from openai import OpenAI
class LLM:
    def __init__(self):
        key=os.getenv('OPENAI_API_KEY')
        if not key: raise RuntimeError('OPENAI_API_KEY is required')
        self.client=OpenAI(api_key=key); self.model=os.getenv('OPENAI_MODEL','gpt-4o-mini')
    def complete(self,prompt,temperature=0):
        r=self.client.chat.completions.create(model=self.model,messages=[{'role':'system','content':'You are a conservative financial research analyst. Use only supplied evidence; never invent facts, figures, citations, or sources.'},{'role':'user','content':prompt}],temperature=temperature)
        return r.choices[0].message.content
