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

def getVolumi(manga_url):
    manga_url = f"{BASE_URL}/manga/{manga_url}"
    vol = ani.cerca_vol(manga_url)
    return vol

def getPreferiti():
    raw = request.cookies.get("prefe manga")
    prefe = json.loads(unquote(raw)) if raw else {}
    for anime_title, data in prefe.items():
        prefe[anime_title] = {"url": data["url"].split('/')[-1], "img": data["img"]}
    return prefe

def getHistoryWatched():
    raw = request.cookies.get("mangaHistory")
    history = json.loads(unquote(raw)) if raw else None
    return history

web = Blueprint('manga', __name__)

@web.route('/')
def index():
    if q := request.args.get("q"):
        risultati = ani.cerca_nome(q) if q else {}
        return render_template(f'{T}index.html', anime_prefe=getPreferiti(), risultati=risultati, q=q)
    return render_template(f'{T}index.html', anime_prefe=getPreferiti(), continua=getHistoryWatched())

@web.route('/read/<path:manga_url>')
def read(manga_url):
    title = request.args.get("title")
    volumi = getVolumi(manga_url)
    cap = request.args.get("cap")
    if not cap:
        cap = 1
    # ep = request.args.get("ep", 1)
    # episodi = getEpisodi(manga_url)
    # ani_id = ani.get_mal_id_from_url(f"{BASE_URL}/play/{manga_url}")

    return render_template(f'{T}read.html', volumi=volumi, title=title, cap=cap)

@web.route('/getUrlPagina/')
def getUrlPagina():
    cap_url = request.args.get('url')
    real_url = ani.getUrlPagina(cap_url)
    return real_url

if __name__ == '__main__':
    # se eseguito standalone lo importa come se fosse un bluprint (quindi è tutto un bluprint)
    app = Flask(__name__)
    app.secret_key = "S4Ss0"
    app.register_blueprint(web)
    app.run(debug=True, host='0.0.0.0', port=8080)