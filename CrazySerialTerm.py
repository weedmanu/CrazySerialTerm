# Bibliothèques standard
import sys
import threading
import signal
import os
import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
from collections import deque

# Configuration du système de journalisation
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serial_terminal.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CrazySerialTerm")

# Bibliothèques PyQt5
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QTextEdit, QLineEdit, QMainWindow, QMenu, QAction, QFontDialog, QColorDialog, 
                             QMessageBox, QInputDialog, QStyleFactory, QCheckBox, QSpacerItem, QSizePolicy,
                             QFileDialog, QToolBar, QStatusBar, QGroupBox, QTabWidget, QShortcut, QDialog, QGridLayout,
                             QScrollArea)
from PyQt5.QtGui import QColor, QTextCursor, QFont, QKeySequence, QIcon, QPalette, QTextCharFormat
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot, QTimer, QSettings

# Bibliothèques tierces
import serial
import serial.tools.list_ports

# Modules locaux

from esp_at_commands import ESP_AT_COMMANDS
from bt_at_commands import BT_AT_COMMANDS

def resource_path(relative_path):
    """
    Obtenir le chemin absolu vers la ressource, fonctionne pour dev et pour PyInstaller.
    
    Args:
        relative_path (str): Chemin relatif vers la ressource
        
    Returns:
        str: Chemin absolu vers la ressource
    """
    try:
        # PyInstaller crée un dossier temporaire et stocke le chemin dans _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Non packagé, utiliser le chemin du script actuel
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


class Terminal(QMainWindow):
    """
    Terminal de communication série avancé avec interface graphique.
    Permet la connexion, l'envoi et la réception de données via port série.
    """
    
    # Constantes de classe
    PORT_CHECK_INTERVAL = 5000  # ms
    MAX_HISTORY_SIZE = 100
    DEFAULT_BUFFER_SIZE = 10000  # Pour l'affichage
    MAX_RX_BUFFER_SIZE = 50000   # Taille max du buffer circulaire de réception (en octets)

    def __init__(self):
        super().__init__()
        # Configuration de base
        self.serial_port = None
        self.read_thread = None
        self.read_thread_running = False
        self.command_history: List[str] = []
        self.history_index: int = -1
        self.settings = QSettings("SerialTerminal", "Settings")
        self.log_file = None
        self.rx_bytes_count = 0
        self.tx_bytes_count = 0
        self.last_receive_time = None

        # Charger les constantes de configuration
        try:
            from config import MAX_SAVED_COMMANDS
            self.max_saved_commands = MAX_SAVED_COMMANDS
        except (ImportError, AttributeError):
            self.max_saved_commands = 10
            
        logger.info("Initialisation du terminal série")
        
        self.initUI()
        # Utiliser la fonction resource_path pour trouver l'icône
        icon_path = resource_path('LogoFreeTermIco.ico')
        self.setWindowIcon(QIcon(icon_path))
        logger.debug(f"Icône chargée depuis: {icon_path}")
        
        self.loadSettings()
        self.setupShortcuts()
        
        # Vérifier périodiquement les ports disponibles
        self.port_timer = QTimer()
        self.port_timer.timeout.connect(self.checkPorts)
        self.port_timer.start(self.PORT_CHECK_INTERVAL)
        logger.debug(f"Timer de vérification des ports démarré ({self.PORT_CHECK_INTERVAL}ms)")

    def initUI(self):
        # Configuration de la fenêtre principale
        self.setWindowTitle('Terminal de Communication Série Avancé')        
        self.setMinimumSize(400, 400)  # Taille minimale
        
        # Initialiser la barre de statut
        self.statusBarWidget = QStatusBar()
        self.setStatusBar(self.statusBarWidget)
        # Ajouter un label permanent pour les compteurs RX/TX
        self.statusRxTxLabel = QLabel("RX: 0 | TX: 0")
        self.statusBarWidget.addPermanentWidget(self.statusRxTxLabel)
        # Message initial
        self.statusBarWidget.showMessage("Prêt")
        
        # Créer un widget central avec des onglets
        self.tabWidget = QTabWidget()
        self.setCentralWidget(self.tabWidget)
        
        # Onglet principal pour le terminal
        self.terminalTab = QWidget()
        self.tabWidget.addTab(self.terminalTab, "Terminal")
        
        # Layout principal pour l'onglet terminal
        self.main_layout = QVBoxLayout(self.terminalTab)
        
        # Panneau de configuration de connexion
        self.setupConnectionPanel()
        
        # Zone de terminal avec affichage formaté
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)  # Terminal en lecture seule
        font = QFont("Consolas", 12) # Police par défaut du terminal en taille 12
        self.terminal.setFont(font)
        self.terminal.setMinimumHeight(200)  # Hauteur minimale pour le terminal
        self.main_layout.addWidget(self.terminal, 4)  # Donner plus d'espace au terminal
        
        # Stocker les valeurs par défaut
        self.defaultFont = self.terminal.font()
        self.defaultTextColor = self.terminal.textColor()
        self.defaultBgColor = self.terminal.palette().base().color()
        
        # Panneau inférieur (saisie et options)
        self.setupInputPanel()
        
        # Créer les menus
        self.setupMenus()
        
        # Onglet de configuration avancée
        self.setupAdvancedTab()
        
        # Onglet des commandes prédéfinies
        self.setupCommandsTab()
        
        # Onglets des commandes AT (stockés pour pouvoir les afficher/masquer)
        self.commandTabs = {}
        
        # Onglet des commandes AT ESP01
        self.setupEspAtCommandsTab()
        
        # Onglet des commandes AT Bluetooth HC-05/HC-06
        self.setupBtAtCommandsTab()
        
        # Charger la visibilité des onglets de commandes
        self.loadCommandTabsVisibility()
        # Masquer les onglets au démarrage (forcer l'état masqué)
        idx = self.tabWidget.indexOf(self.commandsTab)
        if idx != -1:
            self.tabWidget.removeTab(idx)
        idx = self.tabWidget.indexOf(self.advancedTab)
        if idx != -1:
            self.tabWidget.removeTab(idx)
        esp_tab = self.commandTabs.get('esp', {}).get('tab')
        if esp_tab:
            idx = self.tabWidget.indexOf(esp_tab)
            if idx != -1:
                self.tabWidget.removeTab(idx)
        bt_tab = self.commandTabs.get('bt', {}).get('tab')
        if bt_tab:
            idx = self.tabWidget.indexOf(bt_tab)
            if idx != -1:
                self.tabWidget.removeTab(idx)

        self.show()
        self.resize(600, 500)  # <-- Taille initiale plus large pour un meilleur affichage

    def setupToolbar(self):
        # Créer une barre d'outils
        self.toolbar = QToolBar("Barre d'outils principale")
        self.addToolBar(self.toolbar)
        
        # Actions pour la barre d'outils
        self.connectAction = QAction("Connecter", self)
        self.connectAction.triggered.connect(self.toggle_connection)
        self.toolbar.addAction(self.connectAction)
        
        self.clearAction = QAction("Effacer", self)
        self.clearAction.triggered.connect(self.clearTerminal)
        self.toolbar.addAction(self.clearAction)
        
        self.logAction = QAction("Démarrer log", self)
        self.logAction.triggered.connect(self.toggle_logging)
        self.toolbar.addAction(self.logAction)
        
        self.toolbar.addSeparator()
        
        self.refreshAction = QAction("Rafraîchir ports", self)
        self.refreshAction.triggered.connect(self.refreshPorts)
        self.toolbar.addAction(self.refreshAction)

    def setupConnectionPanel(self):
        # Groupe pour les paramètres de connexion
        self.connectionGroup = QGroupBox("Paramètres de connexion")
        connectionLayout = QHBoxLayout()
        
        # Port série
        portLayout = QHBoxLayout()
        portLayout.addWidget(QLabel('Port:'))
        self.portSelect = QComboBox()
        self.refreshPorts()
        portLayout.addWidget(self.portSelect)
        connectionLayout.addLayout(portLayout)
        
        # Bouton de rafraîchissement
        refreshBtn = QPushButton('Rafraîchir')
        refreshBtn.clicked.connect(self.refreshPorts)
        connectionLayout.addWidget(refreshBtn)
        
        # Vitesse
        baudLayout = QHBoxLayout()
        baudLayout.addWidget(QLabel('Vitesse:'))
        self.baudSelect = QComboBox()
        self.baudSelect.addItems(['9600', '19200', '38400', '57600', '115200', '230400', '460800', '921600'])
        self.baudSelect.setCurrentText('115200')  # Vitesse par défaut moderne
        baudLayout.addWidget(self.baudSelect)
        connectionLayout.addLayout(baudLayout)
        
        # Bouton de connexion
        self.connectBtn = QPushButton('Connecter')
        self.connectBtn.setMinimumWidth(80)  # Largeur minimale pour le bouton
        self.connectBtn.clicked.connect(self.toggle_connection)
        connectionLayout.addWidget(self.connectBtn)
        
        # Bouton pour effacer
        self.clearBtn = QPushButton('Effacer')
        self.clearBtn.clicked.connect(self.clearTerminal)
        connectionLayout.addWidget(self.clearBtn)
        
        # Créer les widgets pour les options avancées (ils seront utilisés dans l'onglet avancé)
        # Bits de données
        self.dataSelect = QComboBox()
        self.dataSelect.addItems(['5', '6', '7', '8'])
        self.dataSelect.setCurrentText('8')
        
        # Parité
        self.paritySelect = QComboBox()
        self.paritySelect.addItems(['Aucune', 'Paire', 'Impaire'])
        
        # Bits de stop
        self.stopSelect = QComboBox()
        self.stopSelect.addItems(['1', '1.5', '2'])
        
        # Flux de contrôle
        self.flowSelect = QComboBox()
        self.flowSelect.addItems(['Aucun', 'XON/XOFF', 'RTS/CTS', 'DSR/DTR'])
        
        # Créer les widgets pour les options d'affichage (ils seront utilisés dans l'onglet avancé)
        # Format d'affichage
        self.displayFormat = QComboBox()
        self.displayFormat.addItems(['ASCII', 'HEX', 'Les deux'])
        
        # Défilement automatique
        self.scrollCheckBox = QCheckBox('Défilement automatique')
        self.scrollCheckBox.setChecked(True)
        self.scrollCheckBox.stateChanged.connect(self.toggleAutoScroll)
        
        # Timestamp
        self.timestampCheckBox = QCheckBox('Afficher timestamps')
        
        self.connectionGroup.setLayout(connectionLayout)
        self.main_layout.addWidget(self.connectionGroup)

    def setupInputPanel(self):
        # Panel pour la saisie de texte
        self.inputGroup = QGroupBox("Envoi de données") # Assigner à self.inputGroup
        inputLayout = QVBoxLayout()

        # Zone de saisie et bouton
        sendLayout = QHBoxLayout()
        self.inputField = QLineEdit()
        self.inputField.returnPressed.connect(self.sendData)
        sendLayout.addWidget(QLabel("Commande :"))
        sendLayout.addWidget(self.inputField, 4)

        self.sendBtn = QPushButton('Envoyer')
        self.sendBtn.clicked.connect(self.sendData)
        sendLayout.addWidget(self.sendBtn)

        inputLayout.addLayout(sendLayout)

        # Créer les widgets pour les options d'envoi (ils seront utilisés dans l'onglet avancé)
        # Format d'envoi (ASCII/HEX)
        self.formatSelect = QComboBox()
        self.formatSelect.addItems(['ASCII', 'HEX'])
        
        # Fin de ligne
        self.nlcrChoice = QComboBox()
        self.nlcrChoice.addItems(['Aucun', 'NL', 'CR', 'NL+CR'])
        
        # Répétition
        self.repeatCheck = QCheckBox('Répéter')
        
        # Intervalle
        self.repeatInterval = QLineEdit('1000')
        self.repeatInterval.setFixedWidth(60)

        self.inputGroup.setLayout(inputLayout) # Utiliser self.inputGroup
        self.main_layout.addWidget(self.inputGroup) # Utiliser self.inputGroup

        # Timer pour l'envoi répété
        self.repeat_timer = QTimer()
        self.repeat_timer.timeout.connect(self.sendData)

    def setupDisplayOptionsPanel(self):
        # Cette méthode est maintenant vide car les options d'affichage ont été déplacées
        # vers l'onglet des paramètres avancés
        pass

    def setupMenus(self):
        # Menu Connexion
        connectionMenu = self.menuBar().addMenu('Connexion')
        
        # Connecter/Déconnecter
        connectAction = QAction('Connecter/Déconnecter', self)
        connectAction.setShortcut('Ctrl+K')
        connectAction.triggered.connect(self.toggle_connection)
        connectionMenu.addAction(connectAction)
        
        # Rafraîchir les ports
        refreshAction = QAction('Rafraîchir les ports', self)
        refreshAction.triggered.connect(self.refreshPorts)
        connectionMenu.addAction(refreshAction)
        
        connectionMenu.addSeparator()
        
        # Quitter
        exitAction = QAction('Quitter', self)
        exitAction.triggered.connect(self.close)
        connectionMenu.addAction(exitAction)
        
        # Menu Terminal
        terminalMenu = self.menuBar().addMenu('Terminal')
        
        # Effacer le terminal
        clearAction = QAction('Effacer le terminal', self)
        clearAction.setShortcut('Ctrl+C')
        clearAction.triggered.connect(self.clearTerminal)
        terminalMenu.addAction(clearAction)
        
        # Enregistrer le contenu du terminal
        saveAction = QAction('Enregistrer le contenu...', self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.triggered.connect(self.saveTerminalContent)
        terminalMenu.addAction(saveAction)
        
        # Démarrer/arrêter l'enregistrement
        self.logFileAction = QAction('Démarrer enregistrement...', self)
        self.logFileAction.setShortcut('Ctrl+L')
        self.logFileAction.triggered.connect(self.startLogging)
        terminalMenu.addAction(self.logFileAction)
        
        terminalMenu.addSeparator()
        
        # Copier
        copyAction = QAction('Copier', self)
        copyAction.triggered.connect(self.copyText)
        terminalMenu.addAction(copyAction)
        
        # Coller
        pasteAction = QAction('Coller', self)
        pasteAction.triggered.connect(self.pasteText)
        terminalMenu.addAction(pasteAction)
        
        # Menu Affichage
        viewMenu = self.menuBar().addMenu('Affichage')
        
        # Masquer/Afficher le panneau d'envoi
        self.toggleSendPanelAction = QAction('Afficher le panneau d\'envoi', self, checkable=True)
        self.toggleSendPanelAction.setShortcut('Ctrl+T')
        self.toggleSendPanelAction.setChecked(True) # Visible par défaut
        self.toggleSendPanelAction.triggered.connect(self.toggleSendPanelVisibility)
        viewMenu.addAction(self.toggleSendPanelAction)
        
        # Sous-menu des onglets
        tabsMenu = viewMenu.addMenu('Onglets')

        # Onglet Commandes
        self.commandsTabAction = QAction('Commandes', self)
        self.commandsTabAction.setCheckable(True)
        self.commandsTabAction.setChecked(True)
        self.commandsTabAction.triggered.connect(lambda checked: self.toggleTab(self.commandsTab, checked, 'Commandes'))
        tabsMenu.addAction(self.commandsTabAction)

        # Onglet Paramètres avancés
        self.advancedTabAction = QAction('Paramètres avancés', self)
        self.advancedTabAction.setCheckable(True)
        self.advancedTabAction.setChecked(True)
        self.advancedTabAction.triggered.connect(lambda checked: self.toggleTab(self.advancedTab, checked, 'Paramètres avancés'))
        tabsMenu.addAction(self.advancedTabAction)

        # Onglet ESP01
        self.espTabAction = QAction('Commandes AT ESP01', self)
        self.espTabAction.setCheckable(True)
        self.espTabAction.setChecked(True)
        self.espTabAction.triggered.connect(lambda checked: self.toggleCommandTab('esp', checked))
        tabsMenu.addAction(self.espTabAction)

        # Onglet Bluetooth
        self.btTabAction = QAction('Commandes AT Bluetooth', self)
        self.btTabAction.setCheckable(True)
        self.btTabAction.setChecked(True)
        self.btTabAction.triggered.connect(lambda checked: self.toggleCommandTab('bt', checked))
        tabsMenu.addAction(self.btTabAction)

        # Sous-menu Apparence (remplace Thèmes)
        appearanceMenu = viewMenu.addMenu('Apparence')
        # Thèmes prédéfinis
        lightThemeAction = QAction('Thème clair', self)
        lightThemeAction.triggered.connect(lambda: self.applyTheme('clair'))
        appearanceMenu.addAction(lightThemeAction)
        darkThemeAction = QAction('Thème sombre', self)
        darkThemeAction.triggered.connect(lambda: self.applyTheme('sombre'))
        appearanceMenu.addAction(darkThemeAction)
        hackerThemeAction = QAction('Thème hacker', self)
        hackerThemeAction.triggered.connect(lambda: self.applyTheme('hacker'))
        appearanceMenu.addAction(hackerThemeAction)
        # Personnalisation
        appearanceMenu.addSeparator()
        fontAction = QAction('Changer la police', self)
        fontAction.triggered.connect(self.changeFont)
        appearanceMenu.addAction(fontAction)
        textColorAction = QAction('Couleur du texte', self)
        textColorAction.triggered.connect(self.changeTextColor)
        appearanceMenu.addAction(textColorAction)
        bgColorAction = QAction('Couleur du fond', self)
        bgColorAction.triggered.connect(self.changeBgColor)
        appearanceMenu.addAction(bgColorAction)
        resetViewAction = QAction('Réinitialiser l\'apparence', self)
        resetViewAction.setToolTip("Réinitialise l'apparence au thème sombre par défaut")
        resetViewAction.triggered.connect(self.resetConfig)
        appearanceMenu.addAction(resetViewAction)
    
    def toggleTab(self, tabWidget, visible, label):
        idx = self.tabWidget.indexOf(tabWidget)
        if visible:
            if idx == -1:
                # Ajoute l'onglet à la bonne position (après Terminal)
                self.tabWidget.addTab(tabWidget, label)
        else:
            if idx != -1:
                self.tabWidget.removeTab(idx)

    def setupAdvancedTab(self):
        # Onglet des paramètres avancés
        self.advancedTab = QWidget()
        self.tabWidget.addTab(self.advancedTab, "Paramètres avancés")
        advancedLayout = QVBoxLayout(self.advancedTab)
        
        # Groupe pour les options d'envoi
        sendGroup = QGroupBox("Options d'envoi")
        sendGroup.setCheckable(True)
        sendGroup.setChecked(True)
        sendLayout = QGridLayout()
        sendWidget = QWidget()
        sendWidget.setLayout(sendLayout)
        
        # Format d'envoi (ASCII/HEX)
        sendLayout.addWidget(QLabel('Format :'), 0, 0)
        sendLayout.addWidget(self.formatSelect, 0, 1)
        
        # Fin de ligne
        sendLayout.addWidget(QLabel('Fin de ligne :'), 0, 2)
        sendLayout.addWidget(self.nlcrChoice, 0, 3)
        
        # Répétition
        sendLayout.addWidget(self.repeatCheck, 1, 0)
        
        # Intervalle
        sendLayout.addWidget(QLabel('Intervalle (ms) :'), 1, 2)
        sendLayout.addWidget(self.repeatInterval, 1, 3)
        
        sendGroupLayout = QVBoxLayout()
        sendGroupLayout.addWidget(sendWidget)
        sendGroup.setLayout(sendGroupLayout)
        advancedLayout.addWidget(sendGroup)
        sendGroup.toggled.connect(lambda checked: sendWidget.setVisible(checked))
        
        # Groupe pour les options d'affichage
        displayGroup = QGroupBox("Options d'affichage")
        displayGroup.setCheckable(True)
        displayGroup.setChecked(True)
        displayLayout = QGridLayout()
        displayWidget = QWidget()
        displayWidget.setLayout(displayLayout)
        
        # Format des données reçues
        displayLayout.addWidget(QLabel('Format d\'affichage:'), 0, 0)
        displayLayout.addWidget(self.displayFormat, 0, 1)
        
        # Défilement automatique
        displayLayout.addWidget(self.scrollCheckBox, 1, 0, 1, 2)
        
        # Timestamp
        displayLayout.addWidget(self.timestampCheckBox, 2, 0, 1, 2)
        
        displayGroupLayout = QVBoxLayout()
        displayGroupLayout.addWidget(displayWidget)
        displayGroup.setLayout(displayGroupLayout)
        advancedLayout.addWidget(displayGroup)
        displayGroup.toggled.connect(lambda checked: displayWidget.setVisible(checked))
        
        # Groupe pour les paramètres de connexion avancés
        serialGroup = QGroupBox("Paramètres de connexion avancés")
        serialGroup.setCheckable(True)
        serialGroup.setChecked(False)
        serialLayout = QGridLayout()
        serialWidget = QWidget()
        serialWidget.setLayout(serialLayout)
        
        # Bits de données
        serialLayout.addWidget(QLabel('Bits de données:'), 0, 0)
        serialLayout.addWidget(self.dataSelect, 0, 1)
        
        # Parité
        serialLayout.addWidget(QLabel('Parité:'), 0, 2)
        serialLayout.addWidget(self.paritySelect, 0, 3)
        
        # Bits de stop
        serialLayout.addWidget(QLabel('Bits de stop:'), 1, 0)
        serialLayout.addWidget(self.stopSelect, 1, 1)
        
        # Flux de contrôle
        serialLayout.addWidget(QLabel('Contrôle de flux:'), 1, 2)
        serialLayout.addWidget(self.flowSelect, 1, 3)
        
        serialGroupLayout = QVBoxLayout()
        serialGroupLayout.addWidget(serialWidget)
        serialGroup.setLayout(serialGroupLayout)
        advancedLayout.addWidget(serialGroup)
        serialGroup.toggled.connect(lambda checked: serialWidget.setVisible(checked))
        serialWidget.setVisible(False)
        
        # Groupe pour les paramètres du terminal
        terminalGroup = QGroupBox("Paramètres du terminal")
        terminalGroup.setCheckable(True)
        terminalGroup.setChecked(False)
        terminalParamsLayout = QVBoxLayout()
        terminalWidget = QWidget()
        terminalWidget.setLayout(terminalParamsLayout)
        
        # Taille du buffer
        bufferLayout = QHBoxLayout()
        bufferLayout.addWidget(QLabel("Taille maximale du buffer:"))
        self.bufferSizeInput = QLineEdit("10000")
        bufferLayout.addWidget(self.bufferSizeInput)
        bufferLayout.addWidget(QLabel("lignes"))
        terminalParamsLayout.addLayout(bufferLayout)
        
        # Filtres d'affichage
        filterLayout = QHBoxLayout()
        filterLayout.addWidget(QLabel("Filtre d'affichage:"))
        self.filterInput = QLineEdit()
        self.filterInput.setPlaceholderText("Entrez un motif pour filtrer (regex supporté)")
        filterLayout.addWidget(self.filterInput)
        terminalParamsLayout.addLayout(filterLayout)
        
        # Activer/désactiver le filtre
        self.enableFilterCheck = QCheckBox("Activer le filtre")
        terminalParamsLayout.addWidget(self.enableFilterCheck)
        
        terminalGroupLayout = QVBoxLayout()
        terminalGroupLayout.addWidget(terminalWidget)
        terminalGroup.setLayout(terminalGroupLayout)
        advancedLayout.addWidget(terminalGroup)
        terminalGroup.toggled.connect(lambda checked: terminalWidget.setVisible(checked))
        terminalWidget.setVisible(False)
        
        # Groupe pour les paramètres de débogage
        debugGroup = QGroupBox("Débogage")
        debugGroup.setCheckable(True)
        debugGroup.setChecked(False)
        debugLayout = QVBoxLayout()
        debugWidget = QWidget()
        debugWidget.setLayout(debugLayout)
        
        # Afficher les octets bruts
        self.showRawBytesCheck = QCheckBox("Afficher les octets bruts")
        debugLayout.addWidget(self.showRawBytesCheck)
        
        # Afficher les délais entre les trames
        self.showTimingCheck = QCheckBox("Afficher les délais entre les trames")
        debugLayout.addWidget(self.showTimingCheck)
        
        debugGroupLayout = QVBoxLayout()
        debugGroupLayout.addWidget(debugWidget)
        debugGroup.setLayout(debugGroupLayout)
        advancedLayout.addWidget(debugGroup)
        debugGroup.toggled.connect(lambda checked: debugWidget.setVisible(checked))
        debugWidget.setVisible(False)
        
        # Groupe pour les paramètres de sauvegarde
        saveGroup = QGroupBox("Sauvegarde automatique")
        saveGroup.setCheckable(True)
        saveGroup.setChecked(False)
        saveLayout = QVBoxLayout()
        saveWidget = QWidget()
        saveWidget.setLayout(saveLayout)
        
        # Activation de la sauvegarde automatique
        self.autoSaveCheck = QCheckBox("Activer la sauvegarde automatique")
        saveLayout.addWidget(self.autoSaveCheck)
        
        # Dossier de sauvegarde
        folderLayout = QHBoxLayout()
        folderLayout.addWidget(QLabel("Dossier de sauvegarde:"))
        self.savePathInput = QLineEdit()
        folderLayout.addWidget(self.savePathInput)
        browseBtn = QPushButton("Parcourir...")
        browseBtn.clicked.connect(self.browseSavePath)
        folderLayout.addWidget(browseBtn)
        saveLayout.addLayout(folderLayout)
        
        saveGroupLayout = QVBoxLayout()
        saveGroupLayout.addWidget(saveWidget)
        saveGroup.setLayout(saveGroupLayout)
        advancedLayout.addWidget(saveGroup)
        saveGroup.toggled.connect(lambda checked: saveWidget.setVisible(checked))
        saveWidget.setVisible(False)
        
        # Boutons de sauvegarde/restauration des paramètres
        btnLayout = QHBoxLayout()
        saveSettingsBtn = QPushButton("Sauvegarder les paramètres")
        saveSettingsBtn.clicked.connect(self.saveSettings)
        btnLayout.addWidget(saveSettingsBtn)
        
        loadSettingsBtn = QPushButton("Restaurer les paramètres")
        loadSettingsBtn.clicked.connect(self.loadSettings)
        btnLayout.addWidget(loadSettingsBtn)
        
        advancedLayout.addLayout(btnLayout)
        advancedLayout.addStretch()

    def setupCommandsTab(self):
        # Onglet pour les commandes prédéfinies
        self.commandsTab = QWidget()
        self.tabWidget.addTab(self.commandsTab, "Commandes")
        commandsLayout = QVBoxLayout(self.commandsTab)
        
        # Explications
        infoLabel = QLabel("Définissez vos commandes fréquemment utilisées ici pour un accès rapide.")
        commandsLayout.addWidget(infoLabel)
        
        # Zone pour les commandes prédéfinies
        self.commandsTextEdit = QTextEdit()
        self.commandsTextEdit.setPlaceholderText("# Format: Nom de la commande = Commande à envoyer\n"
                                             "# Exemple:\nReset = AT+RESET\nVersion = AT+VERSION?")
        commandsLayout.addWidget(self.commandsTextEdit)
        
        # Boutons pour les commandes
        btnLayout = QHBoxLayout()
        
        saveCommandsBtn = QPushButton("Sauvegarder les commandes")
        saveCommandsBtn.clicked.connect(self.saveCommands)
        btnLayout.addWidget(saveCommandsBtn)
        
        loadCommandsBtn = QPushButton("Charger les commandes")
        loadCommandsBtn.clicked.connect(self.loadCommands)
        btnLayout.addWidget(loadCommandsBtn)
        
        clearCommandsBtn = QPushButton("Effacer les commandes")
        clearCommandsBtn.clicked.connect(self.clearCommands)
        btnLayout.addWidget(clearCommandsBtn)
        
        commandsLayout.addLayout(btnLayout)
        
        # Shortcuts des commandes
        shortcutsGroup = QGroupBox("Raccourcis de commandes rapides")
        shortcutsLayout = QVBoxLayout()
        
        # Ici on pourrait ajouter dynamiquement des boutons pour les commandes
        # Pour l'instant on ajoute juste une explication
        shortcutsInfo = QLabel("Les commandes sauvegardées apparaîtront ici comme boutons rapides.")
        shortcutsLayout.addWidget(shortcutsInfo)
        
        self.shortcutButtonsLayout = QHBoxLayout()
        shortcutsLayout.addLayout(self.shortcutButtonsLayout)
        
        shortcutsGroup.setLayout(shortcutsLayout)
        commandsLayout.addWidget(shortcutsGroup)

    def setupShortcuts(self):
        # Raccourcis clavier
        self.shortcutConnect = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcutConnect.activated.connect(self.toggle_connection)
        
        self.shortcutClear = QShortcut(QKeySequence("Ctrl+C"), self)
        self.shortcutClear.activated.connect(self.clearTerminal)
        
        self.shortcutSave = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcutSave.activated.connect(self.saveTerminalContent)
        
        self.shortcutLog = QShortcut(QKeySequence("Ctrl+L"), self)
        self.shortcutLog.activated.connect(self.toggle_logging)
        
        # Historique des commandes (flèches haut/bas)
        self.shortcutUp = QShortcut(QKeySequence("Up"), self.inputField)
        self.shortcutUp.activated.connect(self.previousCommand)
        
        self.shortcutDown = QShortcut(QKeySequence("Down"), self.inputField)
        self.shortcutDown.activated.connect(self.nextCommand)
        
        self.shortcutToggleSendPanel = QShortcut(QKeySequence("Ctrl+T"), self) # Ctrl+T pour Toggle
        self.shortcutToggleSendPanel.activated.connect(self.toggleSendPanelVisibility)

    def refreshPorts(self):
        current_port = self.portSelect.currentText()
        self.portSelect.clear()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.portSelect.addItems(ports)
            if current_port in ports:
                self.portSelect.setCurrentText(current_port)
        else:
            self.statusBarWidget.showMessage("Aucun port série détecté", 3000)

    def checkPorts(self):
        # Vérifier si de nouveaux ports sont disponibles sans changer la sélection actuelle
        try:
            current_ports = set([port.device for port in serial.tools.list_ports.comports()])
            port_items = set([self.portSelect.itemText(i) for i in range(self.portSelect.count())])
            
            # Vérifier si le port actuellement connecté est toujours disponible
            if self.serial_port and hasattr(self.serial_port, 'port'):
                connected_port = self.serial_port.port
                if connected_port not in current_ports and self.serial_port.is_open:
                    logger.info(f"Port {connected_port} déconnecté, fermeture de la connexion")
                    # Appeler handleDisconnect pour éviter les problèmes de thread
                    self.handleDisconnect()
            
            if current_ports != port_items:
                self.refreshPorts()
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des ports: {str(e)}")
            # Ne pas planter l'application en cas d'erreur

    def toggle_connection(self):
        if self.serial_port and self.serial_port.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """
        Établit une connexion avec le port série sélectionné en utilisant les paramètres configurés.
        """
        # Vérifier qu'on n'est pas déjà connecté
        if self.serial_port and self.serial_port.is_open:
            logger.warning("Tentative de connexion avec port déjà ouvert")
            self.disconnect()
            
        port = self.portSelect.currentText()
        if not port:
            self.showMessage("Aucun port série disponible. Vérifiez les connexions.")
            return
            
        try:
            # Récupérer tous les paramètres de connexion
            serial_params = self._get_serial_parameters(port)
            
            # Réinitialiser les compteurs RX/TX à la connexion
            self.rx_bytes_count = 0
            self.tx_bytes_count = 0
            self.updateStatusBar()
            
            # Créer l'objet Serial avec les paramètres
            self.serial_port = serial.Serial(**serial_params)
            
            # Afficher les informations de connexion
            port_info = f"{port} ({serial_params['baudrate']} bauds, {serial_params['bytesize']}{serial_params['parity']}{serial_params['stopbits']})"
            self.appendFormattedText(f'[Système] Connecté à {port_info}\n', QColor("green"))
            
            # Démarrer le thread de lecture
            self.read_thread_running = True
            self.read_thread = threading.Thread(target=self.readData)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            # Mettre à jour l'interface
            self.connectBtn.setText('Déconnecter')
            self.statusBarWidget.showMessage(f"Connecté à {port}", 3000)
                
        except serial.SerialException as e:
            # Erreur spécifique à PySerial lors de la connexion
            self.showMessage(f'Erreur de connexion au port série ({port}): {str(e)}', error=True)
        except FileNotFoundError:
            # Si le port n'existe pas (peut arriver sur certains systèmes)
            self.showMessage(f'Erreur: Le port série {port} n\'a pas été trouvé.', error=True)
        except Exception as e:
            # Autres erreurs inattendues
            self.showMessage(f'Erreur inattendue: {str(e)}', error=True)
            
    def _get_serial_parameters(self, port):
        """
        Récupère tous les paramètres de connexion série à partir des sélections de l'utilisateur.
        
        Args:
            port (str): Port série à utiliser
            
        Returns:
            dict: Dictionnaire des paramètres pour serial.Serial
        """
        # Paramètres de base
        baud = int(self.baudSelect.currentText())
        data_bits = int(self.dataSelect.currentText())
        
        # Convertir la parité sélectionnée en paramètre pour PySerial
        parity_map = {'Aucune': 'N', 'Paire': 'E', 'Impaire': 'O'}
        parity = parity_map[self.paritySelect.currentText()]
        
        # Convertir les bits de stop en paramètre pour PySerial
        stop_bits_map = {'1': 1, '1.5': 1.5, '2': 2}
        stop_bits = stop_bits_map[self.stopSelect.currentText()]
        
        # Configurer le contrôle de flux
        flow_control_map = {
            'Aucun': {'xonxoff': False, 'rtscts': False, 'dsrdtr': False},
            'XON/XOFF': {'xonxoff': True, 'rtscts': False, 'dsrdtr': False},
            'RTS/CTS': {'xonxoff': False, 'rtscts': True, 'dsrdtr': False},
            'DSR/DTR': {'xonxoff': False, 'rtscts': False, 'dsrdtr': True}
        }
        flow_settings = flow_control_map[self.flowSelect.currentText()]
        
        # Construire le dictionnaire de paramètres
        params = {
            'port': port,
            'baudrate': baud,
            'bytesize': data_bits,
            'parity': parity,
            'stopbits': stop_bits,
            'timeout': 0.1,
            **flow_settings
        }
        
        return params

    @pyqtSlot()
    def disconnect(self) -> None:
        """
        Déconnecte le port série et nettoie les ressources associées.
        """
        if self.serial_port:
            logger.info(f"Déconnexion du port {self.serial_port.port if hasattr(self.serial_port, 'port') else 'inconnu'}")
            
            # Arrêter le thread de lecture
            self.read_thread_running = False
            
            if self.read_thread:
                # Attendre un peu pour que le thread se termine proprement
                if self.read_thread.is_alive():
                    logger.debug("Attente de la fin du thread de lecture")
                    try:
                        self.read_thread.join(0.5)
                    except RuntimeError:
                        # Ignorer les erreurs si le thread ne peut pas être joint
                        pass
                    
            # Fermer le port série en utilisant un bloc try-finally pour garantir la fermeture
            try:
                if self.serial_port and hasattr(self.serial_port, 'is_open') and self.serial_port.is_open:
                    try:
                        self.serial_port.close()
                        logger.debug("Port série fermé avec succès")
                    except (serial.SerialException, IOError, OSError) as e:
                        logger.error(f"Erreur lors de la fermeture du port série: {str(e)}")
            except Exception as e:
                logger.error(f"Erreur inattendue lors de la fermeture du port série: {str(e)}")
            finally:
                self.serial_port = None
                self.read_thread = None
            
            # Si on avait un enregistrement en cours, le fermer
            self.stopLogging()
            
            # Arrêter le timer d'envoi répété s'il est actif
            if self.repeat_timer.isActive():
                logger.debug("Arrêt du timer d'envoi répété")
                self.repeat_timer.stop()
                self.repeatCheck.setChecked(False)
                
            # Mettre à jour l'interface
            self.appendFormattedText('[Système] Déconnecté\n', QColor("red"))
            self.connectBtn.setText('Connecter')
            self.statusBarWidget.showMessage("Déconnecté", 3000)
        else:
            logger.warning("Tentative de déconnexion sans connexion active")
            self.appendFormattedText('[Système] Aucune connexion active\n', QColor("orange"))

    @pyqtSlot()
    def handleDisconnect(self):
        """
        Méthode slot pour gérer la déconnexion depuis un thread différent.
        """
        self.disconnect()
    
    def readData(self):
        """
        Méthode exécutée dans un thread séparé pour lire les données du port série.
        Utilise un buffer circulaire pour éviter le blocage si trop de données arrivent.
        """
        last_time = datetime.now()
        timeout_seconds = 0.1  # Timeout en secondes
        thread_sleep = 0.01    # Temps de pause pour éviter de saturer le CPU
        temp_buffer = bytearray()
        error_count = 0
        max_errors = 5
    
        while self.read_thread_running and self.serial_port and self.serial_port.is_open:
            try:
                # Vérifier si le port est toujours valide
                if not self.serial_port or not self.serial_port.is_open:
                    break
    
                # Lire les données disponibles
                try:
                    in_waiting = self.serial_port.in_waiting
                except (serial.SerialException, IOError, OSError):
                    # Port probablement déconnecté
                    self._handle_serial_error("Port déconnecté ou inaccessible")
                    break
    
                if in_waiting > 0:
                    try:
                        data = self.serial_port.read(in_waiting)
                        if data:
                            # Ajouter les données au buffer circulaire
                            self.rx_buffer.extend(data)
                            temp_buffer.extend(data)
    
                            # Si on a une fin de ligne ou un timeout, traiter les données
                            if b'\n' in temp_buffer or (datetime.now() - last_time).total_seconds() > timeout_seconds:
                                # On traite uniquement ce qui est dans temp_buffer
                                self.processReceivedData(bytes(temp_buffer))
                                temp_buffer = bytearray()
                                last_time = datetime.now()
                        
                        # Réinitialiser le compteur d'erreurs si succès
                        error_count = 0
                        
                    except (serial.SerialException, IOError, OSError):
                        error_count += 1
                        if error_count >= max_errors:
                            logger.error(f"Trop d'erreurs ({max_errors}), arrêt de la lecture")
                            self._handle_serial_error(f"Arrêt après {max_errors} erreurs consécutives")
                            break
                        self._handle_serial_error("Erreur lors de la lecture des données")
                else:
                    # Pause courte pour éviter de saturer le CPU
                    threading.Event().wait(thread_sleep)
    
                    # Si le buffer temporaire contient des données et qu'un certain temps s'est écoulé
                    if temp_buffer and (datetime.now() - last_time).total_seconds() > timeout_seconds:
                        self.processReceivedData(bytes(temp_buffer))
                        temp_buffer = bytearray()
                        last_time = datetime.now()
    
                # Si le buffer circulaire est plein, on purge les plus anciennes données automatiquement (deque le fait)
    
            except serial.SerialException as e:
                error_count += 1
                if error_count >= max_errors:
                    logger.error(f"Trop d'erreurs série ({max_errors}): {str(e)}")
                    self._handle_serial_error(f"Arrêt après {max_errors} erreurs: {str(e)}")
                    break
                self._handle_serial_error(f"Erreur série: {str(e)}")
            except Exception as e:
                error_count += 1
                if error_count >= max_errors:
                    logger.error(f"Trop d'exceptions ({max_errors}): {str(e)}")
                    self._handle_serial_error(f"Arrêt après {max_errors} exceptions: {str(e)}")
                    break
                self._handle_serial_error(f"Exception inattendue: {str(e)}")
    
    def _handle_serial_error(self, error_message):
        """
        Gère les erreurs de communication série.
        
        Args:
            error_message (str): Message d'erreur à afficher
        """
        QMetaObject.invokeMethod(
            self, 
            "appendFormattedText", 
            Qt.QueuedConnection, 
            Q_ARG(str, f'[Erreur] {error_message}\n'), 
            Q_ARG(QColor, QColor("red"))
        )
        # En cas d'erreur, on tente de se déconnecter proprement
        # Utiliser une méthode slot spécifique pour éviter les erreurs de QMetaObject
        QMetaObject.invokeMethod(self, "handleDisconnect", Qt.QueuedConnection)

    def processReceivedData(self, data):
        """
        Traite les données reçues du port série et les affiche dans le terminal.
        
        Args:
            data (bytes): Données reçues du port série
        """
        # Obtenir le format d'affichage sélectionné
        display_format = self.displayFormat.currentText()
        
        # Mettre à jour le compteur RX
        self.rx_bytes_count += len(data)
        # Mettre à jour l'affichage dans la barre de statut (thread-safe)
        QMetaObject.invokeMethod(self, "updateStatusBar", Qt.QueuedConnection)
        
        try:
            # Préparer les données à afficher selon le format choisi
            if display_format == 'ASCII':
                # Décoder en texte, en remplaçant les caractères non-imprimables
                display_text = self._decode_data(data)
                
            elif display_format == 'HEX':
                # Afficher en hexadécimal
                display_text = ' '.join(f'{b:02X}' for b in data)
                
            else:  # "Les deux"
                # Afficher en ASCII et HEX
                text_data = self._decode_data(data)
                hex_data = ' '.join(f'{b:02X}' for b in data)
                display_text = f"{text_data} [{hex_data}]"
            
            # Ajouter les timestamps si activé
            display_text = self._add_timestamp(display_text)
                
            # Appliquer un filtre si activé
            if not self._apply_filter(display_text):
                return  # Ne pas afficher si filtré
            
            # Afficher en bleu pour les données reçues
            QMetaObject.invokeMethod(
                self, 
                "appendFormattedText", 
                Qt.QueuedConnection, 
                Q_ARG(str, display_text), 
                Q_ARG(QColor, QColor("blue"))
            )
            
            # Enregistrer dans le fichier log si actif
            if self.log_file:
                self.log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} RX: {display_text}\n")
                self.log_file.flush()
                
        except Exception as e:
            QMetaObject.invokeMethod(
                self, 
                "appendFormattedText", 
                Qt.QueuedConnection, 
                Q_ARG(str, f'[Erreur de traitement] {str(e)}\n'), 
                Q_ARG(QColor, QColor("red"))
            )
            
    def _decode_data(self, data):
        """Décode les données binaires en texte."""
        try:
            return data.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            return data.decode('latin-1', errors='replace')
            
    def _add_timestamp(self, text):
        """Ajoute un timestamp au texte si l'option est activée."""
        if not self.timestampCheckBox.isChecked():
            return text
            
        now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        # Afficher le délai entre les trames si activé
        if self.showTimingCheck.isChecked() and hasattr(self, 'last_receive_time') and self.last_receive_time:
            delta = datetime.now() - self.last_receive_time
            ms = delta.total_seconds() * 1000
            result = f"[{now} +{ms:.1f}ms] {text}"
        else:
            result = f"[{now}] {text}"
            
        self.last_receive_time = datetime.now()
        return result
        
    def _apply_filter(self, text):
        """
        Applique un filtre au texte si l'option est activée.
        
        Returns:
            bool: True si le texte doit être affiché, False sinon
        """
        if not self.enableFilterCheck.isChecked() or not self.filterInput.text():
            return True
            
        try:
            pattern = self.filterInput.text()
            return bool(re.search(pattern, text))
        except re.error:
            # Ignorer les erreurs de regex
            return True

    @pyqtSlot(str, QColor)
    def appendFormattedText(self, text, color=None):
        """
        Ajoute du texte formaté au terminal. Cette méthode est thread-safe.
        
        Args:
            text (str): Texte à ajouter
            color (QColor, optional): Couleur du texte
        """
        # Mettre à jour l'interface depuis n'importe quel thread
        
        # Vérifier si la barre de défilement est déjà en bas AVANT d'ajouter du texte
        scrollbar = self.terminal.verticalScrollBar()
        # On considère qu'on est "en bas" si la valeur est très proche du maximum (marge pour éviter les erreurs d'arrondi)
        was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 4)
        # Sauvegarder la position actuelle de la barre de défilement
        old_scroll_value = scrollbar.value()
        if scrollbar is not None:
            try:
                was_at_bottom = scrollbar.value() >= (scrollbar.maximum() - 4)
                old_scroll_value = scrollbar.value()
            except Exception:
                pass
        
        # Vérifier la taille en octets aussi, pas seulement en lignes
        try:
            max_lines = int(self.bufferSizeInput.text())
            current_text = self.terminal.toPlainText()
            
            # Limiter aussi par taille en octets (ex: 5MB)
            MAX_BYTES = 5 * 1024 * 1024  # 5 MB
            if len(current_text.encode('utf-8')) > MAX_BYTES or current_text.count('\n') > max_lines:
                # Garder seulement 80% du buffer quand on purge
                lines = current_text.split('\n')
                keep_lines = int(max_lines * 0.8)
                new_text = '\n'.join(lines[-keep_lines:])
                self.terminal.setPlainText(new_text)
                # Ajouter un message système
                self.terminal.append("[Système] Buffer purgé pour libérer de la mémoire\n")
            elif current_text.count('\n') > max_lines:
                # Supprimer les anciennes lignes
                lines = current_text.split('\n')
                new_text = '\n'.join(lines[-max_lines:])
                self.terminal.setPlainText(new_text)
                cursor = self.terminal.textCursor()  # Définir cursor ici pour éviter l'erreur
                cursor.movePosition(QTextCursor.End)
            else:
                cursor = self.terminal.textCursor() # Obtenir le curseur seulement si on ne modifie pas tout le texte
        except (ValueError, AttributeError):
            cursor = self.terminal.textCursor()  # Définir cursor en cas d'erreur
            pass  # Ignorer si la taille du buffer n'est pas un nombre valide
            
        # Formater le texte avec la couleur spécifiée
        if color:
            self.terminal.setTextColor(color)
            
        # Insérer le texte à la fin
        cursor.movePosition(QTextCursor.End)
        self.terminal.setTextCursor(cursor)
        self.terminal.insertPlainText(text)
        
        # Restaurer la couleur par défaut
        if color:
            self.terminal.setTextColor(self.defaultTextColor)
        
        # Gérer le défilement
        if self.scrollCheckBox.isChecked():
            # Si la case est cochée, toujours défiler vers le bas
            self.terminal.ensureCursorVisible()
        elif not was_at_bottom:
            # Si la case est décochée ET qu'on n'était PAS en bas,
            # restaurer la position de la barre de défilement précédente.
            scrollbar.setValue(old_scroll_value)
            if scrollbar is not None:
                try:
                    scrollbar.setValue(old_scroll_value)
                except Exception:
                    pass

    def sendData(self) -> None:
        """
        Envoie les données saisies au port série.
        Gère différents formats (ASCII/HEX) et options de fin de ligne.
        """
        if not self.serial_port or not self.serial_port.is_open:
            self.appendFormattedText('[Erreur] Pas de connexion série active\n', QColor("red"))
            logger.error("Tentative d'envoi sans connexion série active")
            return
            
        text = self.inputField.text()
        if not text:
            return
            
        # Mémoriser la commande dans l'historique
        if text not in self.command_history:
            self.command_history.append(text)
            if len(self.command_history) > 100:  # Limiter la taille de l'historique
                self.command_history.pop(0)
        self.history_index = len(self.command_history)
        
        # Formater les données selon le format sélectionné
        format_type = self.formatSelect.currentText()
        eol_type = self.nlcrChoice.currentText()
        
        # Ajouter les caractères de fin de ligne
        eol_map = {
            'Aucun': b'',
            'NL': b'\n',
            'CR': b'\r',
            'NL+CR': b'\r\n'
        }
        eol = eol_map[eol_type]
        
        try:
            # Préparer les données à envoyer
            data = self._prepare_data_to_send(text, format_type, eol)
                
            # Envoyer les données
            bytes_written = self.serial_port.write(data)
            logger.debug(f"Envoi de {bytes_written} octets sur {self.serial_port.port}")
            
            # Mettre à jour le compteur TX
            self.tx_bytes_count += len(data)
            self.updateStatusBar()
            
            # Afficher les données envoyées en vert
            display_text = text
            if eol_type != 'Aucun':
                if format_type == 'ASCII':
                    display_text += f" + {eol_type}"
            
            self.appendFormattedText(f'TX: {display_text}\n', QColor("green"))
            
            # Enregistrer dans le fichier log si actif
            if self.log_file:
                self.log_file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} TX: {display_text}\n")
                self.log_file.flush()
            
            # Gérer l'envoi répété si activé
            self._handle_repeat_send(text)
                
        except Exception as e:
            error_msg = f'[Erreur d\'envoi] {str(e)}'
            self.appendFormattedText(f'{error_msg}\n', QColor("red"))
            logger.error(f"Erreur lors de l'envoi des données: {str(e)}", exc_info=True)
            
    def _prepare_data_to_send(self, text: str, format_type: str, eol: bytes) -> bytes:
        """
        Prépare les données à envoyer selon le format sélectionné.

        Args:
            text: Texte à envoyer
            format_type: Format d'envoi ('ASCII' ou 'HEX')
            eol: Caractères de fin de ligne en bytes
            
        Returns:
            bytes: Données prêtes à être envoyées
        """
        if format_type == 'ASCII':
            # Envoyer en mode texte
            return text.encode('utf-8') + eol
    
        else:  # HEX
            # Convertir la chaîne HEX en bytes
            # Nettoyer l'entrée en supprimant les espaces et caractères non-hex
            hex_text = ''.join(c for c in text.upper() if c in '0123456789ABCDEF ')
            hex_text = hex_text.replace(' ', '')
        
        # Validation plus stricte
        if not hex_text:
            raise ValueError("Aucune donnée hexadécimale valide")
        
        if len(hex_text) % 2 != 0:
            # Avertir l'utilisateur et corriger
            self.appendFormattedText('[Avertissement] Nombre impair de caractères HEX, ajout d\'un 0\n', QColor("orange"))
            hex_text += '0'
            
        try:
            return bytes.fromhex(hex_text) + eol
        except ValueError as e:
            raise ValueError(f"Format hexadécimal invalide: {str(e)}")

    def _handle_repeat_send(self, text: str) -> None:
        """
        Gère l'envoi répété des données si l'option est activée.
        
        Args:
            text: Texte qui a été envoyé
        """
        if self.repeatCheck.isChecked():
            try:
                interval = int(self.repeatInterval.text())
                if not self.repeat_timer.isActive():
                    logger.info(f"Démarrage de l'envoi répété toutes les {interval}ms")
                    self.repeat_timer.start(interval)
            except ValueError:
                self.appendFormattedText('[Erreur] Intervalle non valide\n', QColor("red"))
                logger.error("Intervalle d'envoi répété non valide")
        else:
            if self.repeat_timer.isActive():
                logger.info("Arrêt de l'envoi répété")
                self.repeat_timer.stop()
            
            # Effacer le champ d'entrée sauf en mode répétition
            self.inputField.clear()
            self.inputField.setFocus()

    def clearTerminal(self):
        self.terminal.clear()
        # Réinitialiser aussi les compteurs quand on efface ? Optionnel, mais peut être logique.
        self.rx_bytes_count = 0
        self.tx_bytes_count = 0
        self.updateStatusBar()

    def previousCommand(self):
        if not self.command_history:
            return
        
        if self.history_index > 0:
            self.history_index -= 1
            self.inputField.setText(self.command_history[self.history_index])

    def nextCommand(self):
        if not self.command_history:
            return
            
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.inputField.setText(self.command_history[self.history_index])
        else:
            self.history_index = len(self.command_history)
            self.inputField.clear()

    def toggle_logging(self):
        if self.log_file:
            self.stopLogging()
        else:
            self.startLogging()
            
        # Mettre à jour le texte du menu
        if self.log_file:
            self.logFileAction.setText("Arrêter enregistrement")
        else:
            self.logFileAction.setText("Démarrer enregistrement...")

    def startLogging(self, automatic=False):
        """
        Démarre l'enregistrement des données dans un fichier log.
        
        Args:
            automatic (bool): Si True, utilise le chemin prédéfini dans les paramètres
        """
        # Si déjà en train d'enregistrer, arrêter d'abord
        if self.log_file:
            self.stopLogging()
            
        try:
            if automatic and self.savePathInput.text():
                # En mode automatique, utiliser le chemin prédéfini
                path = self.savePathInput.text()
                if not os.path.isdir(path):
                    os.makedirs(path, exist_ok=True)
                filename = os.path.join(path, f"terminal_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            else:
                # Demander à l'utilisateur où enregistrer le fichier
                filename, _ = QFileDialog.getSaveFileName(
                    self, 'Enregistrer le log', 
                    f"terminal_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    'Fichiers texte (*.txt);;Tous les fichiers (*.*)'
                )
                
            if filename:
                # Utiliser un gestionnaire de contexte pour ouvrir le fichier
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"--- Log démarré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                
                # Garder le fichier ouvert pour l'écriture continue
                self.log_file = open(filename, 'a', encoding='utf-8')
                
                self.appendFormattedText(f'[Système] Enregistrement démarré: {filename}\n', QColor("green"))
                self.logFileAction.setText("Arrêter enregistrement")
                self.statusBarWidget.showMessage(f"Enregistrement en cours: {os.path.basename(filename)}")
        except Exception as e:
            self.showMessage(f"Erreur lors de l'enregistrement: {str(e)}", error=True)

    def stopLogging(self):
        if self.log_file:
            try:
                self.log_file.write(f"--- Log terminé le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                self.log_file.close()
                self.appendFormattedText('[Système] Enregistrement terminé\n', QColor("orange"))
                self.logFileAction.setText("Démarrer enregistrement...")
                self.statusBarWidget.showMessage("Enregistrement terminé", 3000)
            except Exception as e:
                self.showMessage(f"Erreur lors de la fermeture du log: {str(e)}", error=True)
            finally:
                self.log_file = None

    def saveTerminalContent(self):
        """
        Enregistre le contenu actuel du terminal dans un fichier texte.
        """
        try:
            # Proposer un nom de fichier avec la date et l'heure actuelles
            default_filename = f"terminal_contenu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            filename, _ = QFileDialog.getSaveFileName(
                self, 'Enregistrer le contenu du terminal', 
                default_filename,
                'Fichiers texte (*.txt);;Tous les fichiers (*.*)'
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.terminal.toPlainText())
                self.statusBarWidget.showMessage(f"Contenu enregistré dans {os.path.basename(filename)}", 3000)
        except Exception as e:
            self.showMessage(f"Erreur lors de l'enregistrement: {str(e)}", error=True)

    def copyText(self):
        self.terminal.copy()

    def pasteText(self):
        self.inputField.paste()

    def changeFont(self):
        font, ok = QFontDialog.getFont(self.terminal.font(), self)
        if ok:
            self.terminal.setFont(font)
            self.settings.setValue("terminal/font", font.toString())

    def changeTextColor(self):
        color = QColorDialog.getColor(self.terminal.textColor(), self)
        if color.isValid():
            # Appliquer la couleur du texte via le style
            self.terminal.setStyleSheet(f"background-color: {self.defaultBgColor.name()}; color: {color.name()};")
            self.defaultTextColor = color
            self.settings.setValue("terminal/textColor", color.name())
            
    def changeBgColor(self):
        color = QColorDialog.getColor(self.terminal.palette().base().color(), self)
        if color.isValid():
            # Appliquer la couleur de fond via le style
            self.terminal.setStyleSheet(f"background-color: {color.name()}; color: {self.defaultTextColor.name()};")
            self.defaultBgColor = color
            self.settings.setValue("terminal/bgColor", color.name())

    def get_light_palette(self):
        palette = QPalette()
        # Palette claire par défaut (Fusion)
        return palette

    def get_dark_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, QColor('white'))
        palette.setColor(QPalette.Base, QColor(42, 42, 42))
        palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
        palette.setColor(QPalette.ToolTipBase, QColor('white'))
        palette.setColor(QPalette.ToolTipText, QColor('white'))
        palette.setColor(QPalette.Text, QColor('white'))
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, QColor('white'))
        return palette

    def get_hacker_palette(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        palette.setColor(QPalette.WindowText, QColor(0, 255, 0))
        palette.setColor(QPalette.Base, QColor(0, 0, 0))
        palette.setColor(QPalette.Text, QColor(0, 255, 0))
        palette.setColor(QPalette.Button, QColor(10, 30, 10))
        palette.setColor(QPalette.ButtonText, QColor(0, 255, 0))
        palette.setColor(QPalette.Highlight, QColor(0, 255, 0))
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        return palette

    def applyTheme(self, theme):
        """Applique un thème à l'application et au terminal."""
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create('Fusion'))

        if theme == 'clair':
            palette = self.get_light_palette()
            app.setPalette(palette)
            self.terminal.setFont(QFont("Consolas", 12))
            self.terminal.setStyleSheet("background-color: white; color: black;")
            self.defaultTextColor = QColor("black")
            self.defaultBgColor = QColor("white")

        elif theme == 'sombre':
            palette = self.get_dark_palette()
            app.setPalette(palette)
            self.terminal.setFont(QFont("Consolas", 12))
            self.terminal.setStyleSheet(f"background-color: {palette.color(QPalette.Base).name()}; color: white;")
            self.defaultTextColor = QColor("white")
            self.defaultBgColor = palette.color(QPalette.Base)

        elif theme == 'hacker':
            palette = self.get_hacker_palette()
            app.setPalette(palette)
            self.terminal.setFont(QFont("Courier New", 12, QFont.Bold))
            self.terminal.setStyleSheet("background-color: black; color: rgb(0, 255, 0);")
            self.defaultTextColor = QColor(0, 255, 0)
            self.defaultBgColor = QColor("black")

        self.settings.setValue("global/theme", theme)

    def resetConfig(self):
        # Réinitialiser les paramètres d'affichage
        # Réinitialise au thème sombre par défaut
        self.applyTheme('sombre') 
        
        # Réinitialiser les paramètres dans le stockage
        self.settings.remove("terminal/font")
        self.settings.remove("terminal/textColor")
        self.settings.remove("terminal/bgColor")
        self.settings.remove("global/theme") # Utiliser la clé globale
        
        self.statusBarWidget.showMessage("Configuration d'affichage réinitialisée", 3000)

    def showMessage(self, message, error=False):
        if error:
            QMessageBox.critical(self, "Erreur", message)
        else:
            QMessageBox.information(self, "Information", message)

    def showChecksumCalculator(self):
        dialog = ChecksumCalculator(self)
        dialog.exec_()

    def showConverter(self):
        dialog = DataConverter(self)
        dialog.exec_()

    def showShortcuts(self):
        """
        Affiche une boîte de dialogue avec la liste des raccourcis clavier.
        """
        shortcuts_text = (
            "Raccourcis clavier :\n\n"
            "Ctrl+K : Connecter/Déconnecter\n"
            "Ctrl+C : Effacer le terminal\n"
            "Ctrl+S : Enregistrer le contenu du terminal\n"
            "Ctrl+L : Démarrer/Arrêter l'enregistrement\n"
            "Ctrl+T : Afficher/Masquer le panneau d'envoi\n"
            "Flèche haut : Commande précédente\n"
            "Flèche bas : Commande suivante\n"
        )
        
        QMessageBox.information(self, "Raccourcis clavier", shortcuts_text)

    def showAbout(self):
        QMessageBox.about(
            self, 
            "À propos du Terminal Série",
            "Terminal de Communication Série Avancé v1.0\n\n"
            "Un outil complet pour la communication série avec de nombreuses fonctionnalités.\n\n"
            "© Manu - 2025 - Terminal Série"
        )

    def browseSavePath(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier de sauvegarde", 
            self.savePathInput.text() or os.path.expanduser("~")
        )
        if folder:
            self.savePathInput.setText(folder)

    def saveSettings(self):
        # Paramètres de connexion
        self.settings.setValue("connection/port", self.portSelect.currentText())
        self.settings.setValue("connection/baud", self.baudSelect.currentText())
        self.settings.setValue("connection/data", self.dataSelect.currentText())
        self.settings.setValue("connection/parity", self.paritySelect.currentText())
        self.settings.setValue("connection/stop", self.stopSelect.currentText())
        self.settings.setValue("connection/flow", self.flowSelect.currentText())
        
        # Paramètres d'affichage
        self.settings.setValue("display/format", self.displayFormat.currentText())
        self.settings.setValue("display/autoscroll", self.scrollCheckBox.isChecked())
        self.settings.setValue("display/sendPanelVisible", self.inputGroup.isVisible()) # Sauvegarder la visibilité
        self.settings.setValue("display/timestamp", self.timestampCheckBox.isChecked())
        
        # Paramètres d'envoi
        self.settings.setValue("send/format", self.formatSelect.currentText())
        self.settings.setValue("send/eol", self.nlcrChoice.currentText())
        
        # Paramètres avancés
        self.settings.setValue("advanced/bufferSize", self.bufferSizeInput.text())
        self.settings.setValue("advanced/filter", self.filterInput.text())
        self.settings.setValue("advanced/enableFilter", self.enableFilterCheck.isChecked())
        self.settings.setValue("advanced/showRawBytes", self.showRawBytesCheck.isChecked())
        self.settings.setValue("advanced/showTiming", self.showTimingCheck.isChecked())
        self.settings.setValue("advanced/autoSave", self.autoSaveCheck.isChecked())
        self.settings.setValue("advanced/savePath", self.savePathInput.text())
        
        # Commandes prédéfinies
        self.settings.setValue("commands/list", self.commandsTextEdit.toPlainText())
        
        # Visibilité des onglets
        self.settings.setValue("tabs/esp_visible", self.espTabAction.isChecked())
        self.settings.setValue("tabs/bt_visible", self.btTabAction.isChecked())
        
        self.statusBarWidget.showMessage("Paramètres sauvegardés", 3000)

    def loadSettings(self):
        # Paramètres de connexion
        port = self.settings.value("connection/port", "")
        if port and port in [self.portSelect.itemText(i) for i in range(self.portSelect.count())]:
            self.portSelect.setCurrentText(port)
            
        baud = self.settings.value("connection/baud", "115200")
        if baud in [self.baudSelect.itemText(i) for i in range(self.baudSelect.count())]:
            self.baudSelect.setCurrentText(baud)
            
        data = self.settings.value("connection/data", "8")
        if data in [self.dataSelect.itemText(i) for i in range(self.dataSelect.count())]:
            self.dataSelect.setCurrentText(data)
            
        parity = self.settings.value("connection/parity", "Aucune")
        if parity in [self.paritySelect.itemText(i) for i in range(self.paritySelect.count())]:
            self.paritySelect.setCurrentText(parity)
            
        stop = self.settings.value("connection/stop", "1")
        if stop in [self.stopSelect.itemText(i) for i in range(self.stopSelect.count())]:
            self.stopSelect.setCurrentText(stop)
            
        flow = self.settings.value("connection/flow", "Aucun")
        if flow in [self.flowSelect.itemText(i) for i in range(self.flowSelect.count())]:
            self.flowSelect.setCurrentText(flow)
        
        # Paramètres d'affichage
        display_format = self.settings.value("display/format", "ASCII")
        if display_format in [self.displayFormat.itemText(i) for i in range(self.displayFormat.count())]:
            self.displayFormat.setCurrentText(display_format)
            
        self.scrollCheckBox.setChecked(self.settings.value("display/autoscroll", True, type=bool))
        self.timestampCheckBox.setChecked(self.settings.value("display/timestamp", False, type=bool))
        
        # Charger la visibilité du panneau d'envoi
        send_panel_visible = self.settings.value("display/sendPanelVisible", True, type=bool)
        self.inputGroup.setVisible(send_panel_visible)
        self.toggleSendPanelAction.setChecked(send_panel_visible) # Mettre à jour l'état de l'action
        
        # Paramètres d'envoi
        send_format = self.settings.value("send/format", "ASCII")
        if send_format in [self.formatSelect.itemText(i) for i in range(self.formatSelect.count())]:
            self.formatSelect.setCurrentText(send_format)
            
        eol = self.settings.value("send/eol", "Aucun")
        if eol in [self.nlcrChoice.itemText(i) for i in range(self.nlcrChoice.count())]:
            self.nlcrChoice.setCurrentText(eol)
        
        # Paramètres avancés
        try:
            self.bufferSizeInput.setText(self.settings.value("advanced/bufferSize", "10000"))
            self.filterInput.setText(self.settings.value("advanced/filter", ""))
            self.enableFilterCheck.setChecked(self.settings.value("advanced/enableFilter", False, type=bool))
            self.showRawBytesCheck.setChecked(self.settings.value("advanced/showRawBytes", False, type=bool))
            self.showTimingCheck.setChecked(self.settings.value("advanced/showTiming", False, type=bool))
            self.autoSaveCheck.setChecked(self.settings.value("advanced/autoSave", False, type=bool))
            self.savePathInput.setText(self.settings.value("advanced/savePath", ""))
        except AttributeError:
            # Ces attributs pourraient ne pas être initialisés lors du premier appel
            pass
        
        # Commandes prédéfinies
        try:
            commands_text = self.settings.value("commands/list", "")
            self.commandsTextEdit.setPlainText(commands_text)
            self.updateCommandButtons()
        except AttributeError:
            pass
        
        # Appliquer les paramètres d'apparence
        # Charger et appliquer le thème global en dernier pour qu'il prime
        # sur les couleurs individuelles sauvegardées précédemment (si elles existent)
        try:
            theme = self.settings.value("global/theme", "sombre") # Défaut sombre
            if theme in ["clair", "sombre", "hacker"]:
                self.applyTheme(theme)
        except Exception:
            pass  # Ignorer les erreurs de configuration d'apparence

        # Restaurer la géométrie de la fenêtre (taille et position)
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def saveCommands(self):
        """
        Sauvegarde les commandes définies dans les paramètres.
        Limite le nombre de commandes au maximum défini dans la configuration.
        """
        # Récupérer les commandes du TextEdit
        commands_text = self.commandsTextEdit.toPlainText()
        
        # Limiter le nombre de commandes
        commands = []
        for line in commands_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    name, cmd = line.split('=', 1)
                    commands.append(line)
                except ValueError:
                    continue
        
        # Limiter au nombre maximum de commandes
        if len(commands) > self.max_saved_commands:
            commands = commands[:self.max_saved_commands]
            limited_text = '\n'.join(commands)
            self.commandsTextEdit.setPlainText(limited_text)
            self.showMessage(f"Le nombre de commandes a été limité à {self.max_saved_commands}.")
            logger.info(f"Nombre de commandes limité à {self.max_saved_commands}")
            
        # Sauvegarder les commandes dans les paramètres
        self.settings.setValue("commands/list", self.commandsTextEdit.toPlainText())
        self.updateCommandButtons()
        self.statusBarWidget.showMessage("Commandes sauvegardées", 3000)

    def loadCommands(self):
        """
        Charge les commandes depuis les paramètres.
        """
        commands_text = self.settings.value("commands/list", "")
        self.commandsTextEdit.setPlainText(commands_text)
        self.updateCommandButtons()
        self.statusBarWidget.showMessage("Commandes chargées", 3000)
        
    def clearCommands(self):
        """
        Efface toutes les commandes sauvegardées.
        """
        # Demander confirmation avant d'effacer
        reply = QMessageBox.question(
            self, 
            'Confirmation', 
            'Êtes-vous sûr de vouloir effacer toutes les commandes ?',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Effacer le contenu du TextEdit
            self.commandsTextEdit.clear()
            
            # Effacer les commandes dans les paramètres
            self.settings.remove("commands/list")
            
            # Mettre à jour les boutons
            self.updateCommandButtons()
            
            self.statusBarWidget.showMessage("Commandes effacées", 3000)
            logger.info("Toutes les commandes ont été effacées")

    def updateCommandButtons(self):
        """
        Met à jour les boutons de raccourcis pour les commandes sauvegardées.
        Limite le nombre de boutons au maximum défini dans la configuration.
        """
        # Effacer les boutons existants
        while self.shortcutButtonsLayout.count():
            item = self.shortcutButtonsLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Analyser les commandes définies
        text = self.commandsTextEdit.toPlainText()
        command_count = 0
        
        for line in text.split('\n'):
            # Limiter au nombre maximum de commandes
            if command_count >= self.max_saved_commands:
                break
                
            line = line.strip()
            if line and not line.startswith('#'):
                try:
                    name, cmd = line.split('=', 1)
                    name = name.strip()
                    cmd = cmd.strip()
                    
                    # Créer un bouton pour cette commande
                    btn = QPushButton(name)
                    btn.setToolTip(cmd)
                    # Utiliser une fonction lambda avec une valeur par défaut pour capturer la valeur actuelle
                    btn.clicked.connect(lambda checked, cmd=cmd: self.executeCommand(cmd))
                    self.shortcutButtonsLayout.addWidget(btn)
                    command_count += 1
                except ValueError:
                    continue  # Ignorer les lignes mal formées
        
        # Ajouter un spacer à la fin pour l'alignement
        self.shortcutButtonsLayout.addStretch()
        
        # Afficher le nombre de commandes
        if command_count > 0:
            logger.debug(f"{command_count} commandes chargées dans les raccourcis")

    def executeCommand(self, cmd):
        self.inputField.setText(cmd)
        # Basculer vers l'onglet Terminal
        self.tabWidget.setCurrentWidget(self.terminalTab)
        if not self.repeatCheck.isChecked():  # Ne pas envoyer automatiquement en mode répétition
            self.sendData()

    def toggleSendPanelVisibility(self):
        is_visible = not self.inputGroup.isVisible()
        self.inputGroup.setVisible(is_visible)
        self.toggleSendPanelAction.setChecked(is_visible) # Mettre à jour l'état de l'action
        
    def setupEspAtCommandsTab(self):
        """
        Crée un onglet pour les commandes AT ESP01 avec des explications.
        """
        # Créer l'onglet
        self.espAtTab = QWidget()
        tabIndex = self.tabWidget.addTab(self.espAtTab, "Commandes AT ESP01")
        self.commandTabs['esp'] = {'tab': self.espAtTab, 'index': tabIndex}
        
        # Layout principal
        mainLayout = QVBoxLayout(self.espAtTab)
        
        # Texte d'explication
        infoLabel = QLabel("Cliquez sur une commande pour l'insérer dans la barre d'envoi.")
        infoLabel.setWordWrap(True)
        mainLayout.addWidget(infoLabel)
        
        # Zone de défilement
        scrollArea = QWidget()
        scrollLayout = QVBoxLayout(scrollArea)
        
        # Parcourir les catégories de commandes
        for category in ESP_AT_COMMANDS:
            # Créer un groupe pour chaque catégorie
            categoryGroup = QGroupBox(category["category"])
            categoryGroup.setCheckable(True)
            categoryGroup.setChecked(False)
            
            # Layout pour les commandes de cette catégorie
            commandsLayout = QVBoxLayout()
            commandsWidget = QWidget()
            commandsWidget.setLayout(commandsLayout)
            
            # Ajouter chaque commande
            for cmd in category["commands"]:
                # Créer un layout pour chaque commande
                cmdLayout = QVBoxLayout()
                
                # Bouton pour la commande
                cmdBtn = QPushButton(cmd["command"])
                cmdBtn.setStyleSheet("text-align: left; padding: 5px;")
                cmdBtn.setToolTip(cmd["description"])
                # Connecter le bouton à la méthode executeCommand
                cmdBtn.clicked.connect(lambda checked, c=cmd["command"]: self.executeCommand(c))
                cmdLayout.addWidget(cmdBtn)
                
                # Description de la commande
                descLabel = QLabel(cmd["description"])
                descLabel.setWordWrap(True)
                descLabel.setStyleSheet("color: gray; margin-left: 10px;")
                cmdLayout.addWidget(descLabel)
                
                # Ajouter un séparateur
                cmdLayout.addWidget(QLabel(""))
                
                # Ajouter ce layout au layout de la catégorie
                commandsLayout.addLayout(cmdLayout)
            
            # Configurer le groupe de catégorie
            categoryLayout = QVBoxLayout()
            categoryLayout.addWidget(commandsWidget)
            categoryGroup.setLayout(categoryLayout)
            
            # Connecter le signal toggled pour afficher/masquer les commandes
            categoryGroup.toggled.connect(lambda checked, w=commandsWidget: w.setVisible(checked))
            commandsWidget.setVisible(False)
            
            # Ajouter le groupe au layout principal
            scrollLayout.addWidget(categoryGroup)
        
        # Ajouter un espace extensible à la fin
        scrollLayout.addStretch()
        
        # Créer une zone de défilement
        scrollWidget = QScrollArea()
        scrollWidget.setWidgetResizable(True)
        scrollWidget.setWidget(scrollArea)
        
        # Ajouter la zone de défilement au layout principal
        mainLayout.addWidget(scrollWidget)
        
    def setupBtAtCommandsTab(self):
        """
        Crée un onglet pour les commandes AT des modules Bluetooth HC-05/HC-06 avec des explications.
        """
        # Créer l'onglet
        self.btAtTab = QWidget()
        tabIndex = self.tabWidget.addTab(self.btAtTab, "Commandes AT Bluetooth")
        self.commandTabs['bt'] = {'tab': self.btAtTab, 'index': tabIndex}
        
        # Layout principal
        mainLayout = QVBoxLayout(self.btAtTab)
        
        # Texte d'explication
        infoLabel = QLabel("Cliquez sur une commande pour l'insérer dans la barre d'envoi. Compatible avec les modules HC-05 et HC-06.")
        infoLabel.setWordWrap(True)
        mainLayout.addWidget(infoLabel)
        
        # Zone de défilement
        scrollArea = QWidget()
        scrollLayout = QVBoxLayout(scrollArea)
        
        # Parcourir les catégories de commandes
        for category in BT_AT_COMMANDS:
            # Créer un groupe pour chaque catégorie
            categoryGroup = QGroupBox(category["category"])
            categoryGroup.setCheckable(True)
            categoryGroup.setChecked(False)
            
            # Layout pour les commandes de cette catégorie
            commandsLayout = QVBoxLayout()
            commandsWidget = QWidget()
            commandsWidget.setLayout(commandsLayout)
            
            # Ajouter chaque commande
            for cmd in category["commands"]:
                # Créer un layout pour chaque commande
                cmdLayout = QVBoxLayout()
                
                # Bouton pour la commande
                cmdBtn = QPushButton(cmd["command"])
                cmdBtn.setStyleSheet("text-align: left; padding: 5px;")
                cmdBtn.setToolTip(cmd["description"])
                # Connecter le bouton à la méthode executeCommand
                cmdBtn.clicked.connect(lambda checked, c=cmd["command"]: self.executeCommand(c))
                cmdLayout.addWidget(cmdBtn)
                
                # Description de la commande
                descLabel = QLabel(cmd["description"])
                descLabel.setWordWrap(True)
                descLabel.setStyleSheet("color: gray; margin-left: 10px;")
                cmdLayout.addWidget(descLabel)
                
                # Ajouter un séparateur
                cmdLayout.addWidget(QLabel(""))
                
                # Ajouter ce layout au layout de la catégorie
                commandsLayout.addLayout(cmdLayout)
            
            # Configurer le groupe de catégorie
            categoryLayout = QVBoxLayout()
            categoryLayout.addWidget(commandsWidget)
            categoryGroup.setLayout(categoryLayout)
            
            # Connecter le signal toggled pour afficher/masquer les commandes
            categoryGroup.toggled.connect(lambda checked, w=commandsWidget: w.setVisible(checked))
            commandsWidget.setVisible(False)
            
            # Ajouter le groupe au layout principal
            scrollLayout.addWidget(categoryGroup)
        
        # Ajouter un espace extensible à la fin
        scrollLayout.addStretch()
        
        # Créer une zone de défilement
        scrollWidget = QScrollArea()
        scrollWidget.setWidgetResizable(True)
        scrollWidget.setWidget(scrollArea)
        
        # Ajouter la zone de défilement au layout principal
        mainLayout.addWidget(scrollWidget)
        
    def toggleCommandTab(self, tab_id, visible):
        """
        Affiche ou masque un onglet de commandes AT.
        
        Args:
            tab_id (str): Identifiant de l'onglet ('esp' ou 'bt')
            visible (bool): True pour afficher, False pour masquer
        """
        if tab_id in self.commandTabs:
            tab_info = self.commandTabs[tab_id]
            if visible:
                # Si l'onglet n'est pas déjà présent, l'ajouter
                if self.tabWidget.indexOf(tab_info['tab']) == -1:
                    self.tabWidget.insertTab(tab_info['index'], tab_info['tab'], 
                                           "Commandes AT ESP01" if tab_id == 'esp' else "Commandes AT Bluetooth")
            else:
                # Si l'onglet est présent, le retirer
                index = self.tabWidget.indexOf(tab_info['tab'])
                if index != -1:
                    self.tabWidget.removeTab(index)
            
            # Sauvegarder l'état de visibilité
            self.settings.setValue(f"tabs/{tab_id}_visible", visible)
            
    def loadCommandTabsVisibility(self):
        """
        Charge l'état de visibilité des onglets de commandes AT depuis les paramètres.
        """
        # Charger l'état de l'onglet ESP01
        esp_visible = self.settings.value("tabs/esp_visible", True, type=bool)
        self.espTabAction.setChecked(esp_visible)
        self.toggleCommandTab('esp', esp_visible)
        
        # Charger l'état de l'onglet Bluetooth
        bt_visible = self.settings.value("tabs/bt_visible", True, type=bool)
        self.btTabAction.setChecked(bt_visible)
        self.toggleCommandTab('bt', bt_visible)

    def closeEvent(self, event):
        # Déconnecter proprement
        if self.serial_port and self.serial_port.is_open:
            self.disconnect()
            
        # Sauvegarder les paramètres
        self.saveSettings()
        
        # Sauvegarder la géométrie de la fenêtre
        self.settings.setValue("geometry", self.saveGeometry())
        
        # Accepter l'événement pour fermer l'application
        event.accept()

    def toggleAutoScroll(self):
        # Si la case est cochée, s'assurer que le curseur est visible (fait défiler vers le bas)
        if self.scrollCheckBox.isChecked():
            self.terminal.ensureCursorVisible()
        # Si la case est décochée, aucune action immédiate n'est nécessaire ici.
        # Le comportement est géré dans appendFormattedText qui ne forcera plus
        # le défilement vers le bas lors de l'ajout de nouveau texte.

    @pyqtSlot()
    def updateStatusBar(self):
        """Met à jour le label des compteurs RX/TX dans la barre de statut."""
        self.statusRxTxLabel.setText(f"RX: {self.rx_bytes_count} | TX: {self.tx_bytes_count}")


def setup_dark_palette():
    """
    Crée et retourne une palette de couleurs sombre pour l'application.
    
    Returns:
        QPalette: Palette de couleurs sombre
    """
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(42, 42, 42)) # Fond des zones de texte/liste
    dark_palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white) # Texte général
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    return dark_palette

def setup_application():
    """
    Configure l'application avec les paramètres par défaut.
    
    Returns:
        QApplication: L'application configurée
    """
    app = QApplication(sys.argv)

    # Définir la police par défaut pour toute l'application
    default_font = QFont("Arial", 12)
    app.setFont(default_font)

    # Appliquer un style et une palette sombre
    app.setStyle(QStyleFactory.create('Fusion'))
    app.setPalette(setup_dark_palette())
    
    return app

if __name__ == "__main__":
    # Configuration de l'application avant de créer la fenêtre
    app = setup_application()
    
    # Créer et afficher la fenêtre principale
    terminal = Terminal()
    
    # Exécuter l'application
    sys.exit(app.exec_())
