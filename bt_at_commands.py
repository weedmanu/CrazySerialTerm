"""
Module contenant les commandes AT pour modules Bluetooth HC-05 et HC-06.
"""

# Liste des commandes AT pour modules Bluetooth avec leurs descriptions
BT_AT_COMMANDS = [
    {
        "category": "Commandes de base",
        "commands": [
            {
                "command": "AT",
                "description": "Test de fonctionnement. Renvoie 'OK' si le module fonctionne correctement."
            },
            {
                "command": "AT+VERSION",
                "description": "Affiche la version du firmware."
            },
            {
                "command": "AT+NAME",
                "description": "Affiche le nom actuel du module."
            },
            {
                "command": "AT+NAME=<nom>",
                "description": "Change le nom du module Bluetooth."
            },
            {
                "command": "AT+RESET",
                "description": "Redémarre le module."
            }
        ]
    },
    {
        "category": "Configuration Bluetooth",
        "commands": [
            {
                "command": "AT+ADDR",
                "description": "Affiche l'adresse MAC du module."
            },
            {
                "command": "AT+ROLE=0",
                "description": "Configure le module en mode esclave (HC-05 uniquement)."
            },
            {
                "command": "AT+ROLE=1",
                "description": "Configure le module en mode maître (HC-05 uniquement)."
            },
            {
                "command": "AT+PSWD=<code>",
                "description": "Définit le code PIN pour l'appairage (généralement 1234)."
            },
            {
                "command": "AT+PIN<code>",
                "description": "Définit le code PIN pour l'appairage (format HC-06)."
            },
            {
                "command": "AT+POLAR=<0/1>,<0/1>",
                "description": "Configure la polarité des broches d'état (HC-05 uniquement)."
            }
        ]
    },
    {
        "category": "Configuration UART",
        "commands": [
            {
                "command": "AT+UART=<baud>,<stop>,<parity>",
                "description": "Configure les paramètres UART (HC-05). Ex: AT+UART=9600,0,0"
            },
            {
                "command": "AT+BAUD<n>",
                "description": "Configure le débit en bauds (HC-06). n=1:1200, 2:2400, 3:4800, 4:9600, 5:19200, 6:38400, 7:57600, 8:115200"
            },
            {
                "command": "AT+ORGL",
                "description": "Restaure les paramètres d'usine (HC-05 uniquement)."
            },
            {
                "command": "AT+RMAAD",
                "description": "Efface tous les appareils appairés (HC-05 uniquement)."
            }
        ]
    },
    {
        "category": "Connexion (HC-05 uniquement)",
        "commands": [
            {
                "command": "AT+STATE",
                "description": "Affiche l'état actuel de la connexion."
            },
            {
                "command": "AT+INIT",
                "description": "Initialise le module SPP."
            },
            {
                "command": "AT+INQ",
                "description": "Recherche les appareils Bluetooth à proximité."
            },
            {
                "command": "AT+LINK=<addr>",
                "description": "Se connecte à l'adresse MAC spécifiée."
            },
            {
                "command": "AT+DISC",
                "description": "Déconnecte la connexion actuelle."
            },
            {
                "command": "AT+CMODE=0",
                "description": "Se connecte uniquement à l'adresse spécifiée."
            },
            {
                "command": "AT+CMODE=1",
                "description": "Se connecte à n'importe quel appareil disponible."
            }
        ]
    }
]