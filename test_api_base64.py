import requests
import json
import base64

url = "https://gemini-api-wrapper--dukgiqn.replit.app/gemini"
image_path = "/home/ubuntu/upload/search_images/S5yAxomVUXIX.jpg"

with open(image_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

payload = {
    "pro": "Décris cette image précisément.",
    "image": encoded_string,
    "uid": "test-manus-base64"
}
headers = {
    "Content-Type": "application/json"
}

print(f"Envoi de la requête POST (base64) à {url}...")
try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Statut Code: {response.status_code}")
    print("Réponse brute:")
    print(response.text)
    
    try:
        data = response.json()
        print("\nRéponse JSON parsée:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        pass
        
except Exception as e:
    print(f"Erreur lors de la requête : {e}")
