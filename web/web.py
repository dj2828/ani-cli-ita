from flask import Flask, Blueprint, render_template, request, redirect, url_for
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.dont_write_bytecode = True
try:
    from moduli.ani_cli import main as ani  # come modulo
except ImportError:
    import main as ani  # standalone

BASE_URL = "https://www.animeworld.ac"
IS_STANDALONE = __name__ == '__main__'
T = '' if IS_STANDALONE else 'ani/'

def getEpisodi(anime_url):
    anime_url = f"{BASE_URL}/play/{anime_url}"
    ep = ani.cerca_ep(anime_url)
    return ep

def getPreferiti():
    prefe = ani.carica_preferiti()
    if not prefe:
        prefe = {}
    for anime_title, url in prefe.items():
        prefe[anime_title] = url.split('/')[-1]
    return prefe

blueprint = Blueprint('ani', __name__, url_prefix='/ani')

@blueprint.route('/')
def index():
    if q := request.args.get("q"):
        risultati = ani.cerca_nome(q) if q else {}
        return render_template(f'{T}index.html', anime_prefe=getPreferiti(), risultati=risultati, q=q)
    return render_template(f'{T}index.html', anime_prefe=getPreferiti())

@blueprint.get('/img/<anime>')
def img_anime(anime):
    anime_id = anime.split('.')[-1]
    return redirect(f"https://img.animeworld.ac/locandine/{anime_id}.jpg")

@blueprint.route('/play/<path:ep_url>')
def play(ep_url):
    episodi = getEpisodi(ep_url)
    if '/' not in ep_url:
        first_url = list(episodi.values())[0]
        return redirect(url_for('ani.play', ep_url=ep_url) + "/" + first_url.split('/')[-1] + "?ep=1")
    ep = request.args.get("ep")
    url = ani.get_real_video_url(ep_url)
    return render_template(f'{T}play.html', video_url=url, ep=episodi, current_ep=ep)

@blueprint.post('/prefe')
def prefe():
    url = request.form.get('url')
    nome = request.form.get('nome')
    
    pref = ani.carica_preferiti()
    if not pref:
        pref = {}

    if nome in pref:
        del pref[nome]
    else:
        pref[nome] = BASE_URL + url

    with open('preferiti.txt', 'w', encoding='utf-8') as f:
        for title, link in pref.items():
            f.write(f"{title} - {link}\n")

    return "ok", 200


if __name__ == '__main__':
    # se eseguito standalone lo importa come se fosse un bluprint (quindi è tutto un bluprint)
    app = Flask(__name__)
    app.secret_key = "S4Ss0"
    app.register_blueprint(blueprint, url_prefix='/')
    app.run(debug=True, host='0.0.0.0', port=8080)