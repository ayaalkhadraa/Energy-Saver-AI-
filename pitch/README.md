
Pitch‑Material für das Projekt

Dateien in diesem Ordner:

- `script.md` — Sprechtext für einen kurzen Pitch (ca. 60–75 Sekunden). Nutzen Sie dieses Skript für Ihre Aufnahme oder als Vorlage für eine Sprecherin/einen Sprecher.
- `pitch.mp3` — (optional) Hier können Sie später die fertige Audio‑Datei ablegen. Empfehlung: MP3, 128–192 kbps, Dateiname `pitch/pitch.mp3`.

Aufnahme‑Tipps (kurz):

1. Raum: Ruhiger Raum, möglichst wenig Hall.  
2. Mikrofon: Headset oder externes USB‑Mikrofon verbessert die Qualität.  
3. Abstand: Etwa 10–20 cm zum Mikrofon; Pop‑Filter nutzen, wenn möglich.  
4. Format: MP3 (128–192 kbps) oder WAV für beste Qualität.  
5. Dauer: 60–75 Sekunden sind ideal für einen Pitch.

Datei ins Repository legen:

1. Speichern Sie die Audiodatei als `pitch/pitch.mp3`.  
2. Fügen Sie die Datei dem Git‑Repo hinzu und committen Sie sie:

```powershell
git add pitch/pitch.mp3 pitch/script.md
git commit -m "Add pitch audio and script"
git push
```

Hinweis zur Dateigröße: Kleine Audio‑Dateien (<25 MB) können direkt im Repo liegen. Größere Dateien sollten extern (z. B. S3 oder GitHub Releases) gehostet werden und in `pitch/README.md` verlinkt werden.

Wenn Sie möchten, kann ich eine einfache Änderung in `recommendation-api` vorschlagen, damit `/pitch/pitch.mp3` über die API erreichbar wird. Sagen Sie mir Bescheid.

