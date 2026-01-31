import sys
import os
import asyncio
import json

sys.path.append('/home/ubuntu/gemini-api-wrapper')
from main import process_gemini_request

async def test_url_image():
    # URL d'une image publique (un chiot noir sur du bois, similaire à notre test précédent)
    image_url = "https://images.unsplash.com/photo-1552053831-71594a27632d?auto=format&fit=crop&w=400&q=80"
    prompt = "Que vois-tu sur cette image ? Sois très précis sur l'animal."
    
    print(f"Envoi de la requête avec URL d'image...")
    
    result = await process_gemini_request(prompt, image=image_url, uid="test_url_user")
    
    print("\n--- RÉPONSE DE L'API GEMINI (VIA URL) ---")
    print(json.dumps(result, indent=4, ensure_ascii=False))
    print("------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(test_url_image())
