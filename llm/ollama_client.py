import os
import requests


class OllamaClient:
    """Ollama client with installed-model discovery and bounded generation."""

    def __init__(self, model=None, base_url=None, timeout=None):
        self.base_url = (
            base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        ).rstrip('/')
        self.connect_timeout = float(os.getenv('OLLAMA_CONNECT_TIMEOUT', '3'))
        self.timeout = float(timeout or os.getenv('OLLAMA_TIMEOUT', '90'))
        self.num_predict = int(os.getenv('OLLAMA_NUM_PREDICT', '450'))
        self.num_ctx = int(os.getenv('OLLAMA_NUM_CTX', '4096'))
        self.model = model or os.getenv('OLLAMA_MODEL') or self._discover_model()

    def _tags(self):
        r = requests.get(self.base_url + '/api/tags', timeout=self.connect_timeout)
        r.raise_for_status()
        return [m.get('name') for m in r.json().get('models', []) if m.get('name')]

    def _discover_model(self):
        names = self._tags()
        if not names:
            raise RuntimeError('Ollama is reachable, but no models are installed.')
        # Respect the installed model list; do not assume a model name.
        return names[0]

    def health(self):
        try:
            names = self._tags()
            if not names:
                return False, 'Ollama is reachable, but no models are installed.'
            if self.model not in names:
                base = self.model.split(':')[0]
                match = next((n for n in names if n.split(':')[0] == base), None)
                if match:
                    self.model = match
                else:
                    return False, f'Ollama is reachable, but model `{self.model}` is not installed. Installed: {", ".join(names)}'
            return True, f'Ollama is reachable and model `{self.model}` is available.'
        except Exception as exc:
            return False, f'Ollama unavailable at `{self.base_url}`: {type(exc).__name__}: {exc}'

    def available_models(self):
        return self._tags()

    def chat(self, prompt, system=None, temperature=0.0):
        ok, message = self.health()
        if not ok:
            raise RuntimeError(message)

        full_prompt = prompt if not system else (
            f'System instructions:\n{system}\n\nUser request:\n{prompt}'
        )
        payload = {
            'model': self.model,
            'prompt': full_prompt,
            'stream': False,
            'options': {
                'temperature': temperature,
                'num_predict': self.num_predict,
                'num_ctx': self.num_ctx,
                'top_k': 20,
            },
            'keep_alive': '5m',
        }
        try:
            r = requests.post(
                self.base_url + '/api/generate',
                json=payload,
                timeout=(self.connect_timeout, self.timeout),
            )
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f'Ollama generation timed out after {self.timeout:.0f}s for model `{self.model}`.'
            ) from exc
        r.raise_for_status()
        response = r.json().get('response')
        if not response or not response.strip():
            raise RuntimeError('Ollama returned an empty response.')
        return response.strip()
