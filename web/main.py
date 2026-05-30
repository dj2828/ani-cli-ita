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
    return render_template('index.html', anime_prefe=getPreferiti())

@app.get('/img/<anime>') # uso lapi di anilist che quella di mal è lenta
def img_anime(anime):
    import re
    # "Jujutsu Kaisen (ITA)" → "Jujutsu Kaisen"
    anime = re.sub(r'\(.*?\)', '', anime).strip()
    query = """
        query ($titolo: String) {
            Media(search: $titolo, type: ANIME) {
                coverImage {
                    large
                }
            }
        }
    """
    response = requests.post(
        'https://graphql.anilist.co',
        json={ 'query': query, 'variables': { 'titolo': anime } }
    )

    data = response.json()

    if not data.get('data') or not data['data'].get('Media'):
        print(f"[img_anime] Anime non trovato: '{anime}'")
        return "Not Found", 404

    image_url = data['data']['Media']['coverImage']['large']
    return redirect(image_url)

@app.route('/play/<path:ep_url>')
def carica_ep(ep_url):
    if '/' not in ep_url:
        # non ha l'episodio quindi fallback al primo episodio
        return redirect(list(getEpisodi(ep_url).values())[0] + "?id=1")
    id = request.args.get("id")
    url = ani.get_real_video_url(ep_url)
    return render_template('play.html', video_url=f"/play/proxy?url={url}", ep=getEpisodi(ep_url), current_id=id)

@app.route("/play/proxy")
def proxy():
    url = request.args.get("url")
    headers = {}
    
    # Passa il Range header se presente (fondamentale per lo streaming video)
    if "Range" in request.headers:
        headers["Range"] = request.headers["Range"]
    
    r = requests.get(url, stream=True, verify=False, headers=headers)
    
    return Response(
        stream_with_context(r.iter_content(chunk_size=1024*1024)),
        status=r.status_code,  # 206 Partial Content
        content_type=r.headers.get("Content-Type", "video/mp4"),
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": r.headers.get("Content-Range", ""),
            "Content-Length": r.headers.get("Content-Length", ""),
        }
    )

@app.route('/cerca')
def cerca():
    q = request.args.get("q")
    risultati = ani.cerca_nome(q) if q else {}
    return render_template('index.html', anime_prefe=getPreferiti(), risultati=risultati)


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