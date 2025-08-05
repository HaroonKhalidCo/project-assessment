from google import genai
from google.genai import types
import asyncio

class GeminiDocEvaluator:
    def __init__(self):
        self.client = genai.Client()

    async def evaluate(self, file_path: str, prompt: str, model: str = "gemini-2.5-flash") -> str:
        loop = asyncio.get_event_loop()
        # Upload file asynchronously
        myfile = await loop.run_in_executor(None, lambda: self.client.files.upload(file=file_path))
        try:
            # Generate content asynchronously
            def generate():
                return self.client.models.generate_content(
                    model=model,
                    contents=[prompt, myfile]
                )
            response = await loop.run_in_executor(None, generate)
            return response.text
        finally:
            # Delete the file from Gemini after evaluation
            await loop.run_in_executor(None, lambda: self.client.files.delete(name=myfile.name))