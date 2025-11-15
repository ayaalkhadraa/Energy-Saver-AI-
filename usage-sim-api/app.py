# -*- coding: utf-8 -*-
"""
usage-sim-api
-------------
Einfache Simulations-API für Stromverbrauchsdaten.
- /simulate: Gibt stündliche oder tägliche Dummy-Verbrauchswerte zurück.
- /stats:    Liefert Basisstatistiken (Durchschnitt/Min/Max) über N Tage.

Hinweis: Es handelt sich um simulierte Daten, nicht um echte Messwerte.
"""

from fastapi import FastAPI, HTTPException
import random, math

app = FastAPI(title="usage-sim-api")

@app.get("/")
def root():
    """
    Root-Endpunkt mit API-Informationen
    """
    return {
        "name": "usage-sim-api",
        "version": "1.0.0",
        "beschreibung": "Simulations-API für Stromverbrauchsdaten",
        "verfuegbare_endpunkte": {
            "/simulate": "GET - Simulierte Verbrauchsdaten",
            "/stats": "GET - Basisstatistiken über N Tage"
        },
        "hinweis": "Es handelt sich um simulierte Daten, nicht um echte Messwerte."
    }

def gen_hourly(days: int = 7):
    """Erzeugt stündliche Verbrauchswerte (kWh) für mehrere Tage."""
    random.seed(42)  # Reproduzierbare Werte
    data = []
    for d in range(days):
        for h in range(24):
            # Einfache Tageskurve + abendliche Spitze + leichte Zufallsschwankung
            basis = 0.4 + 0.2 * math.sin(h / 24 * 2 * math.pi)
            abend_peak = 0.6 if 18 <= h <= 22 else 0.0
            kwh = round(max(0.1, basis + abend_peak + random.uniform(-0.1, 0.1)), 3)
            data.append({"day": d, "hour": h, "kwh": kwh})
    return data

@app.get("/simulate")
def simulate(granularity: str = "hour", days: int = 7):
    """
    Liefert simulierte Verbrauchsdaten.
    - granularity: "hour" oder "day"
    - days: Anzahl der simulierten Tage
    """
    if granularity not in {"hour", "day"}:
        raise HTTPException(400, "granularity muss 'hour' oder 'day' sein.")
    stunden = gen_hourly(days)
    if granularity == "day":
        summen = {}
        for r in stunden:
            summen[r["day"]] = summen.get(r["day"], 0.0) + r["kwh"]
        return [{"day": d, "kwh": round(v, 3)} for d, v in summen.items()]
    return stunden

@app.get("/stats")
def stats(days: int = 7):
    """Berechnet Durchschnitt/Min/Max über stündliche Werte der letzten N Tage."""
    werte = [r["kwh"] for r in gen_hourly(days)]
    return {
        "days": days,
        "avg": round(sum(werte) / len(werte), 3),
        "max": round(max(werte), 3),
        "min": round(min(werte), 3),
    }
