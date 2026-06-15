from flask import Flask, render_template, Response, stream_with_context, request, redirect
import os, sys, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.dont_write_bytecode = True
import main as ani

app = Flask(__name__)
app.secret_key = "S4Ss0"

BASE_URL = "https://www.animeworld.ac"

def getEpisodi(anime_url):
    anime_url = f"{BASE_URL}/play/{anime_url}"
    ep = ani.cerca_ep(anime_url)
    return ep

def getPreferiti():
    prefe = ani.carica_preferiti()
    if not prefe:
        prefe = {}
    for anime_title, url in prefe.items():
        prefe[anime_title] = url.split('/')[-1]  # Estrai solo la parte finale dell'URL
    return prefe

@app.route('/')
def index():
    if q := request.args.get("q"):
        risultati = ani.cerca_nome(q) if q else {}
        return render_template('index.html', anime_prefe=getPreferiti(), risultati=risultati, q=q)
    return render_template('index.html', anime_prefe=getPreferiti())

@app.get('/img/<anime>')
def img_anime(anime):
    anime_id = anime.split('.')[-1]
    return redirect(f"https://img.animeworld.ac/locandine/{anime_id}.jpg")

@app.route('/play/<path:ep_url>')
def carica_ep(ep_url):
    episodi = getEpisodi(ep_url)
    if '/' not in ep_url:
        return redirect(list(episodi.values())[0] + "?ep=1")
    ep = request.args.get("ep")
    url = ani.get_real_video_url(ep_url)
    return render_template('play.html', video_url=f"{url}", ep=episodi, current_ep=ep)

@app.post('/prefe')
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
    app.run(debug=True, host='0.0.0.0', port=8080)