"""
Implémentation du pattern Observer pour la gestion des événements.
"""
from typing import Dict, List, Any, Callable, Set
import logging

logger = logging.getLogger("CrazySerialTerm")

class Event:
    """Classe représentant un événement dans le système."""
    
    # Types d'événements prédéfinis
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    DATA_RECEIVED = "data_received"
    DATA_SENT = "data_sent"
    ERROR_OCCURRED = "error_occurred"
    PORT_DETECTED = "port_detected"
    PORT_REMOVED = "port_removed"
    
    def __init__(self, event_type: str, data: Any = None):
        """
        Initialise un nouvel événement.
        
        Args:
            event_type: Type de l'événement
            data: Données associées à l'événement
        """
        self.event_type = event_type
        self.data = data

class Observer:
    """Interface pour les observateurs."""
    
    def update(self, event: Event) -> None:
        """
        Méthode appelée lorsqu'un événement est déclenché.
        
        Args:
            event: L'événement déclenché
        """
        pass

class Observable:
    """Classe de base pour les objets observables."""
    
    def __init__(self):
        """Initialise un nouvel objet observable."""
        self._observers: Dict[str, Set[Observer]] = {}
    
    def add_observer(self, event_type: str, observer: Observer) -> None:
        """
        Ajoute un observateur pour un type d'événement spécifique.
        
        Args:
            event_type: Type d'événement à observer
            observer: Observateur à ajouter
        """
        if event_type not in self._observers:
            self._observers[event_type] = set()
        self._observers[event_type].add(observer)
        logger.debug(f"Observateur ajouté pour l'événement {event_type}")
    
    def remove_observer(self, event_type: str, observer: Observer) -> None:
        """
        Supprime un observateur pour un type d'événement spécifique.
        
        Args:
            event_type: Type d'événement
            observer: Observateur à supprimer
        """
        if event_type in self._observers and observer in self._observers[event_type]:
            self._observers[event_type].remove(observer)
            logger.debug(f"Observateur supprimé pour l'événement {event_type}")
    
    def notify_observers(self, event: Event) -> None:
        """
        Notifie tous les observateurs d'un événement.
        
        Args:
            event: L'événement à notifier
        """
        if event.event_type in self._observers:
            for observer in self._observers[event.event_type]:
                try:
                    observer.update(event)
                except Exception as e:
                    logger.error(f"Erreur lors de la notification de l'observateur: {str(e)}")

class EventManager:
    """
    Gestionnaire d'événements centralisé utilisant le pattern Singleton.
    Permet d'enregistrer des callbacks pour des événements spécifiques.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventManager, cls).__new__(cls)
            cls._instance._callbacks = {}
            logger.debug("EventManager créé")
        return cls._instance
    
    def register(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """
        Enregistre un callback pour un type d'événement spécifique.
        
        Args:
            event_type: Type d'événement
            callback: Fonction à appeler lors de l'événement
        """
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
        logger.debug(f"Callback enregistré pour l'événement {event_type}")
    
    def unregister(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """
        Supprime un callback pour un type d'événement spécifique.
        
        Args:
            event_type: Type d'événement
            callback: Fonction à supprimer
        """
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)
            logger.debug(f"Callback supprimé pour l'événement {event_type}")
    
    def emit(self, event: Event) -> None:
        """
        Émet un événement à tous les callbacks enregistrés.
        
        Args:
            event: L'événement à émettre
        """
        if event.event_type in self._callbacks:
            for callback in self._callbacks[event.event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Erreur lors de l'exécution du callback: {str(e)}")