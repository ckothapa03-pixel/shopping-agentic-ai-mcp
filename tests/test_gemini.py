import asyncio
import os
from dotenv import load_dotenv
from google import genai

async def main():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    if not api_key:
        print("ERROR: GEMINI_API_KEY was not found in .env")
        return

    try:
        async with genai.Client(api_key=api_key).aio as client:
            print(f"Testing model: {model}")
            print("Sending test request...", flush=True)

            response = await asyncio.wait_for(
                client.interactions.create(
                    model=model,
                    input="Reply with exactly OK",
                    store=False,
                    timeout=20,
                ),
                timeout=25,
            )

            print("SUCCESS:", response.output_text)

    except Exception as error:
        print("TEST FAILED")
        print("Error type:", type(error).__name__)
        print("Error:", str(error))

if __name__ == "__main__":
    asyncio.run(main())
