import requests

cep = "04538133"

url = f"https://brasilapi.com.br/api/cep/v2/{cep}"

response = requests.get(url)

if response.status_code == 200:
    print(response.json())
else:
    print("Erro:", response.status_code)