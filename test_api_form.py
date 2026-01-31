import requests
import json

url = "https://gemini-api-wrapper--dukgiqn.replit.app/gemini"
image_path = "/home/ubuntu/upload/search_images/S5yAxomVUXIX.jpg"

files = {
    'image': ('cat.jpg', open(image_path, 'rb'), 'image/jpeg')
}
data = {
    'pro': 'Décris cette image précisément.',
    'uid': 'test-manus-form'
}

print(f"Envoi de la requête POST (form-data) à {url}...")
try:
    response = requests.post(url, files=files, data=data)
    print(f"Statut Code: {response.status_code}")
    print("Réponse brute:")
    print(response.text)
    
    try:
        data_json = response.json()
        print("\nRéponse JSON parsée:")
        print(json.dumps(data_json, indent=2, ensure_ascii=False))
    except:
        pass
        
except Exception as e:
    print(f"Erreur lors de la requête : {e}")
