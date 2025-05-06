# Terminal de Communication Série Avancé

Ce projet est un terminal de communication série avancé, conçu pour faciliter les interactions avec des périphériques via des ports série. Il offre une interface graphique conviviale et des fonctionnalités puissantes pour les utilisateurs finaux et les développeurs.

---

## Fonctionnalités principales

- **Connexion série** : Sélectionnez un port série, configurez les paramètres (baudrate, bits de données, parité, etc.) et connectez-vous facilement.
- **Affichage des données** : Visualisez les données reçues en temps réel en ASCII, HEX ou les deux formats.
- **Envoi de données** : Envoyez des commandes en ASCII ou HEX avec des options de fin de ligne (NL, CR, NL+CR).
- **Outils intégrés** :
  - **Calculatrice de checksums** : Calculez des checksums (CRC8, CRC16, CRC32, MD5, SHA-1, SHA-256, etc.).
  - **Convertisseur de données** : Convertissez des données entre les formats ASCII et HEX.
- **Personnalisation** :
  - Thèmes (clair, sombre, hacker).
  - Options d'affichage (défilement automatique, timestamps, filtres).
- **Commandes prédéfinies** : Configurez des commandes fréquemment utilisées pour un accès rapide.
- **Enregistrement des logs** : Enregistrez les données reçues et envoyées dans un fichier texte.

---

## Options et paramètres

### Paramètres de connexion

- **Port série** : Sélectionnez le port série disponible sur votre système.
- **Baudrate** : Configurez la vitesse de communication (par exemple : 9600, 115200).
- **Bits de données** : Choisissez entre 5, 6, 7 ou 8 bits.
- **Parité** : Aucune, paire ou impaire.
- **Bits de stop** : 1, 1.5 ou 2 bits.
- **Contrôle de flux** : Aucun, XON/XOFF, RTS/CTS ou DSR/DTR.

### Options d'affichage

- **Format d'affichage** : ASCII, HEX ou les deux.
- **Défilement automatique** : Activez ou désactivez le défilement automatique des données reçues.
- **Timestamps** : Ajoutez un horodatage aux données reçues.
- **Filtres** : Appliquez un filtre (regex) pour afficher uniquement les données correspondantes.

### Outils intégrés

- **Calculatrice de checksums** : Permet de calculer des checksums pour les données saisies (CRC8, CRC16, CRC32, MD5, SHA-1, SHA-256, etc.).
- **Convertisseur de données** : Convertissez des données entre les formats ASCII et HEX.

### Commandes prédéfinies

- Configurez des commandes fréquemment utilisées pour un accès rapide dans l'interface.

### Enregistrement des logs

- Enregistrez les données reçues et envoyées dans un fichier texte pour une analyse ultérieure.

---

## Installation pour les utilisateurs finaux

### Utilisation du fichier `.exe`

1. Téléchargez le fichier exécutable `    CrazySerialTerm.exe` depuis le dossier `Programme .exe`.
2. Double-cliquez sur `    CrazySerialTerm.exe` pour lancer l'application.
3. Aucune installation supplémentaire n'est nécessaire. Toutes les dépendances sont incluses dans l'exécutable.

---

## Installation pour les développeurs

### Structure du projet

Le dossier `Programme .py` contient les fichiers source Python suivants :

- `    CrazySerialTerm.py` : Le fichier principal de l'application.
- `checksum_calculator.py` : Module pour la calculatrice de checksums.
- `data_converter.py` : Module pour le convertisseur de données.
- `LogoFreeTermIco.ico` : Icône de l'application.

### Prérequis

- **Python 3.x** : Assurez-vous que Python est installé sur votre système. [Télécharger Python](https://www.python.org/).
- **pip** : Le gestionnaire de paquets Python, généralement inclus avec Python.

### Installation des dépendances

Exécutez la commande suivante pour installer les bibliothèques nécessaires :

```bash
pip install PyQt5 pyserial
```

### Lancement de l'application

1. Naviguez dans le dossier `Programme .py` via un terminal :

```bash
cd "c:\Users\weedm\Documents\GitHub\    CrazySerialTerm\Programme .py"
```

2. Lancez l'application avec Python :

```bash
python     CrazySerialTerm.py
```

