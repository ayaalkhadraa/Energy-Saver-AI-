import os
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
import numpy as np
try:
    import faiss
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    faiss = None

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

# Embeddings-Datenbank für verbesserte AI-Antworten
ENERGY_TIPS_DATABASE = [
    {
        "kategorie": "standby",
        "verbrauch_typ": "hoch",
        "tipp": "Verwenden Sie schaltbare Steckdosenleisten für Geräte im Standby-Modus. Bis zu 15% Einsparung möglich.",
        "sicherheit": "sicher"
    },
    {
        "kategorie": "beleuchtung",
        "verbrauch_typ": "normal",
        "tipp": "LED-Lampen verbrauchen 80% weniger Energie als Glühbirnen bei gleicher Helligkeit.",
        "sicherheit": "sicher"
    },
    {
        "kategorie": "heizen",
        "verbrauch_typ": "hoch", 
        "tipp": "Senken Sie die Raumtemperatur um 1°C - das spart etwa 6% Heizenergie.",
        "sicherheit": "sicher"
    },
    {
        "kategorie": "kochen",
        "verbrauch_typ": "normal",
        "tipp": "Nutzen Sie Deckel beim Kochen - reduziert Energieverbrauch um bis zu 50%.",
        "sicherheit": "sicher"
    },
    {
        "kategorie": "waschen",
        "verbrauch_typ": "normal",
        "tipp": "Waschen Sie bei 30°C statt 60°C - spart bis zu 60% der Waschenergie.",
        "sicherheit": "sicher"
    }
]

# Embeddings-Index (wird bei Bedarf initialisiert)
embeddings_index = None
embeddings_texts = None

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

def initialize_embeddings():
    """
    Initialisiert die Embeddings-Datenbank für verbesserte AI-Antworten
    """
    global embeddings_index, embeddings_texts
    
    if not OPENAI_API_KEY or not EMBEDDINGS_AVAILABLE:
        return False
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Erstelle Embeddings für alle sicheren Energietipps
        texts = [f"{tip['kategorie']}: {tip['tipp']}" for tip in ENERGY_TIPS_DATABASE]
        embeddings_texts = texts
        
        embeddings = []
        for text in texts:
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )
            embeddings.append(response.data[0].embedding)
        
        # Erstelle FAISS-Index
        embeddings_array = np.array(embeddings).astype('float32')
        embeddings_index = faiss.IndexFlatIP(embeddings_array.shape[1])  # Inner Product für Similarität
        faiss.normalize_L2(embeddings_array)  # Normalisiere für Cosine-Similarity
        embeddings_index.add(embeddings_array)
        
        return True
        
    except Exception:
        return False

def get_context_from_embeddings(query: str, top_k: int = 3) -> List[str]:
    """
    Sucht relevante Tipps basierend auf Embeddings-Ähnlichkeit
    """
    global embeddings_index, embeddings_texts
    
    if not embeddings_index or not OPENAI_API_KEY:
        return []
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Erstelle Embedding für Query
        response = client.embeddings.create(
            input=query,
            model="text-embedding-3-small"
        )
        query_embedding = np.array([response.data[0].embedding]).astype('float32')
        faiss.normalize_L2(query_embedding)
        
        # Suche ähnliche Tipps
        scores, indices = embeddings_index.search(query_embedding, top_k)
        
        relevant_tips = []
        for idx in indices[0]:
            if idx < len(ENERGY_TIPS_DATABASE):
                tip_data = ENERGY_TIPS_DATABASE[idx]
                relevant_tips.append(f"Kategorie {tip_data['kategorie']}: {tip_data['tipp']}")
                
        return relevant_tips
        
    except Exception:
        return []

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

async def call_llm_tips_enhanced(avg: float, max_tips: int, langs: List[str]) -> str | None:
    """
    Erweiterte AI-Tipps mit Embeddings-Kontext - SICHERHEITSFILTER BLEIBEN AKTIV
    
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
        language = "Deutsch" if "de" in langs else "Deutsch"
        
        # Erstelle Kontext-Query basierend auf Verbrauch
        if avg > HIGH_THRESHOLD:
            context_query = "hoher energieverbrauch reduzieren sparen effizienz"
        elif avg < LOW_THRESHOLD:
            context_query = "niedriger verbrauch optimieren effizienz standby"
        else:
            context_query = "normaler energieverbrauch optimieren haushalt"
        
        # Hole relevante Tipps aus Embeddings
        context_tips = get_context_from_embeddings(context_query, top_k=2)
        context_text = ""
        if context_tips:
            context_text = f"\\n\\nRelevante bewährte Methoden:\\n" + "\\n".join(context_tips)
        
        prompt = (
            f"Erstelle präzise und sichere Energiespartipps für einen deutschen Haushalt auf {language}.\\n"
            f"- Durchschnittlicher stündlicher Verbrauch: {avg} kWh.\\n"
            f"- Gib zwischen 3 und {max_tips} praktische Tipps.\\n"
            "WICHTIG: Keine gefährlichen technischen Ratschläge, keine erfundenen Zahlen. "
            "Kurze, umsetzbare Sätze. Bei unzureichenden Informationen antworte: 'Keine genauen Angaben möglich.'\\n"
            f"Fokus auf alltägliche, sichere Energiesparmaßnahmen.{context_text}"
        )
        
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system", 
                    "content": "Du bist ein Experte für Haushalts-Energieeffizienz. OBERSTE PRIORITÄT: Sicherheit und Genauigkeit. Antworte ausschließlich auf Deutsch. Gib NIEMALS gefährliche elektrische Ratschläge."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2 if AI_SAFE_MODE else 0.5,
            max_tokens=300
        )
        return resp.choices[0].message.content
    except Exception:
        return None

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
    ALLE SICHERHEITSFILTER BLEIBEN AKTIV!
    
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

    # Versuche zuerst erweiterte AI-Tipps mit Embeddings-Kontext
    llm_text = await call_llm_tips_enhanced(avg, req.max_tips, req.languages or ["de"])
    if llm_text:
        # KRITISCHE SICHERHEITSFILTER - MÜSSEN ERHALTEN BLEIBEN!
        verbotene_begriffe = [
            "hauptschalter ausschalten", 
            "stromzähler manipulieren", 
            "sicherungen entfernen",
            "sicherung entfernen", 
            "elektrische anlage öffnen",
            "kabel durchtrennen",
            "elektrische installation",
            "verkabelung ändern",
            "sicherung überbrücken"
        ]
        
        # Zusätzliche gefährliche Wörter (einzeln)
        gefaehrliche_woerter = ["hochspannung", "starkstrom", "manipulation", "überbrücken", "manipulieren"]
        
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
            "quelle": "ai-enhanced" if llm_text != "Keine genauen Angaben möglich; unsichere Empfehlung erkannt. Hier sind bewährte allgemeine Tipps." else "regelbasiert-fallback", 
            "durchschnitt_kwh": avg, 
            "tipps_text": llm_text, 
            "sprache": "de",
            "sicherheitsfilter": "aktiv",
            "embeddings_verwendet": bool(embeddings_index)
        }

    # Falls AI nicht verfügbar/fehlgeschlagen → regelbasierte Tipps
    result = rule_based_tips(avg, req.max_tips, req.languages or ["de"])
    result["sicherheitsfilter"] = "aktiv"
    return result


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
    Gesundheitsprüfung der API mit Embeddings-Status
    """
    # Initialisiere Embeddings bei erster Anfrage
    global embeddings_index
    if embeddings_index is None and OPENAI_API_KEY and EMBEDDINGS_AVAILABLE:
        embeddings_ready = initialize_embeddings()
    else:
        embeddings_ready = bool(embeddings_index)
    
    return {
        "status": "gesund",
        "ai_verfuegbar": bool(OPENAI_API_KEY),
        "embeddings_verfuegbar": embeddings_ready and EMBEDDINGS_AVAILABLE,
        "safe_modus": AI_SAFE_MODE,
        "sicherheitsfilter": "aktiv"
    }


if __name__ == "__main__":
    import uvicorn
    print(f" Starte Energie-Spar-API auf {API_HOST}:{API_PORT}")
    print(f"Verbrauchs-API: {USAGE_API}")
    print(f"AI-Modus: {'Aktiviert' if OPENAI_API_KEY else 'Deaktiviert'}")
    print(f"Sicherheitsmodus: {'An' if AI_SAFE_MODE else 'Aus'}")
    print(f"Standardsprache: {DEFAULT_LANGUAGE}")
    
    uvicorn.run(
        "app:app", 
        host=API_HOST, 
        port=API_PORT, 
        reload=True
    )
