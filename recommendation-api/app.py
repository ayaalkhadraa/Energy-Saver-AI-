import os
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus .env Datei
load_dotenv()

# Konfiguration über Umgebungsvariablen
USAGE_API = os.getenv("USAGE_API", "http://usage-sim-api:8000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
AI_SAFE_MODE = os.getenv("AI_SAFE_MODE", "true").lower() == "true"
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "de")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Verbrauchs-Schwellen (kWh pro Stunde) - konfigurierbar über ENV
# Beispiel-Werte basieren auf der internen Simulations-API (avg ≈ 0.52 kWh/h)
LOW_THRESHOLD = float(os.getenv("LOW_THRESHOLD", "0.4"))
HIGH_THRESHOLD = float(os.getenv("HIGH_THRESHOLD", "0.8"))

app = FastAPI(
    title="Energie-Spar-Empfehlungs-API",
    description="API für personalisierte Energiespartipps basierend auf Verbrauchsdaten",
    version="1.0.0"
)

class TipsRequest(BaseModel):
    """
    Anfrage-Modell für Energiespartipps
    
    Attribute:
        days: Anzahl der Tage für die Verbrauchsanalyse (Standard: 7)
        max_tips: Maximale Anzahl von Tipps in der Antwort (Standard: 5)
        languages: Liste der gewünschten Sprachen (Standard: ["de"])
    """
    days: int = 7
    max_tips: int = 5
    languages: Optional[List[str]] = ["de"]  # Standardsprache ist Deutsch

async def get_avg(days: int) -> float | None:
    """
    Holt den durchschnittlichen Energieverbrauch für die angegebene Anzahl von Tagen
    
    Args:
        days: Anzahl der Tage für die Durchschnittsberechnung
        
    Returns:
        Durchschnittlicher Verbrauch in kWh oder None bei Fehlern
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{USAGE_API}/stats", params={"days": days})
        if r.status_code == 200 and "avg" in r.json():
            return float(r.json()["avg"])
    except Exception:
        pass
    return None

def rule_based_tips(avg: float, max_tips: int, langs: List[str]) -> dict:
    """
    Generiert regelbasierte Energiespartipps auf Deutsch
    
    Args:
        avg: Durchschnittlicher Verbrauch in kWh
        max_tips: Maximale Anzahl von Tipps
        langs: Liste der gewünschten Sprachen
        
    Returns:
        Dictionary mit Tipps und Metadaten
    """
    # Sichere und bewährte Energiespartipps auf Deutsch
    tips_de = [
        "Schalten Sie Geräte im Standby-Modus nachts vollständig aus.",
        "Verwenden Sie energieeffiziente LED-Beleuchtung.",
        "Betreiben Sie Wasch- und Spülmaschine nur bei voller Beladung.",
        "Trennen Sie unbenutzte Ladegeräte vom Stromnetz.",
        "Senken Sie die Warmwassertemperatur um 1-2 Grad ab.",
        "Nutzen Sie Zeitschaltuhren für elektrische Geräte.",
        "Überprüfen Sie die Dichtungen von Kühl- und Gefrierschränken.",
        "Verwenden Sie Deckel beim Kochen auf dem Herd."
    ]
    
    # Klassifiziere Verbrauch und ergänze gezielte Tipps
    def classify_consumption(avg_val: float) -> str:
        if avg_val is None:
            return "unknown"
        if avg_val < LOW_THRESHOLD:
            return "low"
        if avg_val > HIGH_THRESHOLD:
            return "high"
        return "normal"

    classification = classify_consumption(avg)

    if classification == "high":
        tips_de.extend([
            "Verlagern Sie den Betrieb energieintensiver Geräte in verbrauchsarme Zeiten.",
            "Prüfen Sie, ob alte Geräte durch energieeffizientere ersetzt werden können.",
            "Führen Sie einen Energie-Check durch, um Großverbraucher im Haushalt zu identifizieren."
        ])
    elif classification == "low":
        tips_de.extend([
            "Ihr Verbrauch ist niedrig — prüfen Sie, ob automatische Abschaltungen korrekt funktionieren.",
            "Nutzen Sie Energiesparmodi und behalten Sie Wartungsempfehlungen bei.",
            "Kontrollieren Sie, ob Messwerte plausibel sind (z.B. kein fehlerhafter Sensor)."
        ])
    else:
        # normal: allgemeine Hinweise, evtl. einzelne Optimierungen
        tips_de.extend([
            "Planen Sie energieintensive Haushaltsaufgaben in Zeiten mit niedrigerem Verbrauch.",
            "Nutzen Sie Zeitschaltuhren und effiziente Betriebsweisen für Geräte."
        ])

    return {
        "quelle": "regelbasiert",
        "klassifikation": classification,
        "tipps": tips_de[:max_tips],
        "sprache": "de",
        "durchschnitt_kwh": avg
    }

async def call_llm_tips(avg: float, max_tips: int, langs: List[str]) -> str | None:
    """
    Ruft AI-generierte Energiespartipps über OpenAI API ab
    
    Args:
        avg: Durchschnittlicher Verbrauch in kWh
        max_tips: Maximale Anzahl von Tipps
        langs: Liste der gewünschten Sprachen
        
    Returns:
        AI-generierte Tipps als String oder None bei Fehlern
    """
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Bestimme die Sprache für den Prompt
        language = "Deutsch" if "de" in langs else "Deutsch"  # Standard auf Deutsch
        
        prompt = (
            f"Erstelle präzise und sichere Energiespartipps für einen deutschen Haushalt auf {language}.\n"
            f"- Durchschnittlicher stündlicher Verbrauch: {avg} kWh.\n"
            f"- Gib zwischen 3 und {max_tips} praktische Tipps.\n"
            "Bedingungen: Keine gefährlichen technischen Ratschläge, keine erfundenen Zahlen. "
            "Kurze, umsetzbare Sätze. Bei unzureichenden Informationen antworte: 'Keine genauen Angaben möglich.'\n"
            "Fokus auf alltägliche, sichere Energiesparmaßnahmen."
        )
        
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system", 
                    "content": "Du bist ein Experte für Haushalts-Energieeffizienz. Priorität haben Sicherheit und Genauigkeit. Antworte ausschließlich auf Deutsch."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2 if AI_SAFE_MODE else 0.5,
            max_tokens=300
        )
        return resp.choices[0].message.content
    except Exception:
        return None

@app.post("/tips")
async def tips(req: TipsRequest):
    """
    Hauptendpunkt für Energiespartipps
    
    Liefert personalisierte Energiespartipps basierend auf dem Verbrauchsprofil.
    Verwendet AI-Empfehlungen wenn verfügbar, andernfalls regelbasierte Tipps.
    
    Args:
        req: TipsRequest mit Parametern für die Tipp-Generierung
        
    Returns:
        Dictionary mit Energiespartipps und Metadaten
    """
    avg = await get_avg(req.days)

    # Falls kein Durchschnitt ermittelt werden kann, allgemeine Tipps zurückgeben
    if avg is None:
        fallback = rule_based_tips(0.7, req.max_tips, req.languages or ["de"])
        fallback["nachricht"] = "Keine genauen Verbrauchsdaten verfügbar. Hier sind allgemeine Energiespartipps."
        return fallback

    # Versuche zuerst AI-generierte Tipps für bessere Formulierung
    llm_text = await call_llm_tips(avg, req.max_tips, req.languages or ["de"])
    if llm_text:
        # Erweiterte Sicherheitsfilter: Verhindere gefährliche Ratschläge
        verbotene_begriffe = [
            "hauptschalter ausschalten", 
            "stromzähler manipulieren", 
            "sicherungen entfernen",
            "elektrische anlage öffnen",
            "kabel durchtrennen",
            "elektrische installation",
            "verkabelung ändern",
            "sicherung überbrücken"
        ]
        
        # Zusätzliche gefährliche Wörter (einzeln)
        gefaehrliche_woerter = ["hochspannung", "starkstrom", "manipulation", "überbrücken"]
        
        llm_lower = llm_text.lower()
        
        # Prüfe verbotene Begriffe (Phrasen)
        for begriff in verbotene_begriffe:
            if begriff in llm_lower:
                llm_text = "Keine genauen Angaben möglich; unsichere Empfehlung erkannt. Hier sind bewährte allgemeine Tipps."
                break
        
        # Prüfe einzelne gefährliche Wörter
        if llm_text != "Keine genauen Angaben möglich; unsichere Empfehlung erkannt. Hier sind bewährte allgemeine Tipps.":
            for wort in gefaehrliche_woerter:
                if wort in llm_lower:
                    llm_text = "Keine genauen Angaben möglich; unsichere Empfehlung erkannt. Hier sind bewährte allgemeine Tipps."
                    break
                
        return {
            "quelle": "ai-generiert", 
            "durchschnitt_kwh": avg, 
            "tipps_text": llm_text, 
            "sprache": "de"
        }

    # Falls AI nicht verfügbar/fehlgeschlagen → regelbasierte Tipps
    return rule_based_tips(avg, req.max_tips, req.languages or ["de"])


@app.get("/")
async def root():
    """
    Root-Endpunkt mit API-Informationen
    """
    return {
        "name": "Energie-Spar-Empfehlungs-API",
        "version": "1.0.0",
        "beschreibung": "API für personalisierte Energiespartipps",
        "verfuegbare_endpunkte": {
            "/tips": "POST - Energiespartipps anfordern",
            "/docs": "GET - API Dokumentation"
        },
        "standardsprache": DEFAULT_LANGUAGE
    }


@app.get("/health")
async def health_check():
    """
    Gesundheitsprüfung der API
    """
    return {
        "status": "gesund",
        "ai_verfuegbar": bool(OPENAI_API_KEY),
        "safe_modus": AI_SAFE_MODE
    }


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starte Energie-Spar-API auf {API_HOST}:{API_PORT}")
    print(f"📊 Verbrauchs-API: {USAGE_API}")
    print(f"🤖 AI-Modus: {'Aktiviert' if OPENAI_API_KEY else 'Deaktiviert'}")
    print(f"🔒 Sicherheitsmodus: {'An' if AI_SAFE_MODE else 'Aus'}")
    print(f"🌐 Standardsprache: {DEFAULT_LANGUAGE}")
    
    uvicorn.run(
        "app:app", 
        host=API_HOST, 
        port=API_PORT, 
        reload=True
    )
