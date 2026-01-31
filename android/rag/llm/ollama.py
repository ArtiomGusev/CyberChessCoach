import json
import subprocess
from rag.llm.base import BaseLLM


class OllamaLLM(BaseLLM):
    def __init__(self, model: str, temperature: float = 0.2):
        self.model = model
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        """
        Calls local Ollama model via CLI.
        """

        cmd = [
            "ollama",
            "run",
            self.model,
            "--temperature",
            str(self.temperature),
        ]

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = process.communicate(prompt)

        if process.returncode != 0:
            raise RuntimeError(f"Ollama error: {stderr}")

        return stdout.strip()
