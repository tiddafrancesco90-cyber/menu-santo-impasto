#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera data.js leggendo la tabella 'Piatti' su Airtable.
Gira dentro la GitHub Action. Usa solo la stdlib.

Variabili d'ambiente richieste:
  AIRTABLE_TOKEN    (dai secrets del repo)
  AIRTABLE_BASE_ID  (impostata nel workflow)
"""

import os, sys, json
import urllib.request, urllib.parse, urllib.error

TABLE = "Piatti"

# --- dati statici del locale (non stanno su Airtable) ---
RESTAURANT = {
    "name": "Santo Impasto",
    "kicker": "Trattoria · Pizzeria · Toscana",
    "subtitle": "Pizzeria & Cucina",
    "motto": "«Ogni pizza è un piccolo miracolo.\nLa lievitazione fa il resto.»",
    "coperto": 2
}

ALLERGENS = {
    "glutine":{"code":"Gl","name":"Glutine"}, "crostacei":{"code":"Cr","name":"Crostacei"},
    "uova":{"code":"Uo","name":"Uova"}, "pesce":{"code":"Pe","name":"Pesce"},
    "arachidi":{"code":"Ar","name":"Arachidi"}, "soia":{"code":"So","name":"Soia"},
    "latte":{"code":"La","name":"Latte"}, "frutta":{"code":"Fg","name":"Frutta a guscio"},
    "sedano":{"code":"Se","name":"Sedano"}, "senape":{"code":"Sn","name":"Senape"},
    "sesamo":{"code":"Ss","name":"Sesamo"}, "solfiti":{"code":"Sl","name":"Solfiti"},
    "lupini":{"code":"Lu","name":"Lupini"}, "molluschi":{"code":"Mo","name":"Molluschi"}
}
ORDER = ["glutine","crostacei","uova","pesce","arachidi","soia","latte","frutta",
         "sedano","senape","sesamo","solfiti","lupini","molluschi"]

# etichetta Airtable -> chiave interna
LABEL2KEY = {
    "Glutine":"glutine","Crostacei":"crostacei","Uova":"uova","Pesce":"pesce",
    "Arachidi":"arachidi","Soia":"soia","Latte":"latte","Frutta a guscio":"frutta",
    "Sedano":"sedano","Senape":"senape","Sesamo":"sesamo","Solfiti":"solfiti",
    "Lupini":"lupini","Molluschi":"molluschi"
}

# ordine + id + sottotitolo delle categorie (le categorie sono stabili)
CATEGORY_CONFIG = [
    ("Antipasti & Sfizi","antipasti","gli inizi che contano"),
    ("Fritti","fritti","il peccato è servito"),
    ("Le Pizze — Classiche","classiche","lievitazione 48h"),
    ("Le Pizze — Gourmet","gourmet","quelle che si danno un tono"),
    ("Calzoni","calzoni","la pizza che si ripiega su sé stessa"),
    ("Primi","primi","fatti come si deve"),
    ("Secondi","secondi","roba seria"),
    ("Contorni","contorni","mai da soli"),
    ("Dolci","dolci","fatti in casa"),
    ("Bevande","bevande","per accompagnare"),
]


def fetch_records(token, base_id):
    """Scarica tutti i record della tabella Piatti (con paginazione)."""
    records = []
    offset = None
    while True:
        url = "https://api.airtable.com/v0/%s/%s?pageSize=100" % (base_id, TABLE)
        if offset:
            url += "&offset=" + urllib.parse.quote(offset)
        r = urllib.request.Request(url)
        r.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(r, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


def build_data(records):
    """Trasforma i record Airtable nella struttura MENU_DATA."""
    # solo visibili
    rows = []
    for rec in records:
        f = rec.get("fields", {})
        if not f.get("Visibile"):
            continue
        rows.append(f)
    # ordina per campo Ordine (mancante -> in fondo)
    rows.sort(key=lambda f: (f.get("Ordine") is None, f.get("Ordine", 1e9)))

    sections = []
    for label, sec_id, subtitle in CATEGORY_CONFIG:
        items = []
        for f in rows:
            if (f.get("Categoria") or "").strip() != label:
                continue
            keys = []
            for a in (f.get("Allergeni") or []):
                k = LABEL2KEY.get(a)
                if k:
                    keys.append(k)
            item = {
                "name": (f.get("Nome") or "").strip(),
                "desc": (f.get("Descrizione") or "").strip(),
                "price": (f.get("Prezzo") or "").strip(),
                "keys": keys
            }
            if f.get("Surgelato"):
                item["frozen"] = True
            items.append(item)
        if items:
            sections.append({"id":sec_id,"title":label,"subtitle":subtitle,"items":items})

    return {
        "restaurant": RESTAURANT,
        "allergens": ALLERGENS,
        "order": ORDER,
        "sections": sections
    }


def render_js(data):
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return ("/* GENERATO AUTOMATICAMENTE DA build_site.py — non modificare a mano.\n"
            "   La fonte dei dati è Airtable (tabella 'Piatti'). */\n"
            "window.MENU_DATA = " + payload + ";\n")


def main():
    token = os.environ.get("AIRTABLE_TOKEN")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    if not token or not base_id:
        print("Mancano AIRTABLE_TOKEN o AIRTABLE_BASE_ID"); sys.exit(1)
    recs = fetch_records(token, base_id)
    data = build_data(recs)
    n = sum(len(s["items"]) for s in data["sections"])
    js = render_js(data)
    with open("data.js","w",encoding="utf-8") as fh:
        fh.write(js)
    print("data.js rigenerato: %d sezioni, %d piatti visibili." % (len(data["sections"]), n))


if __name__ == "__main__":
    main()
