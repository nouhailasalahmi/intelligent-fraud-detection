# 🛡️ Système Autonome Multi-Agents de Détection et Réponse aux Fraudes Bancaires

Ce projet implémente une plateforme bancaire de surveillance en temps réel, combinant des modèles de Machine Learning (supervisé et non supervisé), une architecture multi-agents LLM (ReAct et collaboration d'experts), ainsi qu'un moteur de remédiation automatisée et de conformité réglementaire (DSP2, RGPD, rapports SAR Tracfin/ACPR).

---

## 🏛️ Architecture Globale du Système

```
+---------------------------------------------------------------------------------------------------+
|                                      PIPELINE ÉVÉNEMENTIEL KAFKA                                  |
|                                                                                                   |
|  [Producer] ---> Topic 'transactions' ---> [Consumer (Triage & Multi-Agents)]                      |
|                                                     |                                             |
|                                                     v                                             |
|                                            [ML Scoring (XGB+IF)]                                  |
|                                                     |                                             |
|                                                     v                                             |
|                                            [DSP2 Check (SCA/2FA)]                                 |
|                                                     |                                             |
|                                                     v                                             |
|                             +-----------------------------------------------+                     |
|                             |          SYSTÈME MULTI-AGENTS LLM             |                     |
|                             |                                               |                     |
|                             |   [InvestigatorAgent] <--> [tools.py / DB]    |                     |
|                             |             | (Facts JSON)                    |                     |
|                             |             v                                 |                     |
|                             |      [DecisionAgent]                          |                     |
|                             |             ^                                 |                     |
|                             |             | (Coordination / Pass 2)         |                     |
|                             |      [MultiAgentOrchestrator]                 |                     |
|                             +-----------------------------------------------+                     |
|                                                     |                                             |
|                                                     v                                             |
|                                      [determine_action(matrice)]                                  |
|                                                     |                                             |
|                                                     +---> Topic 'fraud-actions'                   |
|                                                                  |                                |
|                                                                  v                                |
|                                                      [Action Consumer Engine]                     |
|                                                       - BLOCK_CARD                                |
|                                                       - NOTIFY_CUSTOMER                           |
|                                                       - FLAG_FOR_REVIEW                           |
|                                                       - SAR Report (RGPD/Tracfin)                 |
|                                                       - Logs 'action_log' & 'audit_trail'         |
+---------------------------------------------------------------------------------------------------+
```

---

## 🧩 Les 3 Axes Majeurs Réalisés

### 1. 🤖 Système Multi-Agents Spécialisés (`LLM/agents/`)
- **`InvestigatorAgent`** :
  - Enquête factuelle autonome sans parti pris décisionnel.
  - Interroge dynamiquement les outils (`LLM/tools.py`) pour extraire l'historique étendu et le profilage de risque du client.
  - Produit un rapport factuel structuré (`anomalies_detected`, `risk_factors`, `mitigating_factors`, `factual_context`).
- **`DecisionAgent`** :
  - Juge impartial sans accès direct à la base de données.
  - Évalue les signaux ML (XGBoost + Isolation Forest) croisés avec le rapport de l'Investigateur et le statut DSP2.
  - Rend un verdict motivé avec score de confiance (`0.0` à `1.0`), justification textuelle et recommandation d'action.
- **`MultiAgentOrchestrator`** :
  - Supervise les échanges, gère une 2ᵉ passe d'enquête ciblée en cas d'incertitude (`confidence < 0.60`), et enregistre chaque étape dans la piste d'audit.

### 2. ⚡ Réponses Automatisées en Temps Réel (`kafka_pipeline/`, `compliance/actions.py`)
- **Topic Kafka dédié** : `fraud-actions`
- **Matrice Décision -> Action** :
  - `fraude` (confiance $\ge 0.85$) $\rightarrow$ **`BLOCK_CARD`** (Blocage immédiat carte + alerte Core Banking + SAR).
  - `fraude` ($0.60 \le \text{confiance} < 0.85$) $\rightarrow$ **`NOTIFY_CUSTOMER`** (Notification SMS/Push instantanée pour confirmation).
  - `incertain` ou confiance $< 0.60$ $\rightarrow$ **`FLAG_FOR_REVIEW`** (Escalade prioritaire Desk Analyste Fraude L2).
  - `legitime` $\rightarrow$ **`ALLOW`** (Autorisation sans restriction).
- **Consommateur d'actions (`action_consumer.py`)** :
  - Exécute les actions de remédiation en direct et historise chaque opération dans la table `action_log`.

### 3. 📜 Conformité Réglementaire Bancaire, Traçabilité & RGPD (`compliance/`, `db.py`)
- **Rapports SAR (Suspicious Activity Report / ACPR / Tracfin)** :
  - Génération automatique de rapports officiels structurés (JSON + Markdown dans `reports/`) pour toute fraude confirmée.
- **Vérification DSP2 / SCA** :
  - Contrôle automatique de l'Authentification Forte du Client (2FA) selon les règles et exemptions de la Directive sur les Services de Paiement.
- **Pseudonymisation RGPD** :
  - Hash cryptographique irréversible des identifiants clients (`CUST_HASH_...`) et masquage standardisé PCI-DSS des cartes (`**** **** **** 1234`).
- **Piste d'Audit Centralisée (`audit_trail`)** :
  - Traçabilité complète horodatée de l'ingestion à l'exécution de l'action (`ML_SCORING`, `INVESTIGATION`, `DECISION`, `ACTION_DISPATCHED`, `ACTION_EXECUTED`, `SAR_GENERATED`).

---

## 🚀 Démarrage et Exécution

### 1. Prérequis & Installation
```bash
# Installation des dépendances
pip install -r requirements.txt
```

### 2. Lancement des Tests Unitaires & d'Intégration
```bash
python -m unittest discover tests
```

### 3. Démarrage complet via Docker Compose
```bash
docker-compose up --build
```
Les conteneurs lancés :
- `data_base` : PostgreSQL (transactions, logs d'actions, audit trail, statuts cartes)
- `broker` : Apache Kafka en mode KRaft
- `kafka-ui` : Interface web Kafka sur `http://localhost:8080`
- `consumer` : Détection ML + Inférence Multi-Agents + Dispatch d'actions
- `action_consumer` : Exécution des actions automatisées et génération des SAR
- `producer` : Simulateur de flux de transactions bancaires temps réel

---

## 📁 Structure du Répertoire

```
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── config.py                     # Configuration centralisée & seuils
├── db.py                         # Gestion PostgreSQL (transactions, audit_trail, action_log)
│
├── compliance/                   # Module de conformité bancaire & réglementaire
│   ├── __init__.py
│   ├── actions.py                # Matrice décision -> action de remédiation
│   ├── dsp2.py                   # Vérification SCA / Exemptions DSP2
│   ├── rgpd.py                   # Pseudonymisation & masquage PCI-DSS
│   └── sar_generator.py          # Générateur officiel de rapports SAR / Tracfin
│
├── LLM/                          # Moteur d'intelligence agentique
│   ├── __init__.py
│   ├── factory.py                # Factory LLM (Ollama, Mistral, OpenAI, Anthropic)
│   ├── tools.py                  # Outils d'investigation de données
│   ├── agent.py                  # Agent ReAct legacy
│   ├── analyzer.py               # Analyseur LLM classique
│   └── agents/                   # Architecture Multi-Agents
│       ├── __init__.py
│       ├── investigator_agent.py # Agent Enquêteur (collecte des faits)
│       ├── decision_agent.py     # Agent Décideur (arbitrage & verdict)
│       └── orchestrator.py       # Orchestrateur & supervision
│
├── ML/                           # Modèles de détection de fraude
│   ├── fraud_detector.py         # Pipeline de prédiction XGBoost + Isolation Forest
│   └── models/                   # Pkl artefacts des modèles entraînés
│
├── kafka_pipeline/               # Pipeline de streaming temps réel
│   ├── producer.py               # Générateur de flux de transactions
│   ├── consumer.py               # Ingestion, ML, DSP2 & Multi-Agents
│   └── action_consumer.py        # Exécuteur des actions automatisées & SAR
│
├── entities/                     # Modélisation des données bancaires
│   ├── customers.py
│   └── transactions.py
│
├── reports/                      # Dossier de sortie des rapports SAR générés
└── tests/                        # Suite complète de tests unitaires et E2E
    ├── test_compliance.py
    ├── test_multi_agent.py
    └── test_end_to_end.py
```
