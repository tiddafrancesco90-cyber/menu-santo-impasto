#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
 Aggiunge due tabelle alla base Airtable — Santo Impasto
   - "Categorie"  : gestione sezioni (nome, sottotitolo, visibile, ordine)
   - "Testi sito" : testi modificabili (motto, coperto, note)
============================================================
Prerequisiti:
  - La base "Menu Santo" esiste gia' (quella con la tabella Piatti).
  - Il token ha gli scope: schema.bases:read, schema.bases:write,
    data.records:read, data.records:write.

Come lanciarlo su Colab (da telefono):
  In una cella incolla ed esegui:
     import urllib.request
     code = urllib.request.urlopen("https://raw.githubusercontent.com/tiddafrancesco90-cyber/menu-santo-impasto/main/crea_liste_airtable.py").read().decode()
     exec(code)
  Poi incolla il token quando richiesto.

Nota: lo script NON crea doppioni. Se una tabella esiste gia' e ha
righe, salta l'inserimento.
============================================================
"""

import json, sys, time, getpass
import urllib.request, urllib.error

API = "https://api.airtable.com/v0"
BASE_NAME = "Menu Santo"

# --- Categorie: (Nome, Sottotitolo, Ordine) — i Nomi DEVONO combaciare
#     esattamente con la tendina "Categoria" della tabella Piatti ---
CATEGORIE = [
    ("Antipasti & Sfizi", "gli inizi che contano", 1),
    ("Fritti", "il peccato è servito", 2),
    ("Le Pizze — Classiche", "lievitazione 48h", 3),
    ("Le Pizze — Gourmet", "quelle che si danno un tono", 4),
    ("Calzoni", "la pizza che si ripiega su sé stessa", 5),
    ("Primi", "fatti come si deve", 6),
    ("Secondi", "roba seria", 7),
    ("Contorni", "mai da soli", 8),
    ("Dolci", "fatti in casa", 9),
    ("Bevande", "per accompagnare", 10),
]

# --- Testi sito: (Chiave, Etichetta leggibile, Testo, Ordine) ---
#     La "Chiave" e' un identificativo tecnico: NON va cambiata.
#     Il tuo amico modifica solo la colonna "Testo".
TESTI = [
    ("coperto", "Coperto — importo in € (solo numero)", "2", 1),
    ("motto", "Motto — frase sotto il titolo", "«Ogni pizza è un piccolo miracolo.\nLa lievitazione fa il resto.»", 2),
    ("nota_surgelati", "Nota surgelati — in fondo alla pagina", "* prodotto surgelato all'origine o congelato in loco", 3),
    ("nota_allergeni", "Nota allergeni — in fondo alla pagina", "Menù allergeni e informazioni sugli ingredienti disponibili su richiesta.", 4),
    ("nota_legenda_allergeni", "Nota nella legenda allergeni (popup)", "Menù allergeni completo e informazioni sugli ingredienti disponibili su richiesta. Rif. Reg. UE 1169/2011.", 5),
]


def req(method, url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer " + token)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try: body = json.loads(body)
        except: pass
        return e.code, body


def find_base(token):
    st, res = req("GET", API + "/meta/bases", token)
    if st != 200:
        print("ERRORE (%s) elencando le basi: %s" % (st, res))
        print("Il token ha 'schema.bases:read'?"); return None
    bases = res.get("bases", [])
    for b in bases:
        if b.get("name","").strip() == BASE_NAME:
            return b["id"]
    if len(bases) == 1:
        print("Nome non combacia, ma il token vede una sola base: la uso.")
        return bases[0]["id"]
    print("Base '%s' non trovata. Basi visibili:" % BASE_NAME)
    for b in bases: print("  -", b.get("name"), b["id"])
    return None


def get_table(token, base_id, name):
    st, res = req("GET", API + "/meta/bases/%s/tables" % base_id, token)
    if st != 200:
        return None
    for t in res.get("tables", []):
        if t.get("name") == name:
            return t
    return None


def create_table(token, base_id, name, fields):
    st, res = req("POST", API + "/meta/bases/%s/tables" % base_id, token,
                  {"name": name, "fields": fields})
    if st == 200:
        print("  Tabella '%s' creata." % name); return res["id"]
    if st == 422 and "DUPLICATE" in json.dumps(res).upper():
        t = get_table(token, base_id, name)
        if t:
            print("  Tabella '%s' gia' esistente: la riuso." % name); return t["id"]
    print("  ERRORE creando '%s' (%s): %s" % (name, st, res))
    print("  Serve lo scope 'schema.bases:write'."); return None


def table_has_rows(token, base_id, table_id):
    st, res = req("GET", API + "/%s/%s?maxRecords=1" % (base_id, table_id), token)
    return st == 200 and len(res.get("records", [])) > 0


def insert(token, base_id, table_id, records):
    ok = 0
    for i in range(0, len(records), 10):
        chunk = records[i:i+10]
        st, res = req("POST", API + "/%s/%s" % (base_id, table_id), token,
                      {"records": chunk, "typecast": True})
        if st == 200:
            ok += len(res.get("records", []))
        else:
            print("  ERRORE inserimento (%s): %s" % (st, res)); return ok
        time.sleep(0.25)
    return ok


def main():
    print("="*52)
    print(" Setup tabelle Categorie + Testi sito")
    print("="*52)
    try:
        token = getpass.getpass("Incolla il token Airtable e premi Invio: ").strip()
    except Exception:
        token = input("Token Airtable: ").strip()
    if not token:
        print("Nessun token. Esco."); return

    base_id = find_base(token)
    if not base_id:
        return
    print("Base: %s\n" % base_id)

    # ---- Categorie ----
    print("[1/2] Tabella 'Categorie'")
    cat_fields = [
        {"name":"Nome","type":"singleLineText"},
        {"name":"Sottotitolo","type":"singleLineText"},
        {"name":"Visibile","type":"checkbox","options":{"icon":"check","color":"greenBright"}},
        {"name":"Ordine","type":"number","options":{"precision":0}},
    ]
    cat_id = create_table(token, base_id, "Categorie", cat_fields)
    if cat_id:
        if table_has_rows(token, base_id, cat_id):
            print("  Ha gia' righe: non inserisco doppioni.")
        else:
            recs = [{"fields":{"Nome":n,"Sottotitolo":s,"Visibile":True,"Ordine":o}}
                    for (n,s,o) in CATEGORIE]
            print("  Inserite:", insert(token, base_id, cat_id, recs), "categorie.")

    # ---- Testi sito ----
    print("\n[2/2] Tabella 'Testi sito'")
    txt_fields = [
        {"name":"Chiave","type":"singleLineText"},
        {"name":"Etichetta","type":"singleLineText"},
        {"name":"Testo","type":"multilineText"},
        {"name":"Ordine","type":"number","options":{"precision":0}},
    ]
    txt_id = create_table(token, base_id, "Testi sito", txt_fields)
    if txt_id:
        if table_has_rows(token, base_id, txt_id):
            print("  Ha gia' righe: non inserisco doppioni.")
        else:
            recs = [{"fields":{"Chiave":k,"Etichetta":e,"Testo":t,"Ordine":o}}
                    for (k,e,t,o) in TESTI]
            print("  Inseriti:", insert(token, base_id, txt_id, recs), "testi.")

    print("\n" + "="*52)
    print(" FATTO. Ora rilancia il workflow su GitHub per veder")
    print(" comparire categorie e testi presi da Airtable.")
    print("="*52)


if __name__ == "__main__":
    main()
