import sys
import os
import base64
import asyncio
import json

# Ajouter le chemin pour importer main.py
sys.path.append('/home/ubuntu/gemini-api-wrapper')
from main import process_gemini_request

async def test_post_image():
    # Lire l'image en base64
    with open('/home/ubuntu/gemini-api-wrapper/test_image_b64.txt', 'r') as f:
        image_b64 = f.read()
    
    # Préparer les données
    image_data = f"data:image/jpeg;base64,{image_b64}"
    prompt = "Que vois-tu sur cette image ? Décris précisément l'animal et son environnement."
    
    print(f"Envoi de la requête POST avec une image ({len(image_b64)} octets)...")
    
    # Appeler directement la fonction de traitement
    result = await process_gemini_request(prompt, image=image_data, uid="test_user_001")
    
    # Afficher le résultat
    print("\n--- RÉPONSE DE L'API GEMINI ---")
    print(json.dumps(result, indent=4, ensure_ascii=False))
    print("-------------------------------\n")
    
    if result['status'] == 'success':
        answer = result['answer'].lower()
        # Vérifier si la réponse contient des mots clés liés à l'image (un chien noir/chiot)
        keywords = ['chien', 'chiot', 'noir', 'animal', 'regard', 'bois']
        matches = [word for word in keywords if word in answer]
        
        print(f"Mots-clés trouvés dans la réponse : {matches}")
        if len(matches) >= 2:
            print("VÉRIFICATION RÉUSSIE : La réponse correspond à l'image envoyée.")
        else:
            print("VÉRIFICATION INCERTAINE : La réponse ne semble pas décrire précisément l'image.")
    else:
        print(f"ERREUR : {result.get('message', 'Erreur inconnue')}")

if __name__ == "__main__":
    asyncio.run(test_post_image())
