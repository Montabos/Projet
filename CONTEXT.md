# Multi-Agent Email & Task Automation Assistant

## 📋 Vue d'ensemble du projet

**Objectif** : Construire un assistant multi-agents qui automatise la rédaction d'emails professionnels avec récupération de contexte interne/externe et validation humaine avant envoi.

**Type de projet** : Projet B — Multi-Agent Email & Task Automation Assistant

**Contexte pédagogique** : Projet final pour le cours AgenticAI — Multi-Agent AI Systems

---

## 🎯 Exigences du projet

### Exigences spécifiques (Projet B)
- ✅ Multi-agent system (intent classifier, retriever, drafter, safety reviewer)
- ✅ Routing logic dynamique entre agents
- ✅ Vector DB pour récupération de connaissances organisationnelles
- ✅ Agent externe avec recherche web/API
- ✅ Human-in-the-loop : validation/édition avant envoi
- ✅ Persistence avec SqliteSaver
- ✅ Langfuse monitoring (traces + spans)

### Exigences universelles
- ✅ Planner/Router agent avec décisions de routing dynamiques
- ✅ Au moins une base de données vectorielle pour RAG
- ✅ Au moins un agent d'outil externe (web/API)
- ✅ Interruption et reprise human-in-the-loop
- ✅ Persistence avec SqliteSaver
- ✅ Langfuse monitoring (trace + spans)
- ✅ Extensibilité pour d'autres cas d'usage

---

## 🏗️ Architecture du système

### Flow principal

```
User Input → Intent Classifier → [Routing] → Retrieval Agent → [Optional: Web Search] → Drafter → Safety Reviewer → Human Approval → Final Email
```

### Détail du workflow

1. **Intent Classifier** : analyse la demande utilisateur
   - `REPLY_EMAIL` → répondre à un email existant
   - `NEW_EMAIL` → créer un nouveau mail from scratch
   - `SUMMARIZE_THREAD` → résumer une conversation

2. **Retrieval Agent** : récupère le contexte depuis la **vector DB de conversations email**
   - Emails précédents du thread
   - Messages de la conversation avec une personne
   - Contexte professionnel (projets, demandes, décisions)

3. **Web Search Agent** (conditionnel) : recherche externe si nécessaire
   - Détecte si des informations **externes et récentes** sont nécessaires (news, contexte marché, infos publiques)
   - Utilise l’API Tavily
   - Enrichit le contexte avec un bloc `--- External Information ---`

4. **Drafter Agent** : rédige le contenu
   - Email de réponse (REPLY_EMAIL)
   - Email complet (NEW_EMAIL)
   - Résumé structuré (SUMMARIZE_THREAD)
   - Utilise à la fois :
     - le contexte interne (conversations email)
     - et, si présent, les infos issues de la recherche web

5. **Safety Reviewer** : vérifie la qualité et conformité
   - Ton professionnel
   - Cohérence avec la demande utilisateur
   - Absence d’erreurs majeures
   - Absence d’informations sensibles
   - Si problème → renvoie vers le Drafter avec des issues/suggestions

6. **Human-in-the-loop** : validation utilisateur
   - Affiche le draft (`/show`) avec :
     - `INTENT`, `SUBJECT`, `BODY`
     - `REVIEW STATUS`, `Issues`, `Suggestions`
   - L’utilisateur peut :
     - **valider** (`/approve`)
     - **modifier** le texte (`/edit <texte>`, puis review relancée automatiquement)
     - **reprendre** (`/resume`)

7. **Persistence & Monitoring** : enregistrement et traçabilité
   - État sauvegardé dans SQLite (`email_agent.db`) par `thread_id`
   - Traces complètes dans Langfuse (graph, nœuds, prompts, sorties)

---

## 🤖 Agents et responsabilités

### 1. Intent Classifier Agent
**Rôle** : Classifier l'intention de l'utilisateur et router vers le bon workflow

**Input** : Message utilisateur (string)

**Output** : 
- `intent`: `REPLY_EMAIL` | `NEW_EMAIL` | `SUMMARIZE_THREAD`
- `confidence`: float
- `context_needed`: dict (informations extraites)

**Routing** :
- `REPLY_EMAIL` → Retrieval Agent (avec thread_id)
- `NEW_EMAIL` → Retrieval Agent (sans thread_id)
- `SUMMARIZE_THREAD` → Retrieval Agent (avec thread_id)

### 2. Retrieval Agent
**Rôle** : Récupérer le contexte pertinent depuis la vector DB

**Input** : 
- `intent`: type d'intention
- `query`: requête de recherche
- `thread_id`: (optionnel) ID du thread email

**Output** :
- `retrieved_docs`: list de documents pertinents
- `context`: string concaténé
- `needs_web_search`: bool (si contexte externe nécessaire)

**Actions** :
- Recherche vectorielle dans la DB
- Récupération des emails du thread
- Récupération des templates pertinents
- Décision si recherche web nécessaire

### 3. Web Search Agent
**Rôle** : Compléter le contexte avec des informations externes

**Input** :
- `search_query`: requête de recherche
- `current_context`: contexte déjà récupéré

**Output** :
- `web_results`: résultats de recherche
- `summarized_info`: résumé des infos externes
- `enhanced_context`: contexte enrichi

**Tool utilisé** : Tavily Search API

### 4. Drafter Agent
**Rôle** : Rédiger le contenu final (email ou résumé)

**Input** :
- `intent`: type d'intention
- `context`: contexte complet (interne + externe)
- `user_instruction`: instruction originale

**Output** :
- `draft`: contenu rédigé
- `metadata`: métadonnées (sujet, destinataires, etc.)

**Adaptation selon intent** :
- `REPLY_EMAIL`: réponse contextuelle au thread
- `NEW_EMAIL`: email complet avec structure
- `SUMMARIZE_THREAD`: résumé structuré

### 5. Safety Reviewer Agent
**Rôle** : Vérifier qualité, conformité et sécurité

**Input** :
- `draft`: contenu à vérifier
- `intent`: intention originale
- `context`: contexte utilisé

**Output** :
- `approved`: bool
- `issues`: list de problèmes détectés
- `suggestions`: suggestions d'amélioration
- `revised_draft`: (optionnel) version corrigée

**Vérifications** :
- Ton professionnel approprié
- Cohérence avec le contexte
- Absence d'erreurs grammaticales/orthographiques
- Conformité à la demande utilisateur
- Détection de données sensibles (PII, secrets)
- Longueur et structure appropriées

**Routing** :
- Si `approved == True` → Human Approval
- Si `approved == False` → Retour au Drafter avec suggestions

---

## 📊 État du système (State)

### AgentState (TypedDict)

```python
class EmailAgentState(TypedDict, total=False):
    # Input utilisateur
    user_input: str
    thread_id: Optional[str]
    
    # Classification
    intent: str  # REPLY_EMAIL | NEW_EMAIL | SUMMARIZE_THREAD
    intent_confidence: float
    
    # Retrieval
    retrieved_docs: List[Document]
    context: str
    needs_web_search: bool
    
    # Web search
    web_results: List[Dict]
    enhanced_context: str
    
    # Drafting
    draft: str
    draft_metadata: Dict[str, Any]
    
    # Review
    review_approved: bool
    review_issues: List[str]
    review_suggestions: List[str]
    
    # Human interaction
    human_feedback: Optional[str]
    human_approved: bool
    final_email: Optional[str]
    
    # Tracking
    history: List[str]
    step_count: int
```

---

## 🛠️ Technologies et dépendances

### Core
- **LangGraph** : Construction du workflow multi-agents
- **LangChain** : Intégration LLM et outils
- **OpenAI** : ChatOpenAI (gpt-4o-mini ou gpt-5)

### Vector Database
- **ChromaDB** ou **FAISS** : Base vectorielle pour RAG
- **LangChain Vector Stores** : Intégration

### External Tools
- **Tavily Search** : Recherche web
- **LangChain Tools** : Wrapping des outils

### Persistence
- **SqliteSaver** : Sauvegarde d'état (langgraph-checkpoint-sqlite)
- **SQLite** : Base de données locale

### Monitoring
- **Langfuse** : Observabilité et traçage
- **langfuse-langchain** : Intégration LangChain

### Utilitaires
- **python-dotenv** : Variables d'environnement
- **TypedDict** : Typage des états

---

## 📁 Structure du code (inspirée des exemples du prof)

```
Projet/
├── utils.py                 # Fonctions utilitaires, état, nœuds (agents), workflow LangGraph
├── build_agent.py           # Construction du graph principal (LLM, RAG, outils, Langfuse)
├── email_agent_chat.py      # Interface CLI interactive
├── vector_db.py             # Setup et gestion de la vector DB (indexation des conversations email)
├── tools.py                 # Définition des outils (web search Tavily)
├── vector_data/             # Conversations email (.md) – 1 fichier = 1 thread
├── .env                     # Variables d'environnement
├── requirements.txt         # Dépendances
├── CONTEXT.md               # Ce fichier
└── README.md                # Documentation utilisateur
```

### Détail des fichiers

#### `utils.py`
- Définition de `EmailAgentState` (TypedDict)
- Fonction `make_llm()` : initialisation du LLM
- Fonctions de nœuds : `intent_classifier_node`, `retrieval_node`, `web_search_node`, `drafter_node`, `reviewer_node`
- Fonction `build_workflow()` : construction du StateGraph
- Fonction `get_checkpointer()` : context manager pour SqliteSaver

#### `build_agent.py`
- Fonction principale `build_email_agent()` : compile le graph avec checkpointer
- Configuration Langfuse
- Retourne l'agent compilé

#### `email_agent_chat.py`
- Interface CLI interactive
- Commandes : `/new`, `/resume`, `/show`, `/approve`, `/edit`, `/help`, `/exit`
- Gestion des threads et persistence
- Affichage des drafts pour validation

#### `vector_db.py`
- Initialisation de la vector DB (Chroma)
- Chargement des conversations email depuis `vector_data/`
- Création/chargement de l’index vectoriel
- Gestion des embeddings OpenAI

#### `tools.py`
- Définition de l’outil de recherche web Tavily (`web_search`)

---

## 🔄 Flow détaillé avec routing

### Flow 1 : REPLY_EMAIL

```
START
  ↓
Intent Classifier
  ↓ (intent = REPLY_EMAIL)
Retrieval Agent (avec thread_id)
  ↓
[Condition: needs_web_search?]
  ├─ OUI → Web Search Agent → Enhanced Context
  └─ NON → Continue
  ↓
Drafter Agent (mode reply)
  ↓
Safety Reviewer
  ├─ Approved → Human Approval
  └─ Not Approved → Drafter (avec feedback)
  ↓
Human Approval
  ├─ Approved → Send & Log → END
  └─ Needs Edit → Drafter (avec modifications)
```

### Flow 2 : NEW_EMAIL

```
START
  ↓
Intent Classifier
  ↓ (intent = NEW_EMAIL)
Retrieval Agent (templates, docs)
  ↓
[Condition: needs_web_search?]
  ├─ OUI → Web Search Agent
  └─ NON → Continue
  ↓
Drafter Agent (mode new)
  ↓
Safety Reviewer
  ├─ Approved → Human Approval
  └─ Not Approved → Drafter
  ↓
Human Approval → Send & Log → END
```

### Flow 3 : SUMMARIZE_THREAD

```
START
  ↓
Intent Classifier
  ↓ (intent = SUMMARIZE_THREAD)
Retrieval Agent (tout le thread)
  ↓
Drafter Agent (mode summarize)
  ↓
Safety Reviewer
  ├─ Approved → Human Approval
  └─ Not Approved → Drafter
  ↓
Human Approval → Display Summary → END
```

---

## 🎛️ Points d'interruption (Human-in-the-loop)

### Interruptions configurées

1. **Après Safety Reviewer** : Toujours interrompre pour validation humaine
   ```python
   interrupt_after=["reviewer"]
   ```

2. **Après modifications utilisateur** : Reprendre depuis le Drafter

3. **Avant envoi final** : Dernière confirmation

### Gestion des interruptions

- État sauvegardé automatiquement après chaque nœud
- Possibilité de reprendre avec `/resume`
- Affichage de l'état actuel avec `/show`
- Modification avec `/edit <nouveau_contenu>`

---

## 📈 Langfuse Monitoring

### Traces à capturer

1. **Intent Classification**
   - Input utilisateur
   - Intent détecté + confidence
   - Temps d'exécution

2. **Retrieval**
   - Query de recherche
   - Nombre de documents récupérés
   - Score de similarité

3. **Web Search** (si activé)
   - Query de recherche
   - Nombre de résultats
   - Temps de recherche

4. **Drafting**
   - Intent utilisé
   - Longueur du draft
   - Temps de génération

5. **Review**
   - Issues détectées
   - Approved/Not approved
   - Suggestions générées

6. **Human Interaction**
   - Actions utilisateur (approve/edit/reject)
   - Temps de réponse

7. **Final Output**
   - Email final envoyé
   - Métadonnées complètes

### Configuration Langfuse

```python
from langfuse import Langfuse
from langfuse.decorators import langfuse_context

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)
```

---

## ✅ Checklist de développement

### Phase 1 : Setup de base
- [ ] Structure de fichiers créée
- [ ] Dépendances installées (requirements.txt)
- [ ] Variables d'environnement configurées (.env)
- [ ] État TypedDict défini (EmailAgentState)
- [ ] LLM initialisé (make_llm)

### Phase 2 : Agents de base
- [ ] Intent Classifier Node
- [ ] Retrieval Node
- [ ] Drafter Node
- [ ] Safety Reviewer Node

### Phase 3 : Intégrations
- [ ] Vector DB setup (ChromaDB/FAISS)
- [ ] Chargement de documents dans vector DB
- [ ] Web Search Agent (Tavily)
- [ ] Routing conditionnel implémenté

### Phase 4 : Workflow
- [ ] StateGraph construit avec tous les nœuds
- [ ] Edges et conditional edges configurés
- [ ] Interruptions configurées
- [ ] Workflow testé end-to-end

### Phase 5 : Persistence
- [ ] SqliteSaver intégré
- [ ] Checkpointer fonctionnel
- [ ] Test de reprise de session
- [ ] Gestion des thread_id

### Phase 6 : Human-in-the-loop
- [ ] Interface CLI interactive
- [ ] Commandes implémentées (/new, /resume, /show, /approve, /edit)
- [ ] Affichage des drafts
- [ ] Gestion des modifications utilisateur

### Phase 7 : Monitoring
- [ ] Langfuse configuré
- [ ] Traces pour chaque agent
- [ ] Spans pour les sous-opérations
- [ ] Dashboard Langfuse vérifié

### Phase 8 : Tests et polish
- [ ] Tests avec les 3 types d'intentions
- [ ] Test de recherche web conditionnelle
- [ ] Test de reprise après interruption
- [ ] Documentation utilisateur (README.md)
- [ ] Diagramme d'architecture

---

## 🔑 Points clés à retenir

1. **Style du prof** : Suivre les patterns des exemples (utils.py, build_agent.py, etc.)
2. **Simplicité** : Garder le code lisible et modulaire
3. **Extensibilité** : Facile d'ajouter de nouveaux agents ou intentions
4. **Persistence** : Toujours utiliser SqliteSaver pour les sessions
5. **Monitoring** : Tracer chaque étape dans Langfuse
6. **Human-in-the-loop** : Toujours interrompre avant envoi final

---

## 📝 Notes de développement

### Variables d'environnement nécessaires

```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Modèle LLM recommandé

- **Développement** : `gpt-4o-mini` (rapide, économique)
- **Production** : `gpt-4o` ou `gpt-5` (meilleure qualité)

### Base de données

- **Vector DB** : ChromaDB (simple, local) ou FAISS
- **Persistence** : SQLite (`email_agent.db`)

---

## 🎯 Objectifs de démo

Pour la présentation, le système doit démontrer :

1. **Multi-agent routing** : Montrer le classifier qui route vers différents chemins
2. **Vector retrieval** : Afficher les documents récupérés avec scores
3. **Web search** : Montrer quand et comment la recherche web est déclenchée
4. **Human approval** : Interface interactive avec validation/modification
5. **Persistence** : Reprendre une session interrompue
6. **Langfuse** : Dashboard montrant toutes les traces et spans

---

**Dernière mise à jour** : [Date]
**Version** : 1.0

