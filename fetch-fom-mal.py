import requests
import time
import main

def get_mal_anime_list(username):
    base_url = f"https://myanimelist.net/animelist/{username}/load.json"
    offset = 0
    all_anime = []
    
    print(f"--- Recupero lista per l'utente: {username} ---")

    while True:
        # MAL carica la lista in blocchi (solitamente 300 per volta)
        params = {
            'offset': offset,
            'status': 7 # 7 indica "Tutti gli anime"
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code != 200:
            print(f"Errore: Impossibile accedere alla lista. Status code: {response.status_code}")
            break
            
        data = response.json()
        
        if not data: # Se la lista è vuota, abbiamo finito
            break
            
        all_anime.extend(data)
        print(f"Scaricati {len(all_anime)} anime...")
        
        # Incrementa l'offset per la pagina successiva
        offset += len(data)
        
        # Piccola pausa per non sovraccaricare il server
        time.sleep(1)

    return all_anime

def scegli(anime_list):
    print("Anime disponibili per il download:")
    for i, anime in enumerate(anime_list):
        # Supporta sia elementi dict (dalla API MAL) sia stringhe (titoli già estratti)
        if isinstance(anime, dict):
            title = anime.get('anime_title_eng') or anime.get('anime_title') or str(anime)
        else:
            title = str(anime)
        print(f"{i + 1}. {title}")
    
    scelta_input = input("Seleziona i numeri degli anime da scaricare (es. 1,2,43): ")
    # Supporta selezione multipla separata da virgole; ignora valori non validi
    selected_indices = []
    for part in scelta_input.split(','):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(anime_list):
                selected_indices.append(idx)
            else:
                print(f"Indice fuori range ignorato: {part}")
        else:
            print(f"Valore non valido ignorato: {part}")

    if not selected_indices:
        print("Nessuna scelta valida.")
        return []

    # Rimuove duplicati mantenendo l'ordine
    seen = set()
    selected = []
    for idx in selected_indices:
        if idx not in seen:
            seen.add(idx)
            selected.append(anime_list[idx])

    return selected

if __name__ == "__main__":
    user = "dj_2828"
    anime_list = get_mal_anime_list(user)
    anime_fatti = []
    anime_list_giusta = []

    if anime_list:
        for anime in anime_list:
            title = anime.get('anime_title_eng')
            if not title:
                title = anime.get('anime_title')
            status = anime.get('status')
            airing = anime.get('anime_airing_status')
            if status != 6 or airing == 3: # 6 indica "on plan to watch", 2 indica "airing"
                continue
            # print(f"Titolo: {title}, Stato: {status}, Airing Status: {airing}")
            anime_list_giusta.append(title)

        anime_list = scegli(anime_list_giusta)

        for title in anime_list:
            # integrazione con main.py
            name_list = main.cerca_nome(title)
            name_list_ok = {}
            for i, (name, url) in enumerate(name_list.items()):
                if i < 5:
                    print(name, url)
                    name_list_ok[name] = url

            print(name_list_ok)
            
            # Selezione migliorata:
            # Priorità: exact ITA > exact > partial ITA > partial > any ITA > primo
            selected_name = None

            # exact ITA (es. "Titolo (ITA)")
            for name in name_list_ok:
                if "(ITA)" in name and name.lower().replace(" (ita)", "") == title.lower():
                    selected_name = name
                    break

            # exact
            if not selected_name:
                for name in name_list_ok:
                    if name.lower() == title.lower():
                        selected_name = name
                        break

            # partial ITA (il titolo contenuto nel nome ITA)
            if not selected_name:
                for name in name_list_ok:
                    if "(ITA)" in name and title.lower() in name.lower():
                        selected_name = name
                        break

            # partial (titolo contenuto nel nome)
            if not selected_name:
                for name in name_list_ok:
                    if title.lower() in name.lower():
                        selected_name = name
                        break

            # qualsiasi ITA
            if not selected_name:
                for name in name_list_ok:
                    if "(ITA)" in name:
                        selected_name = name
                        break

            # fallback: primo elemento disponibile
            if not selected_name:
                selected_name = next(iter(name_list_ok)) if name_list_ok else None
            
            print(f"\nScelto: {selected_name}")
            url = "https://www.animeworld.ac" + name_list_ok[selected_name]
            print(f"URL: {url}")

            episodi = main.cerca_ep(url)

            main.url_jelly(episodi, url, anime_scelto_=selected_name)

            anime_fatti.append(selected_name)

    print("\nAnime scaricati:")
    for anime in anime_fatti:
        print(f"- {anime}")
    
    input("\nPremi Invio per uscire...")