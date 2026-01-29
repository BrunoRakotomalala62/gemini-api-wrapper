import asyncio
import time
from main import gemini_endpoint

async def run_tests():
    print("--- Test 1: Prompt Textuel ---")
    start = time.time()
    result_text = await gemini_endpoint(prompt="Bonjour, qui es-tu ? Réponds brièvement.")
    end = time.time()
    print(f"Résultat: {result_text}")
    print(f"Temps total: {round(end - start, 2)}s\n")

    print("--- Test 2: Reconnaissance d'Image via URL ---")
    image_url = "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"
    start = time.time()
    result_image = await gemini_endpoint(prompt="Décris brièvement cette image.", image=image_url)
    end = time.time()
    print(f"Résultat: {result_image}")
    print(f"Temps total: {round(end - start, 2)}s\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
