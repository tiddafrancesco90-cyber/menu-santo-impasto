#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
 Crea la struttura del menu su Airtable — Santo Impasto
============================================================
Cosa fa:
  1) Trova la base che hai creato (di default "Menu Santo Impasto")
  2) Crea la tabella "Piatti" con tutti i campi giusti
  3) Inserisce automaticamente i 50 piatti della demo

PRIMA di lanciarlo:
  - Crea a mano una base VUOTA su Airtable chiamata esattamente:
        Menu Santo Impasto
    (Home Airtable -> Create -> Start from scratch)
  - Assicurati che il tuo Personal Access Token abbia gli scope:
        schema.bases:read, schema.bases:write, data.records:write

Come lanciarlo (Windows / Mac / Linux):
        python crea_base_airtable.py
  Ti verra' chiesto di incollare il token.

Serve solo la libreria standard di Python 3 (nessun pip install).
============================================================
"""

import json, sys, time, getpass
import urllib.request, urllib.error

API = "https://api.airtable.com/v0"
BASE_NAME = "Menu Santo"   # <-- nome della base creata a mano (rinominarla NON rompe il token)
TABLE_NAME = "Piatti"

# ---- I 14 allergeni (etichette che appariranno in Airtable) ----
ALLERGENI = ["Glutine","Crostacei","Uova","Pesce","Arachidi","Soia","Latte",
             "Frutta a guscio","Sedano","Senape","Sesamo","Solfiti","Lupini","Molluschi"]

# mappa chiave interna -> etichetta Airtable
KEY2LABEL = {
    "glutine":"Glutine","crostacei":"Crostacei","uova":"Uova","pesce":"Pesce",
    "arachidi":"Arachidi","soia":"Soia","latte":"Latte","frutta":"Frutta a guscio",
    "sedano":"Sedano","senape":"Senape","sesamo":"Sesamo","solfiti":"Solfiti",
    "lupini":"Lupini","molluschi":"Molluschi"
}

# ---- Categorie (etichette che appariranno in Airtable, in ordine) ----
CATEGORIE = ["Antipasti & Sfizi","Fritti","Le Pizze — Classiche","Le Pizze — Gourmet",
             "Calzoni","Primi","Secondi","Contorni","Dolci","Bevande"]

# ---- I 50 piatti: (categoria, nome, descrizione, prezzo, surgelato, [allergeni]) ----
PIATTI = [
 ("Antipasti & Sfizi","Tagliere del Santo","Salumi e formaggi toscani, miele e confetture","€ 14",False,["latte","frutta","solfiti"]),
 ("Antipasti & Sfizi","Bruschette miste (3 pz)","Pane toscano, pomodoro e olio nuovo","€ 7",False,["glutine"]),
 ("Antipasti & Sfizi","Burrata pugliese","Con pomodorini confit","€ 9",False,["latte"]),
 ("Antipasti & Sfizi","Polpette al sugo della nonna","Nel sugo lento di pomodoro","€ 8",False,["glutine","uova","latte","sedano"]),
 ("Antipasti & Sfizi","Fiori di zucca ripieni","Mozzarella e acciuga","€ 7",True,["glutine","uova","latte","pesce"]),
 ("Fritti","Coccoli, prosciutto e stracchino","Frittelle calde appena fatte","€ 8",False,["glutine","latte"]),
 ("Fritti","Supplì al telefono (2 pz)","Riso, ragù e mozzarella filante","€ 6",False,["glutine","uova","latte","sedano"]),
 ("Fritti","Olive all'ascolana (6 pz)","Ripiene e fritte","€ 6",True,["glutine","uova","latte","sedano"]),
 ("Fritti","Patatine fritte","Croccanti, sempre","€ 4",True,[]),
 ("Le Pizze — Classiche","Marinara","Pomodoro, aglio, origano, olio EVO","€ 6",False,["glutine"]),
 ("Le Pizze — Classiche","Margherita","Pomodoro, mozzarella, basilico","€ 7",False,["glutine","latte"]),
 ("Le Pizze — Classiche","Napoli","Acciughe e capperi","€ 8,50",False,["glutine","latte","pesce"]),
 ("Le Pizze — Classiche","Diavola","Salame piccante","€ 8,50",False,["glutine","latte"]),
 ("Le Pizze — Classiche","Capricciosa","Prosciutto, funghi, carciofi, uovo","€ 9,50",False,["glutine","latte","uova"]),
 ("Le Pizze — Classiche","Quattro Formaggi","Mozzarella, gorgonzola, fontina, grana","€ 9",False,["glutine","latte"]),
 ("Le Pizze — Classiche","Quattro Stagioni","Prosciutto, funghi, carciofi, olive","€ 9,50",False,["glutine","latte"]),
 ("Le Pizze — Classiche","Prosciutto e funghi","Cotto e champignon","€ 9",False,["glutine","latte"]),
 ("Le Pizze — Gourmet","La Santa","Bufala DOP, mortadella e pistacchio","€ 13",False,["glutine","latte","frutta"]),
 ("Le Pizze — Gourmet","Peccato di Gola","Nduja, stracciata e cipolla caramellata","€ 12",False,["glutine","latte","solfiti"]),
 ("Le Pizze — Gourmet","Ortolana","Verdure grigliate e pesto","€ 11",False,["glutine","latte","frutta"]),
 ("Le Pizze — Gourmet","Tonno e Cipolla","Tonno e cipolla di Tropea","€ 9,50",False,["glutine","pesce"]),
 ("Le Pizze — Gourmet","Boscaiola","Salsiccia, porcini e panna","€ 11",False,["glutine","latte"]),
 ("Calzoni","Calzone Classico","Cotto, mozzarella e funghi","€ 9",False,["glutine","latte"]),
 ("Calzoni","Calzone del Santo","Ricotta, spinaci e salsiccia","€ 10",False,["glutine","latte"]),
 ("Primi","Pici cacio e pepe","Pasta fresca tirata a mano","€ 10",False,["glutine","latte"]),
 ("Primi","Tagliatelle al ragù toscano","Ragù di carne lento","€ 11",False,["glutine","uova","sedano"]),
 ("Primi","Ravioli ricotta e spinaci","Burro e salvia","€ 10",False,["glutine","uova","latte"]),
 ("Primi","Risotto ai porcini","Mantecato ai funghi porcini","€ 11",False,["latte","solfiti"]),
 ("Secondi","Tagliata di manzo","Rucola e scaglie di grana","€ 18",False,["latte"]),
 ("Secondi","Peposo alla fornacina","Stracotto toscano al pepe","€ 14",False,["solfiti","sedano"]),
 ("Secondi","Baccalà alla livornese","In umido di pomodoro","€ 15",False,["pesce","sedano"]),
 ("Secondi","Cotoletta alla milanese","Con patate","€ 13",False,["glutine","uova","latte"]),
 ("Contorni","Insalata mista","","€ 4",False,[]),
 ("Contorni","Patate al forno","","€ 4",False,[]),
 ("Contorni","Fagioli all'uccelletto","Al pomodoro e salvia","€ 5",False,["sedano"]),
 ("Contorni","Verdure grigliate","","€ 5",False,[]),
 ("Dolci","Tiramisù del Santo","","€ 5",False,["glutine","uova","latte"]),
 ("Dolci","Panna cotta ai frutti di bosco","","€ 5",False,["latte"]),
 ("Dolci","Cantucci e Vin Santo","","€ 5",False,["glutine","uova","frutta","solfiti"]),
 ("Dolci","Tortino cioccolato cuore caldo","","€ 6",False,["glutine","uova","latte","soia"]),
 ("Bevande","Acqua nat. / friz. 0,75L","","€ 2",False,[]),
 ("Bevande","Birra della casa 0,4L","","€ 5",False,["glutine"]),
 ("Bevande","Birra artigianale toscana 0,33L","","€ 6",False,["glutine"]),
 ("Bevande","Bibite 0,33L","","€ 3",False,[]),
 ("Bevande","Chianti DOCG","calice / bottiglia","€ 5 / 18",False,["solfiti"]),
 ("Bevande","Vermentino","calice / bottiglia","€ 5 / 18",False,["solfiti"]),
 ("Bevande","Prosecco","calice / bottiglia","€ 5 / 20",False,["solfiti"]),
 ("Bevande","Caffè","","€ 1,50",False,[]),
 ("Bevande","Cappuccino","","€ 2",False,["latte"]),
 ("Bevande","Amari","","€ 4",False,["solfiti"]),
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


def main():
    print("="*52)
    print(" Setup base Airtable — Santo Impasto")
    print("="*52)
    try:
        token = getpass.getpass("Incolla il tuo Personal Access Token Airtable e premi Invio: ").strip()
    except Exception:
        token = input("Incolla il tuo token Airtable: ").strip()
    if not token:
        print("Nessun token inserito. Esco."); return

    # 1) trova la base
    print("\n[1/3] Cerco la base '%s'..." % BASE_NAME)
    st, res = req("GET", API + "/meta/bases", token)
    if st != 200:
        print("  ERRORE (%s): %s" % (st, res))
        print("  Controlla che il token abbia lo scope 'schema.bases:read'.")
        return
    bases = res.get("bases", [])
    base_id = None
    for b in bases:
        if b.get("name","").strip() == BASE_NAME:
            base_id = b["id"]; break
    if not base_id:
        # rete di sicurezza: se il token vede UNA sola base, usa quella
        if len(bases) == 1:
            base_id = bases[0]["id"]
            print("  Nome '%s' non combacia, ma il token vede una sola base" % BASE_NAME)
            print("  ('%s'): uso quella." % bases[0].get("name"))
        else:
            print("  Non trovata una base chiamata '%s'." % BASE_NAME)
            print("  Basi visibili dal token:")
            for b in bases:
                print("    - %s (%s)" % (b.get("name"), b["id"]))
            print("  Rinomina la base in '%s' oppure dimmi quale usare." % BASE_NAME)
            return
    print("  Trovata: %s" % base_id)

    # 2) crea la tabella "Piatti"
    print("\n[2/3] Creo la tabella '%s'..." % TABLE_NAME)
    fields = [
        {"name":"Nome","type":"singleLineText"},
        {"name":"Descrizione","type":"multilineText"},
        {"name":"Prezzo","type":"singleLineText"},
        {"name":"Categoria","type":"singleSelect",
         "options":{"choices":[{"name":c} for c in CATEGORIE]}},
        {"name":"Allergeni","type":"multipleSelects",
         "options":{"choices":[{"name":a} for a in ALLERGENI]}},
        {"name":"Surgelato","type":"checkbox",
         "options":{"icon":"check","color":"yellowBright"}},
        {"name":"Visibile","type":"checkbox",
         "options":{"icon":"check","color":"greenBright"}},
        {"name":"Ordine","type":"number","options":{"precision":0}},
    ]
    st, res = req("POST", API + "/meta/bases/%s/tables" % base_id, token,
                  {"name":TABLE_NAME,"fields":fields})
    if st == 200:
        table_id = res["id"]
        print("  Creata: %s" % table_id)
    elif st == 422 and "DUPLICATE" in json.dumps(res).upper():
        # tabella gia' esistente: recuperala
        st2, res2 = req("GET", API + "/meta/bases/%s/tables" % base_id, token)
        table_id = None
        for t in res2.get("tables", []):
            if t.get("name") == TABLE_NAME: table_id = t["id"]; break
        if not table_id:
            print("  ERRORE: tabella duplicata ma non ritrovata: %s" % res); return
        print("  Esisteva gia': la riuso (%s)." % table_id)
    else:
        print("  ERRORE (%s): %s" % (st, res))
        print("  Serve lo scope 'schema.bases:write' sul token.")
        return

    # 3) inserisci i 50 piatti (a lotti da 10)
    print("\n[3/3] Inserisco i %d piatti..." % len(PIATTI))
    records = []
    for i,(cat,nome,desc,prezzo,frozen,keys) in enumerate(PIATTI, start=1):
        f = {"Nome":nome,"Descrizione":desc,"Prezzo":prezzo,"Categoria":cat,
             "Allergeni":[KEY2LABEL[k] for k in keys],
             "Surgelato":bool(frozen),"Visibile":True,"Ordine":i}
        records.append({"fields":f})

    ok = 0
    for i in range(0, len(records), 10):
        chunk = records[i:i+10]
        st, res = req("POST", API + "/%s/%s" % (base_id, table_id), token,
                      {"records":chunk,"typecast":True})
        if st == 200:
            ok += len(res.get("records", []))
            print("  ...%d/%d" % (ok, len(records)))
        else:
            print("  ERRORE inserimento (%s): %s" % (st, res))
            print("  Serve lo scope 'data.records:write' sul token.")
            return
        time.sleep(0.25)  # gentile coi rate limit

    print("\n" + "="*52)
    print(" FATTO. Base pronta con %d piatti." % ok)
    print(" base_id: %s" % base_id)
    print(" (ti servira' per collegare la generazione del sito)")
    print("="*52)


if __name__ == "__main__":
    main()
