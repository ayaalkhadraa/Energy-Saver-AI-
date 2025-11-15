## Kubernetes Manifeste und Deploy-Anleitung

Dieser Ordner enthält grundlegende Kubernetes-Manifest-Templates für die beiden Services in diesem Repo:

- `recommendation-api` (API für Energiespartipps)
- `usage-sim-api` (Simulations-API für Verbrauchsdaten)

Enthaltene Dateien:

- `namespace.yaml` — Namespace `energy-saver-ai`
- `reco-deploy.yaml` — Deployment für `recommendation-api`
- `reco-svc.yaml` — ClusterIP Service für `recommendation-api`
- `usage-sim-deploy.yaml` — Deployment für `usage-sim-api`
- `usage-sim-svc.yaml` — ClusterIP Service für `usage-sim-api`

Wichtige Hinweise
- Ersetze in den Deployment-Templates `<your-registry>/...:tag` mit dem tatsächlichen Image-Namen/Tag, z.B. `ghcr.io/<user>/recommendation-api:1.0.0`.
- Setze Secrets (z.B. `OPENAI_API_KEY`) vor dem Anwenden der Manifeste.

Lokales Testen (minikube / k3d / kind)

1) Builden der Images lokal:

   # Beispiel für minikube: lade Image in minikube's Docker
   minikube start
   eval $(minikube -p minikube docker-env)
   docker build -t recommendation-api:local -f recommendation-api/Dockerfile recommendation-api
   docker build -t usage-sim-api:local -f usage-sim-api/Dockerfile usage-sim-api

   # Dann in den YAML-Dateien image: recommendation-api:local (oder nutze imagePullPolicy: Never)

2) Namespace erstellen und Manifeste anwenden:

   kubectl apply -f k8s/namespace.yaml
   # (Optional) Setze Secret für OPENAI_API_KEY
   kubectl -n energy-saver-ai create secret generic openai-secret --from-literal=OPENAI_API_KEY="<your-key>"

   kubectl apply -n energy-saver-ai -f k8s/reco-deploy.yaml
   kubectl apply -n energy-saver-ai -f k8s/reco-svc.yaml
   kubectl apply -n energy-saver-ai -f k8s/usage-sim-deploy.yaml
   kubectl apply -n energy-saver-ai -f k8s/usage-sim-svc.yaml

3) Testen

   # Pods prüfen
   kubectl -n energy-saver-ai get pods

   # Port-Forward zum Testen (lokal)
   kubectl -n energy-saver-ai port-forward svc/recommendation-api-svc 8080:80
   # Dann: http POST localhost:8080/tips ...

Weiterführende Schritte (empfohlen)
- Erstelle ein Secret-Manifest (keine Keys im Repo). Nutze External Secrets / SealedSecrets für produktive Umgebungen.
- Ingress: Erstelle ein Ingress-Manifest (oder Traefik/NGINX Ingress Controller) um externen Zugriff zu erlauben.
- HorizontalPodAutoscaler: Skaliere `recommendation-api` nach CPU oder benutzerdefinierten Metriken.
- PodDisruptionBudget: Schütze Verfügbarkeit während Wartungen.
- RBAC: Falls dein Cluster restriktiv ist, füge ServiceAccounts/Roles hinzu.
- Helm: Wenn du mehrere Umgebungen (dev/stage/prod) brauchst, scaffolde ein Helm-Chart.

Wenn du willst, kann ich jetzt:

1. Die Manifeste weiter verbessern (Ingress, HPA, Secrets-Manifest).
2. Ein Beispiel-Secret-Manifest mit Platzhaltern erstellen.
3. Ein kleines Helm-Chart scaffolden.

Sag mir, welche Option du bevorzugst — ich setze es dann direkt um.
