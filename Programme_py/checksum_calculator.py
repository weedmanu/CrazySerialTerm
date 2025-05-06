import sys
import hashlib
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QTextEdit, QLineEdit, QPushButton, QGroupBox, QGridLayout)
from PyQt5.QtCore import Qt

class ChecksumCalculator(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculatrice de Checksums")
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        
        # Zone d'entrée
        inputGroup = QGroupBox("Données d'entrée")
        inputLayout = QVBoxLayout()
        
        formatLayout = QHBoxLayout()
        formatLayout.addWidget(QLabel("Format:"))
        self.formatSelect = QComboBox()
        self.formatSelect.addItems(["ASCII", "HEX"])
        self.formatSelect.currentIndexChanged.connect(self.calculateChecksums)
        formatLayout.addWidget(self.formatSelect)
        inputLayout.addLayout(formatLayout)
        
        self.dataInput = QTextEdit()
        self.dataInput.setPlaceholderText("Entrez les données à traiter...")
        self.dataInput.textChanged.connect(self.calculateChecksums)
        inputLayout.addWidget(self.dataInput)
        
        inputGroup.setLayout(inputLayout)
        layout.addWidget(inputGroup)
        
        # Zone de résultats
        resultsGroup = QGroupBox("Résultats")
        resultsLayout = QGridLayout()
        
        # Définir les types de checksums
        checksums = [
            ("Somme", "Sum"),
            ("XOR", "XOR"),
            ("CRC8", "CRC-8"),
            ("CRC16", "CRC-16"),
            ("CRC32", "CRC-32"),
            ("MD5", "MD5"),
            ("SHA-1", "SHA-1"),
            ("SHA-256", "SHA-256")
        ]
        
        self.results = {}
        row = 0
        for name, key in checksums:
            resultsLayout.addWidget(QLabel(f"{name}:"), row, 0)
            self.results[key] = QLineEdit()
            self.results[key].setReadOnly(True)
            resultsLayout.addWidget(self.results[key], row, 1)
            row += 1
            
        resultsGroup.setLayout(resultsLayout)
        layout.addWidget(resultsGroup)
        
        # Boutons
        buttonLayout = QHBoxLayout()
        clearBtn = QPushButton("Effacer")
        clearBtn.clicked.connect(self.clearData)
        buttonLayout.addWidget(clearBtn)
        
        closeBtn = QPushButton("Fermer")
        closeBtn.clicked.connect(self.accept)
        buttonLayout.addWidget(closeBtn)
        
        layout.addLayout(buttonLayout)
        
    def calculateChecksums(self):
        try:
            text = self.dataInput.toPlainText()
            if not text:
                self.clearResults()
                return
                
            # Convertir les données selon le format
            if self.formatSelect.currentText() == "ASCII":
                data = text.encode('utf-8')
            else:  # HEX
                hex_text = ''.join(c for c in text if c.upper() in '0123456789ABCDEF ')
                hex_text = hex_text.replace(' ', '')
                if len(hex_text) % 2 != 0: hex_text += '0'
                try: data = bytes.fromhex(hex_text)
                except ValueError: self.clearResults(); return
            
            # Calculer les checksums
            self.results["Sum"].setText(f"{sum(data) & 0xFF:02X}")
            
            xor_result = 0
            for b in data: xor_result ^= b
            self.results["XOR"].setText(f"{xor_result:02X}")
            
            crc8 = 0
            for b in data:
                crc8 ^= b
                for _ in range(8): crc8 = (crc8 << 1) ^ 0x07 if crc8 & 0x80 else crc8 << 1
                crc8 &= 0xFF
            self.results["CRC-8"].setText(f"{crc8:02X}")

            crc16 = 0xFFFF
            for b in data:
                crc16 ^= b << 8
                for _ in range(8): crc16 = (crc16 << 1) ^ 0x1021 if crc16 & 0x8000 else crc16 << 1
                crc16 &= 0xFFFF
            self.results["CRC-16"].setText(f"{crc16:04X}")

            crc32 = 0xFFFFFFFF
            for b in data:
                crc32 ^= b
                for _ in range(8): crc32 = (crc32 >> 1) ^ 0xEDB88320 if crc32 & 1 else crc32 >> 1
            crc32 ^= 0xFFFFFFFF
            self.results["CRC-32"].setText(f"{crc32:08X}")

            self.results["MD5"].setText(hashlib.md5(data).hexdigest().upper())
            self.results["SHA-1"].setText(hashlib.sha1(data).hexdigest().upper())
            self.results["SHA-256"].setText(hashlib.sha256(data).hexdigest().upper())

        except Exception as e: self.clearResults()

    def clearData(self): self.dataInput.clear(); self.clearResults()
    def clearResults(self): 
        for key in self.results: self.results[key].clear()