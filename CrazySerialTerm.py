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

# Configuration du système de journalisation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("serial_terminal.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CrazySerialTerm")

# Bibliothèques PyQt5
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QTextEdit, QLineEdit, QMainWindow, QMenu, QAction, QFontDialog, QColorDialog, 
                             QMessageBox, QInputDialog, QStyleFactory, QCheckBox, QSpacerItem, QSizePolicy,
                             QFileDialog, QToolBar, QStatusBar, QGroupBox, QTabWidget, QShortcut, QDialog, QGridLayout)
from PyQt5.QtGui import QColor, QTextCursor, QFont, QKeySequence, QIcon, QPalette, QTextCharFormat
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot, QTimer, QSettings

# Bibliothèques tierces
import serial
import serial.tools.list_ports

# Modules locaux
from checksum_calculator import ChecksumCalculator
from data_converter import DataConverter

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
    DEFAULT_BUFFER_SIZE = 10000
    
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
        self.rx_bytes_count: int = 0
        self.tx_bytes_count: int = 0
        self.last_receive_time: Optional[datetime] = None
        
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
        self.setMinimumWidth(500)  # Largeur minimale
        
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
        self.layout = QVBoxLayout(self.terminalTab)
        
        # Panneau de configuration de connexion
        self.setupConnectionPanel()
        
        # Zone de terminal avec affichage formaté
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)  # Terminal en lecture seule
        font = QFont("Consolas", 12) # Police par défaut du terminal en taille 12
        self.terminal.setFont(font)
        self.layout.addWidget(self.terminal, 4)  # Donner plus d'espace au terminal
        
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
        
        self.show()
        self.resize(500, 500)  # <-- Place ceci après self.show()

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
        self.layout.addWidget(self.connectionGroup)

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

        # Options d'envoi
        optionsGroup = QGroupBox("Options d'envoi")
        optionsLayout = QHBoxLayout() # Utiliser un layout horizontal

        # Format d'envoi (ASCII/HEX)
        optionsLayout.addWidget(QLabel('Format :'))
        self.formatSelect = QComboBox()
        self.formatSelect.addItems(['ASCII', 'HEX'])
        optionsLayout.addWidget(self.formatSelect)

        # Fin de ligne
        optionsLayout.addWidget(QLabel('Fin de ligne :'))
        self.nlcrChoice = QComboBox()
        self.nlcrChoice.addItems(['Aucun', 'NL', 'CR', 'NL+CR'])
        optionsLayout.addWidget(self.nlcrChoice)

        # Répétition
        self.repeatCheck = QCheckBox('Répéter')
        optionsLayout.addWidget(self.repeatCheck)

        # Intervalle
        optionsLayout.addWidget(QLabel('Intervalle (ms) :'))
        self.repeatInterval = QLineEdit('1000')
        self.repeatInterval.setFixedWidth(60)
        optionsLayout.addWidget(self.repeatInterval)
        
        optionsLayout.addStretch() # Ajouter un espace extensible à la fin

        optionsGroup.setLayout(optionsLayout)
        inputLayout.addWidget(optionsGroup)

        self.inputGroup.setLayout(inputLayout) # Utiliser self.inputGroup
        self.layout.addWidget(self.inputGroup) # Utiliser self.inputGroup

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
        
        viewMenu.addSeparator()
        
        # Sous-menu des thèmes
        themesMenu = viewMenu.addMenu('Thèmes')
        
        # Thèmes prédéfinis
        lightThemeAction = QAction('Thème clair', self)
        lightThemeAction.triggered.connect(lambda: self.applyTheme('clair'))
        themesMenu.addAction(lightThemeAction)
        
        darkThemeAction = QAction('Thème sombre', self)
        darkThemeAction.triggered.connect(lambda: self.applyTheme('sombre'))
        themesMenu.addAction(darkThemeAction)
        
        hackerThemeAction = QAction('Thème hacker', self)
        hackerThemeAction.triggered.connect(lambda: self.applyTheme('hacker'))
        themesMenu.addAction(hackerThemeAction)
        
        # Sous-menu de personnalisation
        customizeMenu = viewMenu.addMenu('Personnaliser')
        
        # Changer la police
        fontAction = QAction('Changer la police', self)
        fontAction.triggered.connect(self.changeFont)
        customizeMenu.addAction(fontAction)
        
        # Changer la couleur du texte
        textColorAction = QAction('Couleur du texte', self)
        textColorAction.triggered.connect(self.changeTextColor)
        customizeMenu.addAction(textColorAction)
        
        # Changer la couleur du fond
        bgColorAction = QAction('Couleur du fond', self)
        bgColorAction.triggered.connect(self.changeBgColor)
        customizeMenu.addAction(bgColorAction)
        
        # Réinitialiser la vue
        resetViewAction = QAction('Réinitialiser l\'apparence', self)
        resetViewAction.setToolTip("Réinitialise l'apparence au thème sombre par défaut")
        resetViewAction.triggered.connect(self.resetConfig)
        viewMenu.addAction(resetViewAction)
        
        # Menu Outils
        toolsMenu = self.menuBar().addMenu('Outils')
        
        # Calculatrice checksum
        checksumAction = QAction('Calculatrice Checksum', self)
        checksumAction.triggered.connect(self.showChecksumCalculator)
        toolsMenu.addAction(checksumAction)
        
        # Convertisseur de données
        convertAction = QAction('Convertisseur (ASCII/HEX)', self)
        convertAction.triggered.connect(self.showConverter)
        toolsMenu.addAction(convertAction)
        
        # Menu Aide
        helpMenu = self.menuBar().addMenu('Aide')
        
        # Raccourcis clavier
        shortcutsAction = QAction('Raccourcis clavier', self)
        shortcutsAction.triggered.connect(self.showShortcuts)
        helpMenu.addAction(shortcutsAction)
        
        # À propos
        aboutAction = QAction('À propos', self)
        aboutAction.triggered.connect(self.showAbout)
        helpMenu.addAction(aboutAction)

    def setupAdvancedTab(self):
        # Onglet des paramètres avancés
        self.advancedTab = QWidget()
        self.tabWidget.addTab(self.advancedTab, "Paramètres avancés")
        advancedLayout = QVBoxLayout(self.advancedTab)
        
        # Groupe pour les options d'affichage
        displayGroup = QGroupBox("Options d'affichage")
        displayLayout = QGridLayout()
        
        # Format des données reçues
        displayLayout.addWidget(QLabel('Format d\'affichage:'), 0, 0)
        displayLayout.addWidget(self.displayFormat, 0, 1)
        
        # Défilement automatique
        displayLayout.addWidget(self.scrollCheckBox, 1, 0, 1, 2)
        
        # Timestamp
        displayLayout.addWidget(self.timestampCheckBox, 2, 0, 1, 2)
        
        displayGroup.setLayout(displayLayout)
        advancedLayout.addWidget(displayGroup)
        
        # Groupe pour les paramètres de connexion avancés
        serialGroup = QGroupBox("Paramètres de connexion avancés")
        serialLayout = QGridLayout()
        
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
        
        serialGroup.setLayout(serialLayout)
        advancedLayout.addWidget(serialGroup)
        
        # Groupe pour les paramètres du terminal
        terminalGroup = QGroupBox("Paramètres du terminal")
        terminalParamsLayout = QVBoxLayout()
        
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
        
        terminalGroup.setLayout(terminalParamsLayout)
        advancedLayout.addWidget(terminalGroup)
        
        # Groupe pour les paramètres de débogage
        debugGroup = QGroupBox("Débogage")
        debugLayout = QVBoxLayout()
        
        # Afficher les octets bruts
        self.showRawBytesCheck = QCheckBox("Afficher les octets bruts")
        debugLayout.addWidget(self.showRawBytesCheck)
        
        # Afficher les délais entre les trames
        self.showTimingCheck = QCheckBox("Afficher les délais entre les trames")
        debugLayout.addWidget(self.showTimingCheck)
        
        debugGroup.setLayout(debugLayout)
        advancedLayout.addWidget(debugGroup)
        
        # Groupe pour les paramètres de sauvegarde
        saveGroup = QGroupBox("Sauvegarde automatique")
        saveLayout = QVBoxLayout()
        
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
        
        saveGroup.setLayout(saveLayout)
        advancedLayout.addWidget(saveGroup)
        
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
        current_ports = set([port.device for port in serial.tools.list_ports.comports()])
        port_items = set([self.portSelect.itemText(i) for i in range(self.portSelect.count())])
        
        if current_ports != port_items:
            self.refreshPorts()

    def toggle_connection(self):
        if self.serial_port and self.serial_port.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """
        Établit une connexion avec le port série sélectionné en utilisant les paramètres configurés.
        """
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
                    self.read_thread.join(0.5)
                    
            # Fermer le port série en utilisant un bloc try-finally pour garantir la fermeture
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
                    logger.debug("Port série fermé avec succès")
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture du port série: {str(e)}")
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

    def readData(self):
        """
        Méthode exécutée dans un thread séparé pour lire les données du port série.
        Collecte les données et les envoie pour traitement.
        """
        last_time = datetime.now()
        buffer = bytearray()
        timeout_seconds = 0.1  # Timeout en secondes
        thread_sleep = 0.01    # Temps de pause pour éviter de saturer le CPU
        
        while self.read_thread_running and self.serial_port and self.serial_port.is_open:
            try:
                # Lire les données disponibles
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        # Ajouter au buffer
                        buffer.extend(data)
                        
                        # Si on a une fin de ligne ou un timeout, traiter les données
                        if b'\n' in buffer or (datetime.now() - last_time).total_seconds() > timeout_seconds:
                            self.processReceivedData(buffer)
                            buffer = bytearray()
                            last_time = datetime.now()
                else:
                    # Pause courte pour éviter de saturer le CPU
                    threading.Event().wait(thread_sleep)
                    
                    # Si le buffer contient des données et qu'un certain temps s'est écoulé
                    if buffer and (datetime.now() - last_time).total_seconds() > timeout_seconds:
                        self.processReceivedData(buffer)
                        buffer = bytearray()
                        last_time = datetime.now()
                        
            except serial.SerialException as e:
                self._handle_serial_error(str(e))
                break
            except Exception as e:
                self._handle_serial_error(f"Exception inattendue: {str(e)}")
                break
                
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
        QMetaObject.invokeMethod(self, "disconnect", Qt.QueuedConnection)

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
        
        # Vérifier si nous avons besoin de limiter la taille du buffer
        try:
            max_lines = int(self.bufferSizeInput.text())
            current_text = self.terminal.toPlainText()
            
            if current_text.count('\n') > max_lines:
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
            hex_text = ''.join(c for c in text if c.upper() in '0123456789ABCDEF')
            if len(hex_text) % 2 != 0:
                hex_text += '0'  # Ajouter un 0 si nombre impair de caractères
            return bytes.fromhex(hex_text) + eol
            
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
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(42, 42, 42))
        palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
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
        if not self.repeatCheck.isChecked():  # Ne pas envoyer automatiquement en mode répétition
            self.sendData()

    def toggleSendPanelVisibility(self):
        is_visible = not self.inputGroup.isVisible()
        self.inputGroup.setVisible(is_visible)
        self.toggleSendPanelAction.setChecked(is_visible) # Mettre à jour l'état de l'action

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
    