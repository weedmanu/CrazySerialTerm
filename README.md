# CrazySerialTerm

CrazySerialTerm est un terminal série graphique moderne pour Windows, développé en Python avec PyQt5. Il permet d’envoyer et recevoir des commandes AT, d’afficher les réponses, et de personnaliser l’apparence de l’interface.

## Fonctionnalités principales

- Envoi et réception de commandes AT (ESP, Bluetooth, etc.)
- Affichage des réponses dans différents formats (ASCII, HEX)
- Interface graphique personnalisable (menu Apparence)
- Sauvegarde des commandes utilisées
- Icône personnalisée
- Création d’un exécutable Windows (.exe) sans console
- Ajout automatique de raccourcis sur le Bureau et dans le menu Démarrer

## Fichiers du projet

- `CrazySerialTerm.py` : Fichier principal, lance l’application.
- `config.py` : Paramètres de configuration (baudrate, thèmes, etc.).
- `esp_at_commands.py` et `bt_at_commands.py` : Listes de commandes AT pour ESP et Bluetooth.
- `LogoFreeTermIco.ico` : Icône de l’application.
- `README.md` : Ce fichier d’explications.
- `requirements.txt` : Dépendances Python du projet.
- `build_exe/` : Scripts et fichiers pour la création du build (.exe).

---

## Installation du programme Python

1. **Installer Python 3.8+** (https://www.python.org/downloads/)
2. **Installer le programme et ses dépendances** :
   - Ouvrez un terminal dans le dossier du projet
   - Lancez :
     ```powershell
     python install.py
     ```
   - Le script crée un environnement virtuel `.venv` et installe toutes les dépendances nécessaires.
3. **Lancer le programme** :
   - Activez le venv :
     ```powershell
     .\.venv\Scripts\activate
     ```
   - Lancez l’application :
     ```powershell
     python CrazySerialTerm.py
     ```

---

## Création d’un exécutable Windows (.exe)

1. **Pré-requis** : Avoir installé le programme et ses dépendances via `install.py`.
2. **Générer le build** :
   - Activez le venv :
     ```powershell
     .\.venv\Scripts\activate
     ```
   - Lancez le script de build :
     ```powershell
     python build_exe\build_exe.py
     ```
   - Le script purge les caches, installe PyInstaller, génère le .exe sans console, et crée les raccourcis sur le Bureau et dans le menu Démarrer.
3. **Résultat** :
   - Le fichier `.exe` se trouve dans `build_exe/dist/CrazySerialTerm.exe`
   - Les raccourcis sont créés automatiquement

---

## Désinstallation du build

Pour supprimer l’exécutable, les raccourcis, le dossier `dist` et l’environnement virtuel `.venv`, lancez :

```powershell
python build_exe\uninstall.py
```

> **Attention** :  
> Le script ne peut pas supprimer `.venv` si vous êtes encore dans l’environnement virtuel.  
> Désactivez-le d’abord avec `deactivate` ou fermez le terminal avant de relancer la désinstallation.

---

## Conseils et dépannage

- Si une dépendance manque, relancez `install.py`.
- Si le build échoue, vérifiez que le venv est bien activé et que tous les fichiers nécessaires sont présents.
- Pour un build propre, le script supprime automatiquement les fichiers temporaires et caches.
- Si la suppression de `.venv` échoue, quittez l’environnement virtuel puis relancez la suppression.

---

## Auteur

weedmanu

## Licence

Ce projet est open source.
