#!/usr/bin/env python3
from flask import Flask, Blueprint, render_template, request, redirect, jsonify
from urllib.parse import unquote
import os, sys, importlib.util, json, requests
sys.dont_write_bytecode = True

# import main (chiedi a claude)
_main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
if not os.path.exists(_main_path):  # standalone, main.py è una cartella su
    _main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
_spec = importlib.util.spec_from_file_location("ani_main", _main_path)
ani = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ani)


BASE_URL = "https://www.animeworld.ac"
IS_STANDALONE = __name__ == '__main__'
T = '' if IS_STANDALONE else 'ani/'

def getEpisodi(anime_url):
    anime_url = f"{BASE_URL}/play/{anime_url}"
    ep = ani.cerca_ep(anime_url)
    return ep

def getPreferiti():
    if not IS_STANDALONE:
        raw = request.cookies.get("prefe")
        prefe = json.loads(unquote(raw)) if raw else {}
    else:
        prefe = ani.carica_preferiti()
        if not prefe:
            prefe = {}
    for anime_title, data in prefe.items():
        try:
            prefe[anime_title] = {"url": data["url"].split('/')[-1], "img": data["img"]}
        except:
            # per quelli vecchi senza img (prima di img diretta da aniworld)
            prefe[anime_title] = data.split('/')[-1]
    return prefe

def getHistoryWatched():
    raw = request.cookies.get("history")
    history = json.loads(unquote(raw)) if raw else None
    return history

web = Blueprint('ani', __name__)

@web.route('/')
def index():
    if q := request.args.get("q"):
        risultati = ani.cerca_nome(q) if q else {}
        risultati = {
            k: {**v, 'url': v['url'].split('/')[-1]} 
            for k, v in risultati.items()
        }
        return render_template(f'{T}index.html', anime_prefe=getPreferiti(), risultati=risultati, q=q, vercel=not IS_STANDALONE)
    return render_template(f'{T}index.html', anime_prefe=getPreferiti(), vercel=not IS_STANDALONE, continua=getHistoryWatched())

@web.route('/play/<path:anime_url>')
def play(anime_url):
    ep = request.args.get("ep", 1)
    episodi = getEpisodi(anime_url)
    ani_id = ani.get_mal_id_from_url(f"{BASE_URL}/play/{anime_url}")
    
    return render_template(f'{T}play.html', ep=episodi, current_ep=ep, ani_id=ani_id)

@web.route('/realUrl/<path:ep_url>')
def realUrl(ep_url):
    real_url = ani.get_real_video_url(ep_url)
    return jsonify({"url": real_url})

@web.post('/prefe')
def prefe():
    url = request.form.get('url')
    nome = request.form.get('nome')
    img = request.form.get('img')
    
    pref = ani.carica_preferiti()
    if not pref:
        pref = {}

    if nome in pref:
        del pref[nome]
    else:
        pref[nome] = {"url": BASE_URL + url, "img": img}

    with open('preferiti.json', 'w', encoding='utf-8') as f:
        json.dump(pref, f, indent=4)

    return "ok", 200


if __name__ == '__main__':
    # se eseguito standalone lo importa come se fosse un bluprint (quindi è tutto un bluprint)
    app = Flask(__name__)
    app.secret_key = "S4Ss0"
    app.register_blueprint(web)
    app.run(debug=True, host='0.0.0.0', port=8080)