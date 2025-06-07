"""
Module contenant les commandes AT pour ESP01 et leurs descriptions.
"""

# Liste des commandes AT pour ESP01 avec leurs descriptions
ESP_AT_COMMANDS = [
    {
        "category": "Commandes de base",
        "commands": [
            {
                "command": "AT",
                "description": "Test de fonctionnement. Renvoie 'OK' si le module fonctionne correctement."
            },
            {
                "command": "AT+RST",
                "description": "Redémarre le module ESP8266."
            },
            {
                "command": "AT+GMR",
                "description": "Affiche la version du firmware."
            },
            {
                "command": "AT+GSLP=<time>",
                "description": "Met le module en mode veille profonde pendant <time> millisecondes."
            },
            {
                "command": "ATE0",
                "description": "Désactive l'écho des commandes."
            },
            {
                "command": "ATE1",
                "description": "Active l'écho des commandes."
            }
        ]
    },
    {
        "category": "Configuration WiFi",
        "commands": [
            {
                "command": "AT+CWMODE=<mode>",
                "description": "Définit le mode WiFi: 1=Station, 2=AP, 3=Station+AP."
            },
            {
                "command": "AT+CWMODE?",
                "description": "Affiche le mode WiFi actuel."
            },
            {
                "command": "AT+CWJAP=\"<ssid>\",\"<password>\"",
                "description": "Connecte le module à un réseau WiFi."
            },
            {
                "command": "AT+CWJAP?",
                "description": "Affiche les informations du réseau WiFi connecté."
            },
            {
                "command": "AT+CWLAP",
                "description": "Liste les points d'accès disponibles."
            },
            {
                "command": "AT+CWQAP",
                "description": "Déconnecte du réseau WiFi actuel."
            },
            {
                "command": "AT+CWSAP=\"<ssid>\",\"<pwd>\",<chl>,<ecn>",
                "description": "Configure le module en mode point d'accès."
            },
            {
                "command": "AT+CWSAP?",
                "description": "Affiche la configuration du point d'accès."
            }
        ]
    },
    {
        "category": "Commandes TCP/IP",
        "commands": [
            {
                "command": "AT+CIPSTATUS",
                "description": "Affiche l'état de la connexion."
            },
            {
                "command": "AT+CIPSTART=\"<type>\",\"<addr>\",<port>",
                "description": "Établit une connexion TCP ou UDP."
            },
            {
                "command": "AT+CIPSEND=<length>",
                "description": "Envoie des données de longueur spécifiée."
            },
            {
                "command": "AT+CIPCLOSE",
                "description": "Ferme la connexion TCP/UDP."
            },
            {
                "command": "AT+CIFSR",
                "description": "Affiche l'adresse IP locale."
            },
            {
                "command": "AT+CIPMUX=<mode>",
                "description": "Active (1) ou désactive (0) les connexions multiples."
            },
            {
                "command": "AT+CIPSERVER=<mode>[,<port>]",
                "description": "Configure le module en serveur TCP."
            }
        ]
    },
    {
        "category": "Commandes avancées",
        "commands": [
            {
                "command": "AT+UART_DEF=<baud>,<databits>,<stopbits>,<parity>,<flow control>",
                "description": "Configure les paramètres UART par défaut."
            },
            {
                "command": "AT+UART_CUR=<baud>,<databits>,<stopbits>,<parity>,<flow control>",
                "description": "Configure les paramètres UART actuels (temporaires)."
            },
            {
                "command": "AT+SLEEP=<mode>",
                "description": "Configure le mode veille: 0=désactivé, 1=léger, 2=profond."
            },
            {
                "command": "AT+RFPOWER=<power>",
                "description": "Définit la puissance de transmission RF (0-82, max=82)."
            },
            {
                "command": "AT+CWDHCP=<mode>,<en>",
                "description": "Active/désactive DHCP: mode=0/1/2 (STA/AP/both), en=0/1 (OFF/ON)."
            },
            {
                "command": "AT+RESTORE",
                "description": "Restaure les paramètres d'usine."
            }
        ]
    }
]