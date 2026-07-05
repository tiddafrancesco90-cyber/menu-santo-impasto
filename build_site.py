#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera data.js da Airtable (tabella 'Piatti').
Traduce SOLO le descrizioni dei piatti in EN/DE/ES/FR tramite DeepL,
con cache su translations_cache.json (traduce solo cio' che e' nuovo/cambiato).
Il resto dei testi (interfaccia, categorie, allergeni, motto) e' curato
a mano dentro index.html, quindi qui non serve tradurlo.

Env richieste:
  AIRTABLE_TOKEN, AIRTABLE_BASE_ID   (obbligatorie)
  DEEPL_API_KEY                      (opzionale: senza, le descrizioni
                                      restano in italiano su tutte le lingue)
"""

import os, sys, json
import urllib.request, urllib.parse, urllib.error

TABLE = "Piatti"
CACHE_FILE = "translations_cache.json"

# lingue di destinazione -> codice DeepL
TARGETS = {"en": "EN-GB", "de": "DE", "es": "ES", "fr": "FR"}

# ordine + id + sottotitolo (IT) delle categorie — servono come fallback;
# le traduzioni curate vivono in index.html
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

RESTAURANT = {"name": "Santo Impasto", "coperto": 2}


# ---------- Airtable ----------
def fetch_records(token, base_id):
    records, offset = [], None
    while True:
        url = "https://api.airtable.com/v0/%s/%s?pageSize=100" % (base_id, TABLE)
        if offset:
            url += "&offset=" + urllib.parse.quote(offset)
        r = urllib.request.Request(url)
        r.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            print("ERRORE Airtable: HTTP %s" % e.code)
            if e.code == 403:
                print(">> Il token non ha 'data.records:read'. Aggiungilo e riprova.")
            elif e.code == 404:
                print(">> Base/tabella non trovata (base %s, tabella '%s')." % (base_id, TABLE))
            elif e.code == 401:
                print(">> Token non valido/scaduto (secret AIRTABLE_TOKEN).")
            print("Dettaglio:", body[:300]); sys.exit(1)
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


# ---------- DeepL ----------
def deepl_endpoint(key):
    # le chiavi free finiscono con ":fx"
    return "https://api-free.deepl.com/v2/translate" if key.strip().endswith(":fx") \
           else "https://api.deepl.com/v2/translate"

def deepl_translate(text, target_code, key):
    data = urllib.parse.urlencode({
        "text": text, "source_lang": "IT", "target_lang": target_code
    }).encode()
    r = urllib.request.Request(deepl_endpoint(key), data=data)
    r.add_header("Authorization", "DeepL-Auth-Key " + key)
    with urllib.request.urlopen(r, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    return out["translations"][0]["text"]


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)


# ---------- Build ----------
def build(records, deepl_key):
    rows = [r.get("fields", {}) for r in records if r.get("fields", {}).get("Visibile")]
    rows.sort(key=lambda f: (f.get("Ordine") is None, f.get("Ordine", 1e9)))

    cache = load_cache()
    for lang in TARGETS:
        cache.setdefault(lang, {})
    calls = [0]
    warned = {"no_key": False, "err": False}

    def tr_desc(desc_it):
        out = {"it": desc_it}
        for lang, code in TARGETS.items():
            if not desc_it:
                out[lang] = ""
                continue
            if desc_it in cache[lang]:
                out[lang] = cache[lang][desc_it]
                continue
            if not deepl_key:
                out[lang] = desc_it           # fallback: resta in IT
                warned["no_key"] = True
                continue
            try:
                t = deepl_translate(desc_it, code, deepl_key)
                calls[0] += 1
                cache[lang][desc_it] = t
                out[lang] = t
            except Exception as e:
                out[lang] = desc_it           # fallback in caso di errore
                if not warned["err"]:
                    print("Avviso DeepL:", str(e)[:160]); warned["err"] = True
        return out

    sections = []
    for label, sec_id, subtitle in CATEGORY_CONFIG:
        items = []
        for f in rows:
            if (f.get("Categoria") or "").strip() != label:
                continue
            keys = []
            for a in (f.get("Allergeni") or []):
                # mappa etichetta -> chiave (minuscolo, "Frutta a guscio" -> "frutta")
                k = {"Glutine":"glutine","Crostacei":"crostacei","Uova":"uova","Pesce":"pesce",
                     "Arachidi":"arachidi","Soia":"soia","Latte":"latte","Frutta a guscio":"frutta",
                     "Sedano":"sedano","Senape":"senape","Sesamo":"sesamo","Solfiti":"solfiti",
                     "Lupini":"lupini","Molluschi":"molluschi"}.get(a)
                if k:
                    keys.append(k)
            item = {
                "name": (f.get("Nome") or "").strip(),
                "price": (f.get("Prezzo") or "").strip(),
                "keys": keys,
                "desc": tr_desc((f.get("Descrizione") or "").strip()),
            }
            if f.get("Surgelato"):
                item["frozen"] = True
            items.append(item)
        if items:
            sections.append({"id": sec_id, "title": label, "subtitle": subtitle, "items": items})

    save_cache(cache)
    if warned["no_key"]:
        print("Nota: DEEPL_API_KEY assente -> descrizioni lasciate in italiano.")
    print("Traduzioni nuove richieste a DeepL:", calls[0])
    return {"restaurant": RESTAURANT, "sections": sections}


def render_js(data):
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return ("/* GENERATO AUTOMATICAMENTE DA build_site.py — non modificare a mano.\n"
            "   Fonte dati: Airtable (tabella 'Piatti'). Descrizioni: DeepL. */\n"
            "window.MENU_DATA = " + payload + ";\n")


def main():
    token = os.environ.get("AIRTABLE_TOKEN")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    deepl_key = os.environ.get("DEEPL_API_KEY", "").strip()
    if not token:
        print("ERRORE: manca il secret AIRTABLE_TOKEN."); sys.exit(1)
    if not base_id:
        print("ERRORE: manca AIRTABLE_BASE_ID nel workflow."); sys.exit(1)

    recs = fetch_records(token, base_id)
    data = build(recs, deepl_key)
    n = sum(len(s["items"]) for s in data["sections"])
    with open("data.js", "w", encoding="utf-8") as fh:
        fh.write(render_js(data))
    print("data.js rigenerato: %d sezioni, %d piatti visibili." % (len(data["sections"]), n))


if __name__ == "__main__":
    main()
