import requests
import certifi

URL = "https://www.brvm.org/views/ajax"

params = {
    "view_name": "sgi",
    "view_display_id": "page_1",
    "view_args": "",
    "view_path": "/fr/intervenants/sgi/tous",
    "pager_element": 0,
}

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

def fetch_sgi():
    r = requests.get(
        URL,
        params=params,
        headers=headers,
        timeout=30,
        verify=certifi.where()
    )
    
    r.raise_for_status()
    return r.json()

print(fetch_sgi())