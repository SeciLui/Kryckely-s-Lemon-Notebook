# Kanban Ideas

Kanban Ideas est une application de bureau Tkinter pensée pour organiser, tester et
archiver des idées créatives. Chaque idée vit dans un dossier dédié qui peut contenir
plusieurs fichiers audio, une transcription et vos propres notes d’analyse.

L’interface propose un tableau Kanban avec six colonnes (« Inbox », « À tester »,
« En test », « À analyser », « Best-of », « Kill ») ainsi qu’un panneau de détails
pour modifier les métadonnées, lancer une transcription via un outil CLI externe et
stocker manuellement vos analyses.

## Structure du projet

```
.
├── pyproject.toml       # Métadonnées du projet et entrée console `kanban-ideas`
├── requirements.txt     # Dépendances (facultatif)
├── tasks.py             # Tâches Invoke pour installer et lancer l’app
├── data/
│   └── ideas/           # Workspace persistant des idées
└── src/
    └── kanban_ideas/
        ├── __init__.py
        ├── __main__.py  # Permet `python -m kanban_ideas`
        ├── app.py       # Point d’entrée haut niveau
        ├── config.py    # Constantes (statuts, dossiers, CLI par défaut)
        ├── gui.py       # Interface Tkinter
        ├── models.py    # Modèle de données `Idea`
        ├── services.py  # Fonctions longues (transcription, sous-processus)
        └── storage.py   # Lecture / écriture des fichiers du workspace
```

Cette architecture sépare clairement les responsabilités (UI, modèle, persistance,
services), ce qui facilite les évolutions futures.

## Workspace généré

Chaque idée est sauvegardée dans `data/ideas/` avec la hiérarchie
suivante :

```
<workspace>/
└── <horodatage>_<id>_<slug>/
    ├── idea.json        # Métadonnées (titre, statut, tags, audio)
    ├── transcript.txt   # Transcription générée par la CLI (optionnel)
    ├── analysis.json    # Notes d’analyse écrites manuellement
    └── audio/
        └── *.wav|*.mp3  # Fichiers audio copiés dans le workspace
```

## Prérequis

* Python 3.10 ou supérieur
* Un outil de transcription CLI optionnel (ex. `vibe`, `whisper`) disponible dans le
  `PATH` si vous souhaitez utiliser la fonction « Transcrire ».
* (Optionnel) [Invoke](https://www.pyinvoke.org/) pour profiter des tâches automatisées.

## Installation rapide

```bash
python -m venv .venv
source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt  # Facultatif
pip install -e .
```

## Commandes Invoke

Les tâches se trouvent dans `tasks.py` :

```bash
invoke install   # Crée l’environnement virtuel local et installe le projet
invoke run       # Lance l’application (équivalent à `python -m kanban_ideas`)
invoke lint      # Exécute Ruff si l’outil est disponible dans la venv
kanban-ideas --spec-report  # Affiche la complétude des fiches idées selon le cahier des charges
kanban-ideas --spec-report --spec-report-format json   # Version JSON pour automatiser le suivi
kanban-ideas --spec-report --spec-report-format stats  # Tableau de bord agrégé (JSON)
```

## Fonctionnalités principales

* **Gestion Kanban** : glissez mentalement vos idées entre six statuts et modifiez
  les métadonnées (catégorie, tags, etc.). Les champs multi-lignes respectent les
  bornes du cahier des charges (≤3 contextes, ≤6 tags, 1–3 next actions, 1–2
  dialogues d’exemple).
* **Import audio** : ajoutez un ou plusieurs fichiers audio qui seront copiés dans
  le workspace de l’idée.
* **Transcription** : déclenchez Vibe pour transcrire le dernier audio importé
  (pensez à configurer les variables d’environnement décrites ci-dessous).
* **Analyse manuelle** : saisissez vos conclusions directement dans l’onglet Analyse
  et sauvegardez-les localement (aucun appel OpenAI n’est effectué).
* **Recherche** : filtrez les idées via la barre de recherche qui balaye titres,
  tags, transcriptions et analyses.

## Personnalisation

### Transcription avec Vibe

L’application attend la CLI Vibe et un modèle Whisper compatible. Configurez les
variables d’environnement suivantes :

* `VIBE_CLI` : chemin vers l’exécutable `vibe` (optionnel si présent dans le `PATH`).
* `VIBE_MODEL_PATH` : chemin (absolu ou relatif) vers le fichier `.bin` du modèle
  Whisper téléchargé via Vibe.
* `VIBE_LANGUAGE` : langue cible (par défaut : `french`).
* `VIBE_THREADS` : nombre de threads à utiliser (optionnel).
* `VIBE_TEMPERATURE` : température appliquée lors de la transcription (optionnel).

Les chemins relatifs sont résolus depuis le répertoire courant, la racine du projet
ou `data/`. Vous pouvez également ajuster la liste des statuts ou le titre de
l’application dans `src/kanban_ideas/config.py`.

## Tests

Aucun test automatisé n’est fourni pour l’instant. Ajoutez vos propres tests sous
`tests/` si nécessaire.
