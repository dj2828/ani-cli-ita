#!/usr/bin/env python3
from flask import Flask, Blueprint, render_template, request, redirect, jsonify
from urllib.parse import unquote
import os, sys, importlib.util, json, requests
sys.dont_write_bytecode = True

# import main (chiedi a claude)
_main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils.py")
if not os.path.exists(_main_path):  # standalone, utils.py è una cartella su
    _main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".", "utils.py")
_spec = importlib.util.spec_from_file_location("ani_utils", _main_path)
ani = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ani)

BASE_URL = "https://www.mangaworld.mx"
IS_STANDALONE = __name__ == '__main__'
T = '' if IS_STANDALONE else 'manga/'

if not IS_STANDALONE:
    import moduli.ani_api as ani_api

def getData(manga_url):
    manga_url = f"{BASE_URL}/manga/{manga_url}"
    vol, title, img = ani.cerca_vol(manga_url)
    return vol, title, img

def getPreferiti():
    if not IS_STANDALONE:
        prefe = ani_api.getPreferiti(True)
    else:
        raw = request.cookies.get("prefe manga")
        prefe = json.loads(unquote(raw)) if raw else {}
    for anime_title, data in prefe.items():
        prefe[anime_title] = {"url": data["url"].split('/')[-1], "img": data["img"]}
    return prefe

def getHistoryWatched():
    if not IS_STANDALONE:
        return ani_api.getHistoryWatched(True)
    else:
        raw = request.cookies.get("manga-history")
        history = json.loads(unquote(raw)) if raw else None
        return history

web = Blueprint('manga', __name__)

@web.route('/')
def index():
    if q := request.args.get("q"):
        risultati = ani.cerca_nome(q) if q else {}
        return render_template(f'{T}index.html', anime_prefe=getPreferiti(), risultati=risultati, q=q, VERCEL=not IS_STANDALONE)
    return render_template(f'{T}index.html', anime_prefe=getPreferiti(), VERCEL=not IS_STANDALONE, continua=getHistoryWatched())

@web.route('/read/<path:manga_url>')
def read(manga_url):
    volumi, title, img = getData(manga_url)
    cap = request.args.get("cap")
    if not cap:
        cap = 1

    return render_template(f'{T}read.html', volumi=volumi, title=title, img=img, cap=cap, VERCEL=not IS_STANDALONE)

@web.route('/getUrlPagina/')
def getUrlPagina():
    cap_url = request.args.get('url')
    real_url = ani.getUrlPagina(cap_url)
    return real_url

@web.post('/prefe')
def prefe(): # solo per vercel
    data = request.get_json()
    url = data.get('url')
    nome = data.get('nome')
    img = data.get('img')

    pref = getPreferiti()

    if nome in pref:
        del pref[nome]
    else:
        pref[nome] = {"url": url, "img": img}

    ani_api.salvaPreferiti(pref, True)
    return "ok", 200

if __name__ == '__main__':
    # se eseguito standalone lo importa come se fosse un bluprint (quindi è tutto un bluprint)
    app = Flask(__name__)
    app.secret_key = "S4Ss0"
    app.register_blueprint(web)
    app.run(debug=True, host='0.0.0.0', port=8080)