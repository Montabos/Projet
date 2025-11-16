# Multi-Agent Email & Task Automation Assistant

Assistant multi-agents (LangGraph) pour **rédiger des emails professionnels** en utilisant :
- votre **historique de conversations email** (RAG),
- de la **recherche web** ciblée (Tavily),
- un **LLM OpenAI**,
- une boucle **human-in-the-loop**,
- et du **monitoring Langfuse**.

---

## 🎯 Fonctionnalités

- **Multi-agent (LangGraph)** :
  - `Intent Classifier` : détecte si l’utilisateur veut répondre (`REPLY_EMAIL`), créer un nouvel email (`NEW_EMAIL`) ou résumer une conversation (`SUMMARIZE_THREAD`).
  - `Retrieval Agent` : va chercher le contexte dans une **base vectorielle de conversations email** (RAG).
  - `Web Search Agent` : décide et exécute une recherche web via **Tavily** quand des infos externes sont nécessaires (news, contexte public, infos marché).
  - `Drafter Agent` : rédige l’email complet (sujet + corps) à partir du contexte interne + externe.
  - `Reviewer Agent` : vérifie ton, qualité, cohérence, sensibilité, et fournit des issues/suggestions.

- **RAG sur conversations email** :
  - Les fichiers `.md` dans `data/vector_data/` représentent **des threads d’emails réels** (1 fichier = 1 échange complet avec une personne).
  - Lorsqu’on rédige un mail, l’agent retrouve les conversations passées pertinentes pour enrichir le texte.

- **Recherche web (Tavily)** :
  - Le LLM décide, via un prompt dédié, si une recherche web est nécessaire.
  - Il génère une requête optimisée, nettoyée (sans année figée), pour trouver des infos récentes.
  - Le contexte externe est injecté dans l’état sous un bloc `--- External Information ---`.

- **Human-in-the-loop** :
  - L’agent s’arrête **après la review**.
  - Tu vois le draft, le statut de review, les issues/suggestions.
  - Tu peux **éditer** (`/edit`) le texte, puis la review est relancée automatiquement.
  - Tu gardes le dernier mot (`/approve`) avant l’envoi.

- **Persistence (SqliteSaver)** :
  - Chaque exécution est liée à un `thread_id`.
  - L’état (messages, intent, contexte, draft, review, etc.) est sauvegardé dans `artifacts/email_agent.db`.

- **Monitoring (Langfuse)** :
  - Toutes les étapes (intent, retrieval, web search, drafting, review) peuvent être tracées dans Langfuse.
  - Permet d’analyser le comportement de l’agent, les prompts, les réponses, les temps, etc.

---

## 📋 Prérequis

- Python **3.9+**
- Clés API :
  - `OPENAI_API_KEY` (**requis**) – LLM OpenAI.
  - `TAVILY_API_KEY` (*optionnel mais recommandé*) – recherche web.
  - `LANGFUSE_PUBLIC_KEY` & `LANGFUSE_SECRET_KEY` (*optionnel*) – monitoring.

---

## ⚙️ Installation

1. **Cloner le dépôt**

```bash
git clone https://github.com/<ton-compte>/<nom-du-repo>.git
cd <nom-du-repo>
```

2. **Créer un environnement virtuel (recommandé)**

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

3. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

4. **Configurer les variables d’environnement**

Créer un fichier `.env` à la racine :

```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LANGFUSE_PUBLIC_KEY=pk-...     # optionnel
LANGFUSE_SECRET_KEY=sk-...     # optionnel
LANGFUSE_HOST=https://cloud.langfuse.com
```

5. **Préparer les données vectorielles**

- Les fichiers `.md` dans `data/vector_data/` représentent **des threads d’emails** (ex : Mathias, Sophie, Mme Rossi).
- Ils sont automatiquement indexés dans la base vectorielle (Chroma) au premier lancement.
- Tu peux ajouter tes propres conversations (format texte/markdown).

---

## 💻 Utilisation (CLI)

### Lancer l’agent

Depuis la racine du projet :

```bash
python -m src.email_agent_chat
```

### Commandes disponibles

- **`/new <instruction>`** – démarrer une nouvelle tâche email
  - Exemple : `/new Reply to this email confirming the meeting`
  - Exemple : `/new Write an email to thank a client for their business`
  - Exemple : `/new Ecris un mail à Sophie pour faire un point sur le plan Q4`

- **`/show`** – afficher l’état courant
  - Affiche :
    - `[INTENT]`
    - `[SUBJECT]`
    - `[BODY]`
    - `[REVIEW STATUS]` + Issues + Suggestions
    - `[HISTORY]`
    - `[AVAILABLE ACTIONS]` (`/approve`, `/edit`, `/resume`, …)

- **`/edit <nouveau texte>`** – modifier le draft
  - Met à jour le texte dans l’état.
  - Relance automatiquement la review (`Reviewer Agent`) sur le nouveau contenu.

- **`/approve`** – approuver l’email final
  - Affiche l’email final.
  - Marque l’état comme approuvé côté agent (dans une vraie app : envoi).

- **`/resume`** – reprendre le graph (si interrompu).

- **`/intent`** – afficher l’intention détectée.

- **`/id`** – afficher le `thread_id` courant.

- **`/help`**, **`/exit`** – aide / quitter.

---

## 🧠 Architecture Agentique (LangGraph)

### Flow principal

```text
User Input
  ↓
Intent Classifier (agent)
  ↓
Retrieval Agent (RAG sur conversations email)
  ↓  (si besoin de contexte externe ?)
[Web Search Agent (Tavily)]
  ↓
Drafter Agent (rédige l’email)
  ↓
Reviewer Agent (safety / qualité)
  ↓
Human Approval (CLI : /show, /edit, /approve)
```

### Rôle des briques techniques

- **LangGraph** : orchestre les nœuds (agents) et le routage conditionnel.
- **LangChain** : fournit les abstractions LLM, Tools, VectorStores.
- **Chroma (artifacts/chroma_db/)** : base vectorielle pour les conversations email.
- **Tavily** : outil de recherche web (news, infos récentes).
- **SQLite (artifacts/email_agent.db)** : persistence d’état entre exécutions.
- **Langfuse** : traces et observabilité (graph, prompts, latences, etc.).

---

## 📁 Structure du projet

```text
Projet/
├── src/
│   ├── __init__.py
│   ├── utils.py             # État, nœuds (agents), workflow LangGraph
│   ├── build_agent.py       # Construction de l'agent (LLM, RAG, outils, Langfuse)
│   ├── email_agent_chat.py  # Interface CLI (boucle utilisateur, commandes)
│   ├── vector_db.py         # Gestion de la base vectorielle (Chroma)
│   └── tools.py             # Outil externe de recherche web (Tavily)
├── data/
│   └── vector_data/         # Conversations email vectorisées (1 fichier = 1 thread)
├── artifacts/
│   ├── chroma_db/           # Index vectoriel Chroma (généré)
│   └── email_agent.db*      # Base SQLite de persistence (générée)
├── docs/
│   ├── README.md            # Guide d'utilisation détaillé
│   ├── CONTEXT.md           # Documentation technique (pour le cours AgenticAI)
│   ├── GUIDE_TEST.md        # Scénarios de test pour la démo
│   └── GUIDE_UTILISATION.md # Guide d’usage narratif
├── Exemples du prof/        # Matériel de référence du cours (non utilisé par l'agent)
├── requirements.txt         # Dépendances Python
├── .gitignore               # Ignore artifacts, .env, etc.
└── .env                     # Variables d'environnement (non versionné)
```

---

## 📄 Licence

Projet éducatif pour le cours **AgenticAI**.  
Libre d’être forké, adapté et étendu pour d’autres systèmes agentiques.


