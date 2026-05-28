import requests
from bs4 import BeautifulSoup
import subprocess
import os
import re
import json
from time import sleep
from InquirerPy import prompt
from InquirerPy.validator import EmptyInputValidator
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from tqdm import tqdm
import zipfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- VARIABILI GLOBALI ---
anime_scelto = ""
url_scelto = ""
ep_attuale = 0
max_ep = 0
stop_download = False
BASE_URL = "https://www.animeworld.ac/"

# --- CONFIGURAZIONE DATABASE ---
DB_FILE = "db.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- SSL FIX ---
import urllib3
# Disabilita il warning "InsecureRequestWarning"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Patcha requests.Session.request per aggiungere verify=False se non presente
_original_session_request = requests.Session.request
def _session_request_no_verify(self, method, url, *args, **kwargs):
    if 'verify' not in kwargs: kwargs['verify'] = False
    return _original_session_request(self, method, url, *args, **kwargs)
requests.Session.request = _session_request_no_verify

# --- UTILS ---
def path_giusto(titolo):
    # Rimuove caratteri illegali per le cartelle
    titolo = titolo.replace(":", " -")
    titolo = "".join(c for c in titolo if c.isalnum() or c in " .-_()[]")
    return titolo.strip()

def parse_metadata_anime(titolo_originale):
    """
    Estrae Nome, Stagione, Lingua e ani_id.
    Return: (serie_name, season, lang, ani_id)
    """
    # 1. Rileva la lingua
    lang = "ITA" if "(ITA)" in titolo_originale else "SUB"
    
    # 2. Logica esistente per la stagione
    season = 1

    match_season = re.search(r"(?:Season\s+(\d+)|(\d+)(?:st|nd|rd|th)?\s+Season)", titolo_originale, re.IGNORECASE)
    
    if match_season:
        season = int(match_season.group(1) or match_season.group(2))
    else:
        match_num = re.search(r"\s(\d+)$", titolo_originale)
        if match_num:
            season = int(match_num.group(1))
    
    data = get_info(titolo_originale)

    serie_name = data.get("title_english")
    if not serie_name: serie_name = data.get("title")
    ani_id = data.get("mal_id")
    airing = data.get("airing")
    
    return serie_name, season, lang, ani_id, airing

def get_info(nome):
    api = "https://api.jikan.moe/v4/anime/"
    response = requests.get(api+"?limit=1&q="+nome)
    return response.json().get("data")[0]

def get_airing(id):
    api = f"https://api.jikan.moe/v4/anime/{id}"
    response = requests.get(api)
    return response.json().get("data").get("airing")

# --- SCRAPING ---
def cerca_nome(query):
    url = f"{BASE_URL}search?keyword={query}"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Controllo se è presente il div di errore/alert
        if soup.find("div", class_="alert alert-danger"):
            print("[!] ANIME NON TROVATO")
            input("Premi INVIO per riprovare con un altro nome")
            return False

        # 2. Se non c'è l'alert, procedo con il parsing dei titoli
        titoli = soup.find_all("a", class_="name")
        fatto = {}
        for titolo in titoli:
            fatto[titolo.text.strip()] = titolo["href"]

        return fatto if fatto else False
    return False

def cerca_ep(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        # Naviga la struttura in modo più robusto
        server = soup.find("div", class_="server active")
        episodi = {}
        if server:
            ul_list = server.find_all("ul", class_="episodes range active")
            for ul in ul_list:
                for li in ul.find_all("li"):
                    a = li.find("a")
                    if a and a.text.strip():
                        episodi[a.text.strip()] = a['href']
        return episodi
    else:
        print("Errore nella richiesta")

def get_real_video_url(url):
    global stop_download
    stop_download = False

    url_pagina_video = f"{BASE_URL}api/episode/serverPlayerAnimeWorld?id={url.split('/')[-1]}"

    response = requests.get(url_pagina_video)
    soup = BeautifulSoup(response.text, "html.parser")
    link = soup.find("video").find("source")["src"]

    return link

# --- CORE FUNCTIONS ---

def carica(url):
    def ensure_mpv():
        def down_mpv():
            API_URL = "https://api.github.com/repos/mpv-player/mpv/releases/latest"
            OUTPUT_FILE = "mpv.zip"
            print("🔍 Recupero latest release...")

            r = requests.get(API_URL)
            r.raise_for_status()
            data = r.json()

            assets = data.get("assets", [])

            # Cerca il file giusto (Windows x64 msvc)
            download_url = None
            for asset in assets:
                name = asset["name"]
                if "x86_64-pc-windows-msvc" in name:
                    download_url = asset["browser_download_url"]
                    print(f"✅ Trovato: {name}")
                    break

            if not download_url:
                raise Exception("❌ File Windows x64 non trovato!")

            print("⬇️ Download in corso...")

            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(OUTPUT_FILE, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            print(f"✅ Scaricato: {OUTPUT_FILE}")

        # Prova mpv nel PATH
        try:
            subprocess.Popen(["mpv", "--version"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
            return "mpv"
        except FileNotFoundError:
            pass

        # Prova mpv locale
        local_path = os.path.join("mpv", "mpv.exe")
        if os.path.exists(local_path):
            return local_path

        # Scarica mpv
        print("Download di mpv in corso...")
        down_mpv()

        os.makedirs("mpv", exist_ok=True)

        with zipfile.ZipFile("mpv.zip", "r") as zip_ref:
            zip_ref.extractall("mpv")

        os.remove("mpv.zip")

        # Cerca mpv.exe dentro la cartella estratta
        for root, _, files in os.walk("mpv"):
            if "mpv.exe" in files:
                return os.path.join(root, "mpv.exe")

        raise FileNotFoundError("mpv.exe non trovato dopo l'estrazione")

    url = get_real_video_url(url)

    mpv_path = ensure_mpv()

    proc = subprocess.Popen(
        [mpv_path, "--save-position-on-quit", url]
    )

    sleep(2)
    proc.wait()

def url_jelly(episodi_dict, anime_url, anime_scelto_=False):
    def chiedi_info_a_utente(guess_serie, ani_id, guess_season, guess_status):
        guess_status_str = "In Corso" if guess_status else "Concluso"
        print("\nDati rilevati:")
        print(f"Serie: {guess_serie}" + (" - ATTENZIONE - se vuoi che finiscano nella stessa cartella scrivi lo stesso nome di serie della cartella gia presente." if guess_season != 1 else ""))
        print(f"MAL ID (https://myanimelist.net/anime/{ani_id}): {ani_id}")
        print(f"Stagione: {guess_season}")
        print(f"Stato: {guess_status_str}")

        conferma = prompt([
            {
                "type": "confirm",
                "name": "ok",
                "message": "Le informazioni sono corrette?",
                "default": True
            }
        ])["ok"]

        # 3. Se NON corrette → modifica
        if not conferma:
            q_meta = [
                {
                    "type": "input",
                    "message": "Nome Serie (Cartella Principale):",
                    "name": "serie",
                    "default": guess_serie
                },
                {
                    "type": "input",
                    "message": "Mal id (https://myanimelist.net):",
                    "name": "mal_id",
                    "default": str(ani_id)
                },
                {
                    "type": "input",
                    "message": "Numero Stagione:",
                    "name": "season",
                    "default": str(guess_season),
                    "validate": lambda x: x.isdigit(),
                    "filter": lambda x: int(x)
                },
                {
                    "type": "list",
                    "message": "Stato Anime:",
                    "name": "status",
                    "choices": ["In Corso", "Concluso"],
                    "default": guess_status_str
                }
            ]

            meta = prompt(q_meta)

            serie_name = meta["serie"]
            ani_id = meta["mal_id"]
            season = meta["season"]
            status = True if meta["status"] == "In Corso" else False

        else:
            # usa i valori automatici
            serie_name = guess_serie
            season = guess_season
            status = guess_status

        return serie_name, season, status, ani_id
    """
    Gestisce il salvataggio strutturato per Jellyfin e aggiorna il DB locale.
    """
    db = load_db()
    titolo_completo = anime_scelto_ if anime_scelto_ else anime_scelto
    titolo_completo = path_giusto(titolo_completo)

    # 1. Indovina i metadati
    guess_serie, guess_season, guess_lang, ani_id, airing = parse_metadata_anime(titolo_completo)
    print(f"\nConfigurazione salvataggio per: {titolo_completo}")

    if guess_lang == "ITA":
        guess_serie = f"{guess_serie} (ITA)"

    # 2. Chiedi conferma all'utente (InquirerPy)
    serie, season, airing, ani_id = chiedi_info_a_utente(guess_serie, ani_id, guess_season, airing)

    serie_path = path_giusto(serie)
    season_path = f"Season {season:02d}"
    full_path = os.path.join("down", serie_path, season_path)

    os.makedirs(full_path, exist_ok=True)

    # 3. Salva nel DB
    db_key = f"{serie_path}_S{season}"
    db[db_key] = {
        "serie_name": serie,
        "ani_id": ani_id,
        "season": season,
        "url": anime_url,
        "airing": airing,
        "folder": full_path,
        "last_ep_downloaded": []
    }

    # 4. Scarica i file .strm
    print(f"\nSalvataggio collegamenti in: {full_path}")
    progress = tqdm(total=len(episodi_dict), desc="Creazione .strm", unit="ep")
    
    nuovi_ep = []
    
    for ep_num, link in episodi_dict.items():
        filename = f"E{ep_num}.strm" if ep_num.isdigit() else f"{ep_num}.strm"
        filepath = os.path.join(full_path, filename)
        
        # Evita di rifare richieste se il file esiste
        if not os.path.exists(filepath):
            real_url = get_real_video_url(BASE_URL + link)
            if real_url:
                with open(filepath, "w") as f:
                    f.write(real_url)
                nuovi_ep.append(ep_num)
        
        progress.update(1)
    
    progress.close()
    
    # Aggiorna lista episodi nel db
    # Uniamo quelli vecchi con quelli appena scaricati per non perdere lo storico
    existing_eps = set(db[db_key].get("last_ep_downloaded", []))
    existing_eps.update(nuovi_ep)
    db[db_key]["last_ep_downloaded"] = list(existing_eps)
    
    save_db(db)
    print("✅ Salvataggio completato e Database aggiornato.")
    sleep(1)

def aggiorna_libreria():
    """
    Scansiona il DB locale e controlla nuovi episodi solo per le serie 'ongoing'.
    """
    db = load_db()
    ongoing_series = {k: v for k, v in db.items() if v.get("airing") == True}
    
    if not ongoing_series:
        print("Nessuna serie 'In Corso' trovata nel database.")
        sleep(2)
        return

    print(f"Controllo aggiornamenti per {len(ongoing_series)} serie...")
    
    count_new = 0
    
    for key, data in ongoing_series.items():
        print(f"Checking: {data['serie_name']} (Season {data['season']})...")
        episodi_online = cerca_ep(data['url'])

        path_dest = data['folder']
        os.makedirs(path_dest, exist_ok=True)
        
        downloaded = set(data['last_ep_downloaded'])
        
        for ep_num, link in episodi_online.items():
            # Controllo brutale: se non l'abbiamo nella lista o il file non c'è
            filename = f"E{ep_num}.strm" if ep_num.isdigit() else f"{ep_num}.strm"
            filepath = os.path.join(path_dest, filename)
            
            if ep_num not in downloaded or not os.path.exists(filepath):
                print(f" -> Nuovo episodio trovato: {ep_num}")
                real_url = get_real_video_url(BASE_URL + link)
                if real_url:
                    with open(filepath, "w") as f:
                        f.write(real_url)
                    db[key]["last_ep_downloaded"].append(ep_num)
                    count_new += 1

    # controllo se ancora ongoing
    for key in list(ongoing_series.keys()):
        value = ongoing_series[key]

        nuovo_airing = get_airing(value["ani_id"])

        if nuovo_airing:
            continue

        # Se NON è più in corso → chiedi conferma
        conferma = prompt([
            {
                "type": "confirm",
                "name": "ok",
                "message": f"'{value['serie_name']}' non è più in corso. Aggiornare?",
                "default": True
            }
        ])["ok"]

        if conferma:
            db[key]["airing"] = False
            ongoing_series.pop(key)
    
    save_db(db)
    print(f"\n✅ Aggiornamento completato. {count_new} nuovi episodi aggiunti.")
    input("Premi invio per tornare al menu...")

# --- MENU FUNCTIONS ---

def scegli_anime():
    os.system('cls' if os.name == 'nt' else 'clear')
    global anime_scelto, url_scelto
    try:
        questions = [
            {
                "type": "input",
                "message": "Cerca un anime:",
                "name": "query",
                "validate": EmptyInputValidator(),
            }
        ]
        query_result = prompt(questions)
        if not query_result: return False

        risultati = cerca_nome(query_result["query"])
        if not risultati:
            print("Nessun risultato trovato.")
            return False

        anime_choices = [Choice(value=link, name=titolo) for titolo, link in risultati.items()]
        questions = [
            {
                "type": "list",
                "message": "Seleziona un anime:",
                "choices": anime_choices,
                "name": "anime_selection",
            }
        ]
        selection_result = prompt(questions)
        if not selection_result: return False
        
        url_scelto = BASE_URL + selection_result['anime_selection']
        # Find the key (anime title) corresponding to the selected value (link)
        anime_scelto = next(key for key, value in risultati.items() if value == selection_result['anime_selection'])
        print(f"Hai scelto: {anime_scelto}")
        return True

    except KeyboardInterrupt:
        return False

def scegli_ep(next_ep=False, ricarica=False):
    global ep_attuale, max_ep
    os.system('cls' if os.name == 'nt' else 'clear')
    episodi = cerca_ep(url_scelto)
    if not episodi:
        print("Nessun episodio trovato.")
        return

    max_ep = len(episodi)
    
    if next_ep:
        ep_attuale += 1
    elif ricarica:
        pass
    else:
        ep_choices = []
        ep_choices.append(Choice(value="jelly", name=f"▶️  Aggiungi a Jellyfin"))
        ep_choices += [Choice(value=link, name=f"Episodio {i+1}: {nome}") for i, (nome, link) in enumerate(episodi.items())]
        questions = [
            {
                "type": "list",
                "message": f"Scegli un episodio di {anime_scelto}:",
                "choices": ep_choices,
                "name": "episode_selection",
                "cycle": False,
            }
        ]
        try:
            selection_result = prompt(questions)
            if not selection_result: return
            if selection_result['episode_selection'] == "jelly":
                url_jelly(episodi, url_scelto)
                return True

            # Find the index of the chosen episode
            selected_link = selection_result['episode_selection']
            ep_attuale = list(episodi.values()).index(selected_link)

        except KeyboardInterrupt:
            return

    episodio_nome = list(episodi.keys())[ep_attuale]
    url_ep_scelto = BASE_URL + episodi[episodio_nome]
    carica(url_ep_scelto)

def carica_preferiti():
    global anime_scelto, url_scelto
    if os.path.exists("preferiti.txt"):
        with open("preferiti.txt", "r") as f:
            preferiti = {}
            for line in f:
                if " - " in line:
                    nome, link = line.strip().split(" - ", 1)
                    preferiti[nome] = link
        return preferiti
    else:
        print("Nessun preferito trovato.")
        return {}

def salva_preferito():
    global anime_scelto, url_scelto
    with open("preferiti.txt", "a") as f:
        f.write(f"{anime_scelto} - {url_scelto}\n")
    print(f"Anime '{anime_scelto}' salvato nei preferiti.")

def rimuovi_preferito():
    preferiti = carica_preferiti()
    if not preferiti:
        print("Nessun preferito da rimuovere.")
        sleep(2)
        return

    try:
        pref_choices = [Choice(value=link, name=nome) for nome, link in preferiti.items()]
        questions = [
            {
                "type": "list",
                "message": "Seleziona un anime da rimuovere:",
                "choices": pref_choices,
                "name": "anime_da_rimuovere",
            }
        ]
        selection_result = prompt(questions)
        if not selection_result: return
        
        nome_da_rimuovere = next(key for key, value in preferiti.items() if value == selection_result['anime_da_rimuovere'])
        del preferiti[nome_da_rimuovere]

        with open("preferiti.txt", "w") as f:
            for nome, link in preferiti.items():
                f.write(f"{nome} - {link}\n")
        print(f"'{nome_da_rimuovere}' rimosso dai preferiti.")
        sleep(2)

    except KeyboardInterrupt:
        return

def menu_post_visione():
    global stop_download
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        preferiti = carica_preferiti()
        choices = []

        if ep_attuale < max_ep - 1:
            choices.append(Choice(value="prossimo", name=f"▶️  Prossimo episodio ({ep_attuale + 2})"))
        else:
            choices.append(Choice(value=None, name="⏹️  Non ci sono altri episodi"))

        choices.extend([
            Choice(value="scegli", name="🔢 Scegli un altro episodio"),
            Choice(value="ricarica", name="🔃 Ricarica"),
            Separator(),
        ])

        if anime_scelto not in preferiti:
            choices.append(Choice(value="salva", name="⭐ Salva anime nei preferiti"))
        
        choices.append(Choice(value="esci", name="🚪 Indietro"))

        questions = [{
            "type": "list",
            "message": "Cosa vuoi fare ora?",
            "choices": choices,
            "name": "scelta_finale"
        }]

        try:
            result = prompt(questions)
            if not result: # Handle Ctrl+C
                stop_download = True
                print("\nUscita dal programma.")
                break
            
            scelta = result['scelta_finale']

            if scelta == "prossimo":
                stop_download = True
                scegli_ep(next_ep=True)
            elif scelta == "scegli":
                stop_download = True
                scegli_ep()
            elif scelta == "ricarica":
                scegli_ep(ricarica=True)
            elif scelta == "salva":
                salva_preferito()
            elif scelta == "esci":
                stop_download = True
                print("\nUscita dal programma.")
                break
        except KeyboardInterrupt:
            stop_download = True
            print("\nUscita dal programma.")
            break

def cerca_upt(percorso_base = "./down"):
    def get_episodi_presenti(nome_path):
        file_validi = [f for f in os.listdir(f"{percorso_base}/{nome_path}") if f.lower().endswith(('.strm', '.mp4'))]
        # Salva il tipo dal primo elemento (se esiste)
        tipo_file = os.path.splitext(file_validi[0])[1].replace('.', '') if file_validi else None
        # Salva i nomi puliti
        nomi_puliti = [os.path.splitext(f)[0].replace("E", "") for f in file_validi]
        return nomi_puliti
    tutti = [nome for nome in os.listdir(percorso_base) if os.path.isdir(os.path.join(percorso_base, nome))]

    mancanti = {}
    for nome_path in tutti:
        print("Controllo:", nome_path)
        nome, url_ani = next(iter(cerca_nome(nome_path.replace(" - ", ": ")).items()))
        url_ani = BASE_URL + url_ani
        episodi = cerca_ep(url_ani)
        episodi_presenti = get_episodi_presenti(nome_path)
        for nome_ep, url in episodi.items():
            if nome_ep in episodi_presenti: continue
            else:
                if nome not in mancanti: mancanti[nome] = []  # Crea la lista per questa serie
                mancanti[nome].append((nome_ep, BASE_URL + url))
    return mancanti


def main():
    global anime_scelto, url_scelto
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("Benvenuto in Ani-CLI-ITA!")

        preferiti = carica_preferiti()

        choices = [
            Choice("cerca", "🔍 Cerca un nuovo anime"),
            Choice("aggiorna", "🔄 Aggiorna Libreria (Check Nuovi Episodi)"),
            Choice("rimuovi", "🗑️  Rimuovi un anime dai preferiti")
        ]
        
        if preferiti:
            choices.append(Separator("--- PREFERITI ---"))
            pref_choices = [Choice(value=link, name=nome) for nome, link in preferiti.items()]
            choices.extend(pref_choices)

        questions = [
            {
                "type": "list",
                "message": "Scegli un'opzione:",
                "choices": choices,
                "name": "scelta_iniziale"
            }
        ]

        try:
            result = prompt(questions)
            if not result: break # Exit on Ctrl+C
            
            scelta = result['scelta_iniziale']

            if scelta == "cerca":
                if scegli_anime():
                    if scegli_ep():
                        return
                    menu_post_visione()
            elif scelta == "rimuovi":
                rimuovi_preferito()
            elif scelta == "aggiorna":
                aggiorna_libreria()
            else: # An anime from favorites was selected
                url_scelto = scelta
                anime_scelto = next(key for key, value in preferiti.items() if value == scelta)
                print(f"Hai scelto: {anime_scelto}")
                scegli_ep()
                menu_post_visione()

        except KeyboardInterrupt:
            print("\nUscita dal programma.")
            break

if __name__ == "__main__":
    main()
    # cerca_upt()