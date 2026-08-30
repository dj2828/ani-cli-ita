#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "https://www.mangaworld.mx/"

# --- SCRAPING ---

def cerca_nome(query):
    url = f"{BASE_URL}archive?keyword={query}"
    # input(f"[DEBUG] URL di ricerca: {url}")
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        if soup.find("div", class_="alert alert-danger"):
            print("[!] MANGA NON TROVATO")
            return False

        titoli = soup.find_all("a", class_="thumb")
        fatto = {}
        for titolo in titoli:
            fatto[titolo.get("title").strip()] = {"url": titolo["href"], "img": titolo.find("img")["src"]}

        return fatto if fatto else False
    return False

def cerca_vol(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        volumi = {}

        volumiDiv = soup.find_all("div", class_="volume-element")
        for volume in volumiDiv:
            volume_number = volume.find("p", class_="volume-name").text.replace("Volume", "").strip()
            capitoliDiv = volume.find_all("a", class_="chap")
            capitoli = {}
            for capitolo in capitoliDiv:
                capitolo_number = capitolo.find("span", class_="d-inline-block").text.replace("Capitolo", "").strip()
                capitoli[capitolo_number] = capitolo["href"]

            volumi[volume_number] = capitoli

        return volumi
    else:
        print("Errore nella richiesta")

def getUrlPagina(url_capitolo):
    response = requests.get(url_capitolo)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        immagini = [img["src"] for img in soup.find_all("img", class_="img-fluid")]
        immagine = "/".join(immagini[-1].split("/")[:-1])  # Rimuove l'ultima parte dell'URL
        return immagine
    else:
        print("Errore nella richiesta")