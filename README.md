# CrazySerialTerm

Terminal de communication série avancé avec interface graphique pour la connexion et l'interaction avec des périphériques série.

## Description

CrazySerialTerm est un terminal série complet qui offre une interface graphique moderne et intuitive pour communiquer avec des périphériques via port série. Idéal pour les développeurs, les ingénieurs et les hobbyistes travaillant avec des microcontrôleurs, des modules radio, ou tout autre appareil utilisant une communication série.

## Fonctionnalités

- Interface graphique intuitive avec thèmes personnalisables (clair, sombre, hacker)
- Connexion à des ports série avec paramètres configurables
- Envoi et réception de données en formats ASCII et HEX
- Enregistrement des communications dans des fichiers log
- Historique des commandes avec navigation
- Commandes prédéfinies personnalisables et accessibles rapidement
- Filtrage des données reçues avec support des expressions régulières
- Affichage des timestamps et délais entre trames
- Outils intégrés : calculatrice de checksum et convertisseur ASCII/HEX
- Support des commandes AT ESP01 avec documentation intégrée
- Sections pliables/dépliables dans les paramètres avancés
- Gestion robuste des déconnexions USB inattendues

## Installation

### Prérequis

- Python 3.6 ou supérieur
- PyQt5
- pyserial

### Installation des dépendances

```bash
pip install PyQt5 pyserial
```


### Exécution

## Sans console

```bash
python CrazySerialTerm.pyw 
```

## Avec console

```bash
python CrazySerialTerm.py
```

## Structure du projet

- `CrazySerialTerm.pyw` : Script principal de l'application
- `config.py` : Configuration de l'application
- `serial_utils.py` : Utilitaires pour la communication série
- `observer.py` : Implémentation du pattern Observer pour la gestion des événements
- `checksum_calculator.py` : Module pour le calcul de checksums
- `data_converter.py` : Module pour la conversion de données
- `tests/` : Tests unitaires

## Utilisation

1. Lancez l'application
2. Sélectionnez le port série dans la liste déroulante
3. Configurez les paramètres de connexion (vitesse, bits de données, parité, etc.)
4. Cliquez sur "Connecter" pour établir la connexion
5. Utilisez le champ de saisie pour envoyer des commandes
6. Les données reçues s'affichent dans la zone de terminal

## Raccourcis clavier

- `Ctrl+K` : Connecter/Déconnecter
- `Ctrl+C` : Effacer le terminal
- `Ctrl+S` : Enregistrer le contenu du terminal
- `Ctrl+L` : Démarrer/Arrêter l'enregistrement
- `Ctrl+T` : Afficher/Masquer le panneau d'envoi
- Flèches haut/bas : Naviguer dans l'historique des commandes

## Licence

Ce logiciel est libre d'utilisation, de modification et de distribution sans restriction.

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou à soumettre une pull request.
