import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                             QPushButton, QGroupBox)
from PyQt5.QtCore import Qt

class DataConverter(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Convertisseur de Données (ASCII/HEX)")
        self.resize(400, 200)

        layout = QVBoxLayout(self)

        # Zone d'entrée
        inputGroup = QGroupBox("Données d'entrée")
        inputLayout = QVBoxLayout()
        self.inputText = QTextEdit()
        self.inputText.setPlaceholderText("Entrez les données à convertir...")
        inputLayout.addWidget(self.inputText)
        inputGroup.setLayout(inputLayout)
        layout.addWidget(inputGroup)

        # Zone de sortie
        outputGroup = QGroupBox("Données converties")
        outputLayout = QVBoxLayout()
        self.outputText = QTextEdit()
        self.outputText.setReadOnly(True)
        outputLayout.addWidget(self.outputText)
        outputGroup.setLayout(outputLayout)
        layout.addWidget(outputGroup)

        # Boutons
        buttonLayout = QHBoxLayout()
        self.toHexBtn = QPushButton("Convertir en HEX")
        self.toHexBtn.clicked.connect(self.convertToHex)
        buttonLayout.addWidget(self.toHexBtn)

        self.toAsciiBtn = QPushButton("Convertir en ASCII")
        self.toAsciiBtn.clicked.connect(self.convertToAscii)
        buttonLayout.addWidget(self.toAsciiBtn)

        closeBtn = QPushButton("Fermer")
        closeBtn.clicked.connect(self.accept)
        buttonLayout.addWidget(closeBtn)

        layout.addLayout(buttonLayout)

    def convertToHex(self): self.outputText.setText(' '.join(f'{ord(c):02X}' for c in self.inputText.toPlainText()))
    def convertToAscii(self):
        try: self.outputText.setText(bytes.fromhex(self.inputText.toPlainText().replace(' ', '')).decode('utf-8', errors='replace'))
        except ValueError: self.outputText.setText("Erreur : données HEX invalides.")