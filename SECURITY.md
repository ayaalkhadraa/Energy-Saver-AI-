# 🔒 Sicherheitshinweise für API-Keys

## ⚠️ WICHTIGER SICHERHEITSHINWEIS

Der API-Key wurde aus dem Code entfernt und muss nun über Umgebungsvariablen gesetzt werden.

## Setup für lokale Entwicklung

1. Kopieren Sie `.env.example` zu `.env`:
   ```bash
   cp .env.example .env
   ```

2. Bearbeiten Sie `.env` und setzen Sie Ihren echten OpenAI API-Key:
   ```
   OPENAI_API_KEY=ihr_echter_api_key_hier
   ```

## Produktionsumgebung

- Setzen Sie Umgebungsvariablen über Ihr Deployment-System
- Verwenden Sie Secrets Management (Docker Secrets, Kubernetes Secrets, etc.)
- **NIEMALS** API-Keys direkt im Code oder in öffentlichen Repositories

## Docker Compose

Für Docker verwenden Sie eine `.env` Datei oder setzen die Variablen direkt:

```yaml
environment:
  - OPENAI_API_KEY=${OPENAI_API_KEY}
```

## Kubernetes

Erstellen Sie Secrets:

```bash
kubectl create secret generic openai-secret --from-literal=OPENAI_API_KEY="ihr-key"
```

## 🚨 Was zu tun ist, wenn ein API-Key kompromittiert wurde:

1. **Sofort den API-Key bei OpenAI widerrufen/erneuern**
2. **Git History bereinigen (siehe unten)**
3. **Neue Keys über sichere Kanäle verteilen**

## Git History Bereinigung

Falls der Key bereits in Git eingecheckt wurde:

### Option 1: BFG Repo Cleaner (empfohlen)
```bash
# BFG installieren und verwenden
java -jar bfg.jar --replace-text passwords.txt
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

### Option 2: Git Filter-Repo
```bash
git filter-repo --replace-text <(echo "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==>***REMOVED***")
```

### Option 3: Neues Repository (falls andere Optionen nicht funktionieren)
```bash
# Backup des aktuellen Zustands
cp -r . ../backup-clean
# Neues Repo erstellen und saubere Files hinzufügen
git init
git add .
git commit -m "Initial commit - API keys removed"
```

## Best Practices

✅ **Richtig:**
- API-Keys in `.env` Dateien (die in `.gitignore` stehen)
- Verwendung von Secrets Management
- Regelmäßige Key-Rotation
- Umgebungsvariablen für Production

❌ **Falsch:**
- API-Keys im Quellcode
- Keys in Git History
- Sharing von Keys über unsichere Kanäle
- Default-Werte mit echten Keys