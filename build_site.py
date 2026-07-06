#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera data.js da Airtable.
Legge tre tabelle (le ultime due sono opzionali: se mancano, si usano
i valori di default e il sito continua a funzionare):
  - "Piatti"      : i piatti (obbligatoria)
  - "Categorie"   : sezioni + sottotitoli + visibilita' + ordine (opzionale)
  - "Testi sito"  : motto, coperto, note (opzionale)

Traduce SOLO le descrizioni dei piatti in EN/DE/ES/FR via DeepL, con cache.

Env: AIRTABLE_TOKEN, AIRTABLE_BASE_ID (obbligatorie), DEEPL_API_KEY (opzionale).
"""

import os, sys, json, re, unicodedata
import urllib.request, urllib.parse, urllib.error

CACHE_FILE = "translations_cache.json"
TARGETS = {"en": "EN-GB", "de": "DE", "es": "ES", "fr": "FR"}

# mappa nome-categoria -> id stabile (per agganciare le traduzioni curate in index.html)
NAME2ID = {
    "Antipasti & Sfizi":"antipasti", "Fritti":"fritti",
    "Le Pizze — Classiche":"classiche", "Le Pizze — Gourmet":"gourmet",
    "Calzoni":"calzoni", "Primi":"primi", "Secondi":"secondi",
    "Contorni":"contorni", "Dolci":"dolci", "Bevande":"bevande",
}

# fallback categorie (se la tabella "Categorie" non esiste): (nome, sottotitolo, ordine)
FALLBACK_CATEGORIES = [
    ("Antipasti & Sfizi","gli inizi che contano",1),
    ("Fritti","il peccato è servito",2),
    ("Le Pizze — Classiche","lievitazione 48h",3),
    ("Le Pizze — Gourmet","quelle che si danno un tono",4),
    ("Calzoni","la pizza che si ripiega su sé stessa",5),
    ("Primi","fatti come si deve",6),
    ("Secondi","roba seria",7),
    ("Contorni","mai da soli",8),
    ("Dolci","fatti in casa",9),
    ("Bevande","per accompagnare",10),
]

# fallback testi sito (se la tabella "Testi sito" non esiste)
DEFAULT_SITE = {
    "coperto": "2",
    "motto": "«Ogni pizza è un piccolo miracolo.\nLa lievitazione fa il resto.»",
    "frozenLegend": "* prodotto surgelato all'origine o congelato in loco",
    "footerNote": "Menù allergeni e informazioni sugli ingredienti disponibili su richiesta.",
    "legendNote": "Menù allergeni completo e informazioni sugli ingredienti disponibili su richiesta. Rif. Reg. UE 1169/2011.",
}
# chiave in "Testi sito" -> campo interno di site
TESTI_MAP = {
    "coperto":"coperto", "motto":"motto", "nota_surgelati":"frozenLegend",
    "nota_allergeni":"footerNote", "nota_legenda_allergeni":"legendNote",
}

LABEL2KEY = {
    "Glutine":"glutine","Crostacei":"crostacei","Uova":"uova","Pesce":"pesce",
    "Arachidi":"arachidi","Soia":"soia","Latte":"latte","Frutta a guscio":"frutta",
    "Sedano":"sedano","Senape":"senape","Sesamo":"sesamo","Solfiti":"solfiti",
    "Lupini":"lupini","Molluschi":"molluschi",
}


# ---------- Airtable ----------
def fetch_table(token, base_id, table, required=False):
    """Ritorna la lista dei record, o None se la tabella opzionale non esiste.
    Airtable segnala una tabella mancante in modi diversi (404, oppure 403
    'INVALID_PERMISSIONS_OR_MODEL_NOT_FOUND'). Dato che 'Piatti' (required)
    viene letta per prima con successo, i permessi sono a posto: quindi per
    le tabelle opzionali un 403/404/422 significa 'tabella assente'."""
    records, offset = [], None
    while True:
        url = "https://api.airtable.com/v0/%s/%s?pageSize=100" % (base_id, urllib.parse.quote(table))
        if offset:
            url += "&offset=" + urllib.parse.quote(offset)
        r = urllib.request.Request(url)
        r.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if not required and e.code in (400, 403, 404, 422):
                print("Tabella opzionale '%s' assente (HTTP %s): uso i valori di default." % (table, e.code))
                return None
            print("ERRORE Airtable su '%s': HTTP %s" % (table, e.code))
            if e.code == 403:
                print(">> Il token non ha 'data.records:read'.")
            elif e.code == 404:
                print(">> Tabella '%s' non trovata." % table)
            elif e.code == 401:
                print(">> Token non valido/scaduto.")
            print("Dettaglio:", body[:300]); sys.exit(1)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


# ---------- DeepL ----------
def deepl_endpoint(key):
    return "https://api-free.deepl.com/v2/translate" if key.strip().endswith(":fx") \
           else "https://api.deepl.com/v2/translate"

def deepl_translate(text, target_code, key):
    data = urllib.parse.urlencode({"text":text,"source_lang":"IT","target_lang":target_code}).encode()
    r = urllib.request.Request(deepl_endpoint(key), data=data)
    r.add_header("Authorization", "DeepL-Auth-Key " + key)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode())["translations"][0]["text"]

def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as fh: return json.load(fh)
    except Exception: return {}

def save_cache(cache):
    with open(CACHE_FILE,"w",encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)


# ---------- helpers ----------
def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii","ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+","-", s).strip("-").lower()
    return s or "cat"

def name_to_id(name):
    return NAME2ID.get(name.strip(), slugify(name))

def truthy(v):
    return v is True or (isinstance(v,str) and v.strip().lower() in ("true","1","si","sì","x","yes"))


# ---------- build ----------
def build(piatti, categorie, testi, deepl_key):
    # --- site texts ---
    site = dict(DEFAULT_SITE)
    if testi:
        for rec in testi:
            f = rec.get("fields", {})
            k = (f.get("Chiave") or "").strip()
            if k in TESTI_MAP and (f.get("Testo") not in (None, "")):
                site[TESTI_MAP[k]] = f.get("Testo")

    # --- categorie ordinate (da tabella o fallback) ---
    if categorie:
        cats = []
        for rec in categorie:
            f = rec.get("fields", {})
            nome = (f.get("Nome") or "").strip()
            if not nome or not truthy(f.get("Visibile")):
                continue
            cats.append((nome, (f.get("Sottotitolo") or "").strip(),
                         f.get("Ordine") if f.get("Ordine") is not None else 1e9))
        cats.sort(key=lambda c: c[2])
    else:
        cats = [(n, s, o) for (n, s, o) in FALLBACK_CATEGORIES]

    # --- piatti visibili ordinati ---
    rows = [r.get("fields", {}) for r in piatti if truthy(r.get("fields", {}).get("Visibile"))]
    rows.sort(key=lambda f: (f.get("Ordine") is None, f.get("Ordine", 1e9)))

    # --- traduzione descrizioni ---
    cache = load_cache()
    for lang in TARGETS: cache.setdefault(lang, {})
    calls = [0]; warned = {"no_key": False, "err": False}
    def tr_desc(desc_it):
        out = {"it": desc_it}
        for lang, code in TARGETS.items():
            if not desc_it: out[lang] = ""; continue
            if desc_it in cache[lang]: out[lang] = cache[lang][desc_it]; continue
            if not deepl_key: out[lang] = desc_it; warned["no_key"] = True; continue
            try:
                t = deepl_translate(desc_it, code, deepl_key); calls[0]+=1
                cache[lang][desc_it] = t; out[lang] = t
            except Exception as e:
                out[lang] = desc_it
                if not warned["err"]: print("Avviso DeepL:", str(e)[:160]); warned["err"]=True
        return out

    # --- sezioni ---
    sections = []
    for nome, subtitle, _ in cats:
        items = []
        for f in rows:
            if (f.get("Categoria") or "").strip() != nome:
                continue
            keys = [LABEL2KEY[a] for a in (f.get("Allergeni") or []) if a in LABEL2KEY]
            item = {
                "name": (f.get("Nome") or "").strip(),
                "price": (f.get("Prezzo") or "").strip(),
                "keys": keys,
                "desc": tr_desc((f.get("Descrizione") or "").strip()),
            }
            if truthy(f.get("Surgelato")): item["frozen"] = True
            items.append(item)
        if items:
            sections.append({"id": name_to_id(nome), "title": nome,
                             "subtitle": subtitle, "items": items})

    save_cache(cache)
    if warned["no_key"]:
        print("Nota: DEEPL_API_KEY assente -> descrizioni lasciate in italiano.")
    print("Traduzioni nuove richieste a DeepL:", calls[0])
    print("Categorie:", "da Airtable" if categorie else "fallback (codice)",
          "| Testi sito:", "da Airtable" if testi else "fallback (codice)")
    return {"site": site, "sections": sections}


def render_js(data):
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return ("/* GENERATO AUTOMATICAMENTE DA build_site.py — non modificare a mano.\n"
            "   Fonte: Airtable (Piatti + Categorie + Testi sito). Descrizioni: DeepL. */\n"
            "window.MENU_DATA = " + payload + ";\n")


def main():
    token = os.environ.get("AIRTABLE_TOKEN")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    deepl_key = os.environ.get("DEEPL_API_KEY", "").strip()
    if not token: print("ERRORE: manca il secret AIRTABLE_TOKEN."); sys.exit(1)
    if not base_id: print("ERRORE: manca AIRTABLE_BASE_ID nel workflow."); sys.exit(1)

    piatti = fetch_table(token, base_id, "Piatti", required=True)
    categorie = fetch_table(token, base_id, "Categorie")     # None se assente
    testi = fetch_table(token, base_id, "Testi sito")        # None se assente

    data = build(piatti, categorie, testi, deepl_key)
    n = sum(len(s["items"]) for s in data["sections"])
    with open("data.js","w",encoding="utf-8") as fh:
        fh.write(render_js(data))
    print("data.js rigenerato: %d sezioni, %d piatti visibili." % (len(data["sections"]), n))


if __name__ == "__main__":
    main()
