"""
Utilitaires pour la communication série
Ce module contient des fonctions utilitaires pour la communication série.
"""
import serial
import serial.tools.list_ports
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger("CrazySerialTerm")

def list_available_ports() -> List[str]:
    """
    Liste tous les ports série disponibles sur le système.
    
    Returns:
        List[str]: Liste des noms de ports disponibles
    """
    try:
        ports = [port.device for port in serial.tools.list_ports.comports()]
        logger.debug(f"Ports disponibles: {ports}")
        return ports
    except Exception as e:
        logger.error(f"Erreur lors de la recherche des ports: {str(e)}")
        return []

def get_port_info(port_name: str) -> Dict[str, Any]:
    """
    Obtient des informations détaillées sur un port série.
    
    Args:
        port_name: Nom du port série
        
    Returns:
        Dict[str, Any]: Informations sur le port (description, fabricant, etc.)
    """
    try:
        for port in serial.tools.list_ports.comports():
            if port.device == port_name:
                return {
                    "name": port.device,
                    "description": port.description,
                    "manufacturer": port.manufacturer,
                    "hwid": port.hwid,
                    "vid": port.vid,
                    "pid": port.pid,
                    "serial_number": port.serial_number
                }
        return {"name": port_name, "description": "Port inconnu"}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations du port {port_name}: {str(e)}")
        return {"name": port_name, "error": str(e)}

def create_serial_connection(port: str, baudrate: int, bytesize: int = 8, 
                            parity: str = 'N', stopbits: float = 1, 
                            timeout: float = 0.1, **kwargs) -> Optional[serial.Serial]:
    """
    Crée une connexion série avec les paramètres spécifiés.
    
    Args:
        port: Nom du port série
        baudrate: Vitesse en bauds
        bytesize: Nombre de bits de données (5-8)
        parity: Parité ('N', 'E', 'O', 'M', 'S')
        stopbits: Bits de stop (1, 1.5, 2)
        timeout: Timeout en secondes
        **kwargs: Paramètres supplémentaires pour serial.Serial
        
    Returns:
        Optional[serial.Serial]: Objet de connexion série ou None en cas d'erreur
    """
    try:
        logger.info(f"Création d'une connexion série sur {port} ({baudrate} bauds, {bytesize}{parity}{stopbits})")
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
            **kwargs
        )
        return ser
    except serial.SerialException as e:
        logger.error(f"Erreur de connexion au port série {port}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la connexion au port {port}: {str(e)}")
        return None

def format_data_as_hex(data: bytes) -> str:
    """
    Formate des données binaires en chaîne hexadécimale.
    
    Args:
        data: Données binaires
        
    Returns:
        str: Représentation hexadécimale des données
    """
    return ' '.join(f'{b:02X}' for b in data)

def parse_hex_string(hex_string: str) -> bytes:
    """
    Convertit une chaîne hexadécimale en données binaires.
    
    Args:
        hex_string: Chaîne hexadécimale (peut contenir des espaces)
        
    Returns:
        bytes: Données binaires
    """
    # Nettoyer la chaîne en supprimant les espaces et caractères non-hex
    clean_hex = ''.join(c for c in hex_string if c.upper() in '0123456789ABCDEF')
    
    # Ajouter un 0 si nombre impair de caractères
    if len(clean_hex) % 2 != 0:
        clean_hex += '0'
        
    return bytes.fromhex(clean_hex)