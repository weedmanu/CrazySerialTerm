"""
Configuration pour CrazySerialTerm
Ce fichier contient les paramètres configurables de l'application.
"""
from typing import Dict, Any, List

# Paramètres généraux
APP_NAME = "CrazySerialTerm"
APP_VERSION = "1.0.0"
COMPANY_NAME = "SerialTerminal"

# Paramètres de connexion par défaut
DEFAULT_BAUD_RATE = 115200
DEFAULT_DATA_BITS = 8
DEFAULT_PARITY = "N"  # N=None, E=Even, O=Odd
DEFAULT_STOP_BITS = 1
DEFAULT_FLOW_CONTROL = "none"  # none, xonxoff, rtscts, dsrdtr

# Paramètres d'affichage par défaut
DEFAULT_DISPLAY_FORMAT = "ASCII"  # ASCII, HEX, BOTH
DEFAULT_AUTO_SCROLL = True
DEFAULT_TIMESTAMP = False
DEFAULT_BUFFER_SIZE = 10000

# Paramètres d'envoi par défaut
DEFAULT_SEND_FORMAT = "ASCII"  # ASCII, HEX
DEFAULT_EOL = "none"  # none, nl, cr, nlcr
DEFAULT_REPEAT_INTERVAL = 1000  # ms
MAX_SAVED_COMMANDS = 10  # Nombre maximum de commandes sauvegardées

# Liste des vitesses disponibles
BAUD_RATES = [
    9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
]

# Thèmes disponibles
THEMES = {
    "clair": {
        "window": "#FFFFFF",
        "text": "#000000",
        "background": "#FFFFFF",
    },
    "sombre": {
        "window": "#353535",
        "text": "#FFFFFF",
        "background": "#2A2A2A",
    },
    "hacker": {
        "window": "#000000",
        "text": "#00FF00",
        "background": "#000000",
    }
}

# Configuration de journalisation
LOG_CONFIG = {
    "version": 1,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "filename": "serial_terminal.log",
            "mode": "a",
        },
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        }
    },
    "loggers": {
        "CrazySerialTerm": {
            "level": "DEBUG",
            "handlers": ["file", "console"],
            "propagate": False
        }
    }
}