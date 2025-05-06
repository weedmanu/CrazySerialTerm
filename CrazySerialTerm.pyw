import sys
import threading
import signal
import os
import json
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QTextEdit, QLineEdit, QMainWindow, QMenu, QAction, QFontDialog, QColorDialog, 
                             QMessageBox, QInputDialog, QStyleFactory, QCheckBox, QSpacerItem, QSizePolicy,
                             QFileDialog, QToolBar, QStatusBar, QGroupBox, QTabWidget, QShortcut, QDialog, QGridLayout)
from PyQt5.QtGui import QColor, QTextCursor, QFont, QKeySequence, QIcon, QPalette, QTextCharFormat
from PyQt5.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot, QTimer, QSettings
import serial.tools.list_ports, re # Ajout de l'import re manquant
import serial

# Importer les dialogues depuis leurs fichiers séparés
from checksum_calculator import ChecksumCalculator
from data_converter import DataConverter

def resource_path(relative_path):
    """ Obtenir le chemin absolu vers la ressource, fonctionne pour dev et pour PyInstaller """
    try:
        # PyInstaller crée un dossier temporaire et stocke le chemin dans _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Non packagé, utiliser le chemin absolu du script
        base_path = os.path.abspath(".") # Ou os.path.dirname(__file__) pour être plus précis

    return os.path.join(base_path, relative_path)


class Terminal(QMainWindow):
    def __init__(self):
        super().__init__()
        # Configuration de base
        self.serial_port = None
        self.read_thread = None
        self.read_thread_running = False
        self.command_history = []
        self.history_index = -1
        self.settings = QSettings("SerialTerminal", "Settings")
        self.log_file = None
        self.rx_bytes_count = 0
        self.tx_bytes_count = 0
        
        self.initUI()
        # Utiliser la fonction resource_path pour trouver l'icône
        self.setWindowIcon(QIcon(resource_path('LogoFreeTermIco.ico')))        
        self.loadSettings()
        self.setupShortcuts()
        
        # Vérifier périodiquement les ports disponibles
        self.port_timer = QTimer()
        self.port_timer.timeout.connect(self.checkPorts)
        self.port_timer.start(5000)  # Vérifier toutes les 5 secondes

    def initUI(self):
        # Configuration de la fenêtre principale
        self.setWindowTitle('Terminal de Communication Série Avancé')
        self.resize(900, 600)
        
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
        
        # Créer la barre d'outils
        self.setupToolbar()
        
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
        
        # Panneau des options d'affichage
        self.setupDisplayOptionsPanel()
        
        # Créer les menus
        self.setupMenus()
        
        # Onglet de configuration avancée
        self.setupAdvancedTab()
        
        # Onglet des commandes prédéfinies
        self.setupCommandsTab()
        
        self.show()

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
        
        # Vitesse
        baudLayout = QHBoxLayout()
        baudLayout.addWidget(QLabel('Vitesse:'))
        self.baudSelect = QComboBox()
        self.baudSelect.addItems(['9600', '19200', '38400', '57600', '115200', '230400', '460800', '921600'])
        self.baudSelect.setCurrentText('115200')  # Vitesse par défaut moderne
        baudLayout.addWidget(self.baudSelect)
        connectionLayout.addLayout(baudLayout)
        
        # Bits de données
        dataLayout = QHBoxLayout()
        dataLayout.addWidget(QLabel('Bits:'))
        self.dataSelect = QComboBox()
        self.dataSelect.addItems(['5', '6', '7', '8'])
        self.dataSelect.setCurrentText('8')
        dataLayout.addWidget(self.dataSelect)
        connectionLayout.addLayout(dataLayout)
        
        # Parité
        parityLayout = QHBoxLayout()
        parityLayout.addWidget(QLabel('Parité:'))
        self.paritySelect = QComboBox()
        self.paritySelect.addItems(['Aucune', 'Paire', 'Impaire'])
        parityLayout.addWidget(self.paritySelect)
        connectionLayout.addLayout(parityLayout)
        
        # Bits de stop
        stopLayout = QHBoxLayout()
        stopLayout.addWidget(QLabel('Stop:'))
        self.stopSelect = QComboBox()
        self.stopSelect.addItems(['1', '1.5', '2'])
        stopLayout.addWidget(self.stopSelect)
        connectionLayout.addLayout(stopLayout)
        
        # Bouton de connexion
        self.connectBtn = QPushButton('Connecter')
        self.connectBtn.clicked.connect(self.toggle_connection)
        connectionLayout.addWidget(self.connectBtn)
        
        # Flux de contrôle
        flowLayout = QHBoxLayout()
        flowLayout.addWidget(QLabel('Contrôle:'))
        self.flowSelect = QComboBox()
        self.flowSelect.addItems(['Aucun', 'XON/XOFF', 'RTS/CTS', 'DSR/DTR'])
        flowLayout.addWidget(self.flowSelect)
        connectionLayout.addLayout(flowLayout)
        
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
        # Panel pour les options d'affichage
        displayGroup = QGroupBox("Options d'affichage")
        displayLayout = QHBoxLayout()
        
        # Défilement automatique
        self.scrollCheckBox = QCheckBox('Défilement automatique')
        self.scrollCheckBox.setChecked(True)
        self.scrollCheckBox.stateChanged.connect(self.toggleAutoScroll)  # Connecter à la méthode
        displayLayout.addWidget(self.scrollCheckBox)
        
        # Timestamp
        self.timestampCheckBox = QCheckBox('Afficher timestamps')
        displayLayout.addWidget(self.timestampCheckBox)
        
        # Format des données reçues
        displayLayout.addWidget(QLabel('Format d\'affichage:'))
        self.displayFormat = QComboBox()
        self.displayFormat.addItems(['ASCII', 'HEX', 'Les deux'])
        displayLayout.addWidget(self.displayFormat)
        
        # Bouton pour effacer
        self.clearBtn = QPushButton('Effacer')
        self.clearBtn.clicked.connect(self.clearTerminal)
        displayLayout.addWidget(self.clearBtn)
        
        displayGroup.setLayout(displayLayout)
        self.layout.addWidget(displayGroup)

    def setupMenus(self):
        # Menu Fichier
        fileMenu = self.menuBar().addMenu('Fichier')
        
        # Enregistrer le contenu du terminal
        saveAction = QAction('Enregistrer le terminal...', self)
        saveAction.triggered.connect(self.saveTerminalContent)
        fileMenu.addAction(saveAction)
        
        # Démarrer/arrêter l'enregistrement
        self.logFileAction = QAction('Démarrer enregistrement...', self)
        self.logFileAction.triggered.connect(self.startLogging)
        fileMenu.addAction(self.logFileAction)
        
        fileMenu.addSeparator()
        
        # Quitter
        exitAction = QAction('Quitter', self)
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)
        
        # Menu Edition
        editMenu = self.menuBar().addMenu('Edition')
        
        # Copier
        copyAction = QAction('Copier', self)
        copyAction.triggered.connect(self.copyText)
        editMenu.addAction(copyAction)
        
        # Coller
        pasteAction = QAction('Coller', self)
        pasteAction.triggered.connect(self.pasteText)
        editMenu.addAction(pasteAction)
        
        # Menu Vue
        viewMenu = self.menuBar().addMenu('Vue')
        
        # Changer la police
        self.fontAction = QAction('Changer la police', self)
        self.fontAction.triggered.connect(self.changeFont)
        viewMenu.addAction(self.fontAction)
        
        # Changer la couleur du texte
        self.textColorAction = QAction('Couleur du texte', self)
        self.textColorAction.triggered.connect(self.changeTextColor)
        viewMenu.addAction(self.textColorAction)
        
        # Changer la couleur du fond
        self.bgColorAction = QAction('Couleur du fond', self)
        self.bgColorAction.triggered.connect(self.changeBgColor)
        viewMenu.addAction(self.bgColorAction)
        
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
        
        # Réinitialiser la vue
        resetViewAction = QAction('Réinitialiser la vue', self)
        resetViewAction.setToolTip("Réinitialise l'apparence au thème sombre par défaut")
        resetViewAction.triggered.connect(self.resetConfig)
        viewMenu.addAction(resetViewAction)
        
        viewMenu.addSeparator()
        
        # Masquer/Afficher le panneau d'envoi
        self.toggleSendPanelAction = QAction('Afficher le panneau d\'envoi', self, checkable=True)
        self.toggleSendPanelAction.setChecked(True) # Visible par défaut
        self.toggleSendPanelAction.triggered.connect(self.toggleSendPanelVisibility)
        viewMenu.addAction(self.toggleSendPanelAction)
        
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
        
        # À propos
        aboutAction = QAction('À propos', self)
        aboutAction.triggered.connect(self.showAbout)
        helpMenu.addAction(aboutAction)

    def setupAdvancedTab(self):
        # Onglet des paramètres avancés
        self.advancedTab = QWidget()
        self.tabWidget.addTab(self.advancedTab, "Paramètres avancés")
        advancedLayout = QVBoxLayout(self.advancedTab)
        
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
        
        self.shortcutClear = QShortcut(QKeySequence("Ctrl+L"), self)
        self.shortcutClear.activated.connect(self.clearTerminal)
        
        self.shortcutSave = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcutSave.activated.connect(self.saveTerminalContent)
        
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
        port = self.portSelect.currentText()
        if not port:
            self.showMessage("Aucun port série disponible. Vérifiez les connexions.")
            return
            
        baud = int(self.baudSelect.currentText())
        
        # Configurer les paramètres avancés
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
        
        try:
            # Réinitialiser les compteurs RX/TX à la connexion
            self.rx_bytes_count = 0
            self.tx_bytes_count = 0
            self.updateStatusBar()
            
            self.serial_port = serial.Serial(
                port=port, 
                baudrate=baud,
                bytesize=data_bits,
                parity=parity,
                stopbits=stop_bits,
                timeout=0.1,
                **flow_settings
            )
            
            self.appendFormattedText(f'[Système] Connecté à {port} ({baud} bauds, {data_bits}{parity}{stop_bits})\n', QColor("green"))
            self.read_thread_running = True
            self.read_thread = threading.Thread(target=self.readData)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            self.connectBtn.setText('Déconnecter')
            self.connectAction.setText('Déconnecter')
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

    def disconnect(self):
        if self.serial_port:
            self.read_thread_running = False
            if self.read_thread:
                # Attendre un peu pour que le thread se termine proprement
                if self.read_thread.is_alive():
                    self.read_thread.join(0.5)
                    
            if self.serial_port.is_open:
                self.serial_port.close()
                
            self.serial_port = None
            self.read_thread = None
            
            # Si on avait un enregistrement en cours, le fermer
            self.stopLogging()
            
            # Arrêter le timer d'envoi répété s'il est actif
            if self.repeat_timer.isActive():
                self.repeat_timer.stop()
                self.repeatCheck.setChecked(False)
                
            self.appendFormattedText('[Système] Déconnecté\n', QColor("red"))
            self.connectBtn.setText('Connecter')
            self.connectAction.setText('Connecter')
            self.statusBarWidget.showMessage("Déconnecté", 3000)
        else:
            self.appendFormattedText('[Système] Aucune connexion active\n', QColor("orange"))

    def readData(self):
        last_time = datetime.now()
        buffer = bytearray()
        
        while self.read_thread_running and self.serial_port and self.serial_port.is_open:
            try:
                # Lire les données disponibles
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        # Ajouter au buffer
                        buffer.extend(data)
                        
                        # Si on a une fin de ligne ou un timeout, traiter les données
                        if b'\n' in buffer or (datetime.now() - last_time).total_seconds() > 0.1:
                            self.processReceivedData(buffer)
                            buffer = bytearray()
                            last_time = datetime.now()
                else:
                    # Pause courte pour éviter de saturer le CPU
                    threading.Event().wait(0.01)
                    
                    # Si le buffer contient des données et qu'un certain temps s'est écoulé
                    if buffer and (datetime.now() - last_time).total_seconds() > 0.1:
                        self.processReceivedData(buffer)
                        # Mettre à jour le compteur RX (fait dans processReceivedData)
                        # QMetaObject.invokeMethod(self, "updateStatusBar", Qt.QueuedConnection)
                        # Note: L'appel est déplacé dans processReceivedData pour compter les octets traités
                        
                        buffer = bytearray()
                        last_time = datetime.now()
                        
            except serial.SerialException as e:
                QMetaObject.invokeMethod(
                    self, 
                    "appendFormattedText", 
                    Qt.QueuedConnection, 
                    Q_ARG(str, f'[Erreur] {str(e)}\n'), 
                    Q_ARG(QColor, QColor("red"))
                )
                # En cas d'erreur, on tente de se déconnecter proprement
                QMetaObject.invokeMethod(self, "disconnect", Qt.QueuedConnection)
                break
            except Exception as e:
                QMetaObject.invokeMethod(
                    self, 
                    "appendFormattedText", 
                    Qt.QueuedConnection, 
                    Q_ARG(str, f'[Erreur] Exception inattendue: {str(e)}\n'), 
                    Q_ARG(QColor, QColor("red"))
                )
                break

    def processReceivedData(self, data):
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
                try:
                    text_data = data.decode('utf-8', errors='replace')
                except UnicodeDecodeError:
                    text_data = data.decode('latin-1', errors='replace')
                    
                display_text = text_data
                
            elif display_format == 'HEX':
                # Afficher en hexadécimal
                hex_data = ' '.join(f'{b:02X}' for b in data)
                display_text = hex_data
                
            else:  # "Les deux"
                # Afficher en ASCII et HEX
                try:
                    text_data = data.decode('utf-8', errors='replace')
                except UnicodeDecodeError:
                    text_data = data.decode('latin-1', errors='replace')
                    
                hex_data = ' '.join(f'{b:02X}' for b in data)
                display_text = f"{text_data} [{hex_data}]"
            
            # Afficher les timestamps si activé
            if self.timestampCheckBox.isChecked():
                now = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                
                # Afficher le délai entre les trames si activé
                if self.showTimingCheck.isChecked() and self.last_receive_time:
                    delta = datetime.now() - self.last_receive_time
                    ms = delta.total_seconds() * 1000
                    display_text = f"[{now} +{ms:.1f}ms] {display_text}"
                else:
                    display_text = f"[{now}] {display_text}"
                    
            self.last_receive_time = datetime.now()
                
            # Appliquer un filtre si activé
            if self.enableFilterCheck.isChecked() and self.filterInput.text():
                try:
                    pattern = self.filterInput.text()
                    if not re.search(pattern, display_text):
                        return  # Ne pas afficher si ne correspond pas au filtre
                except re.error:
                    pass  # Ignorer les erreurs de regex
            
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

    @pyqtSlot(str, QColor)
    def appendFormattedText(self, text, color=None):
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
                cursor.movePosition(QTextCursor.End)
            else:
                cursor = self.terminal.textCursor() # Obtenir le curseur seulement si on ne modifie pas tout le texte
        except (ValueError, AttributeError):
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

    def sendData(self):
        if not self.serial_port or not self.serial_port.is_open:
            self.appendFormattedText('[Erreur] Pas de connexion série active\n', QColor("red"))
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
            if format_type == 'ASCII':
                # Envoyer en mode texte
                data = text.encode('utf-8') + eol
            else:  # HEX
                # Convertir la chaîne HEX en bytes
                # Nettoyer l'entrée en supprimant les espaces et caractères non-hex
                hex_text = ''.join(c for c in text if c.upper() in '0123456789ABCDEF')
                if len(hex_text) % 2 != 0:
                    hex_text += '0'  # Ajouter un 0 si nombre impair de caractères
                data = bytes.fromhex(hex_text) + eol
                
            # Envoyer les données
            self.serial_port.write(data)
            
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
            if self.repeatCheck.isChecked():
                try:
                    interval = int(self.repeatInterval.text())
                    if not self.repeat_timer.isActive():
                        self.repeat_timer.start(interval)
                except ValueError:
                    self.appendFormattedText('[Erreur] Intervalle non valide\n', QColor("red"))
            else:
                if self.repeat_timer.isActive():
                    self.repeat_timer.stop()
                
            # Effacer le champ d'entrée sauf en mode répétition
            if not self.repeatCheck.isChecked():
                self.inputField.clear()
                
        except Exception as e:
            self.appendFormattedText(f'[Erreur d\'envoi] {str(e)}\n', QColor("red"))

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

    def startLogging(self, automatic=False):
        # Si déjà en train d'enregistrer, arrêter d'abord
        if self.log_file:
            self.stopLogging()
            
        try:
            if automatic and self.savePathInput.text():
                # En mode automatique, utiliser le chemin prédéfini
                path = self.savePathInput.text()
                filename = os.path.join(path, f"terminal_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            else:
                # Demander à l'utilisateur où enregistrer le fichier
                filename, _ = QFileDialog.getSaveFileName(
                    self, 'Enregistrer le log', 
                    f"terminal_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    'Fichiers texte (*.txt);;Tous les fichiers (*.*)'
                )
                
            if filename:
                self.log_file = open(filename, 'w', encoding='utf-8')
                self.log_file.write(f"--- Log démarré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                self.log_file.flush()
                
                self.appendFormattedText(f'[Système] Enregistrement démarré: {filename}\n', QColor("green"))
                self.logAction.setText("Arrêter log")
                self.statusBarWidget.showMessage(f"Enregistrement en cours: {os.path.basename(filename)}")
        except Exception as e:
            self.showMessage(f"Erreur lors de l'enregistrement: {str(e)}", error=True)

    def stopLogging(self):
        if self.log_file:
            try:
                self.log_file.write(f"--- Log terminé le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                self.log_file.close()
                self.appendFormattedText('[Système] Enregistrement terminé\n', QColor("orange"))
                self.logAction.setText("Démarrer log")
                self.statusBarWidget.showMessage("Enregistrement terminé", 3000)
            except Exception as e:
                self.showMessage(f"Erreur lors de la fermeture du log: {str(e)}", error=True)
            finally:
                self.log_file = None

    def saveTerminalContent(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Enregistrer le contenu du terminal', 
            f"terminal_contenu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            'Fichiers texte (*.txt);;Tous les fichiers (*.*)'
        )
        
        if filename:
            try:
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

    def applyTheme(self, theme):
        app = QApplication.instance() # Obtenir l'instance de l'application
        
        if theme == 'clair':
            # Appliquer une palette claire standard
            app.setStyle(QStyleFactory.create('Fusion')) # Assurer le style Fusion
            light_palette = QPalette() # Créer une palette par défaut (généralement claire)
            app.setPalette(light_palette)
            
            # Ajuster spécifiquement le terminal si nécessaire
            self.terminal.setFont(QFont("Consolas", 12))
            self.terminal.setStyleSheet("background-color: white; color: black;") 
            self.defaultTextColor = QColor("black")
            self.defaultBgColor = QColor("white")

        elif theme == 'sombre':
            # Réappliquer la palette sombre définie au démarrage
            app.setStyle(QStyleFactory.create('Fusion'))
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.WindowText, Qt.white)
            dark_palette.setColor(QPalette.Base, QColor(42, 42, 42)) 
            dark_palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
            dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
            dark_palette.setColor(QPalette.ToolTipText, Qt.white)
            dark_palette.setColor(QPalette.Text, Qt.white) 
            dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ButtonText, Qt.white)
            dark_palette.setColor(QPalette.BrightText, Qt.red)
            dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(dark_palette)
            
            # Ajuster le terminal
            self.terminal.setFont(QFont("Consolas", 12))
            self.terminal.setStyleSheet(f"background-color: {dark_palette.color(QPalette.Base).name()}; color: white;")
            self.defaultTextColor = QColor("white")
            self.defaultBgColor = dark_palette.color(QPalette.Base)

        elif theme == 'hacker':
            # Appliquer une palette hacker (noir/vert)
            app.setStyle(QStyleFactory.create('Fusion'))
            hacker_palette = QPalette()
            hacker_palette.setColor(QPalette.Window, QColor(0, 0, 0))
            hacker_palette.setColor(QPalette.WindowText, QColor(0, 255, 0))
            # ... (définir d'autres couleurs si nécessaire, sinon elles héritent)
            hacker_palette.setColor(QPalette.Base, QColor(0, 0, 0)) 
            hacker_palette.setColor(QPalette.Text, QColor(0, 255, 0)) 
            hacker_palette.setColor(QPalette.Button, QColor(10, 30, 10))
            hacker_palette.setColor(QPalette.ButtonText, QColor(0, 255, 0))
            hacker_palette.setColor(QPalette.Highlight, QColor(0, 255, 0))
            hacker_palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
            app.setPalette(hacker_palette)
            
            # Ajuster le terminal
            self.terminal.setFont(QFont("Courier New", 12, QFont.Bold))
            self.terminal.setStyleSheet("background-color: black; color: rgb(0, 255, 0);") 
            self.defaultTextColor = QColor(0, 255, 0)
            self.defaultBgColor = QColor("black")

        # Sauvegarder le thème
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

    def showAbout(self):
        QMessageBox.about(
            self, 
            "À propos du Terminal Série",
            "Terminal de Communication Série Avancé v1.0\n\n"
            "Un outil complet pour la communication série avec de nombreuses fonctionnalités.\n\n"
            "© 2025 Terminal Série"
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
        self.toggleSendPanelAction.setChecked(send_panel_visible) # Mettre à jour l'état de l'action du menu
        
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
        # Sauvegarder les commandes dans les paramètres
        self.settings.setValue("commands/list", self.commandsTextEdit.toPlainText())
        self.updateCommandButtons()
        self.statusBarWidget.showMessage("Commandes sauvegardées", 3000)

    def loadCommands(self):
        # Charger les commandes depuis les paramètres
        commands_text = self.settings.value("commands/list", "")
        self.commandsTextEdit.setPlainText(commands_text)
        self.updateCommandButtons()
        self.statusBarWidget.showMessage("Commandes chargées", 3000)

    def updateCommandButtons(self):
        # Effacer les boutons existants
        while self.shortcutButtonsLayout.count():
            item = self.shortcutButtonsLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Analyser les commandes définies
        text = self.commandsTextEdit.toPlainText()
        for line in text.split('\n'):
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
                except ValueError:
                    continue  # Ignorer les lignes mal formées
        
        # Ajouter un spacer à la fin pour l'alignement
        self.shortcutButtonsLayout.addStretch()

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


if __name__ == "__main__":
    # Configuration de l'application avant de créer la fenêtre
    app = QApplication(sys.argv)

    # Définir la police par défaut pour toute l'application
    default_font = QFont("Arial", 12)
    app.setFont(default_font)

    # Appliquer un style et une palette sombre
    app.setStyle(QStyleFactory.create('Fusion'))
    
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
    app.setPalette(dark_palette)

    terminal = Terminal()
    sys.exit(app.exec_())
