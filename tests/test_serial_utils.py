"""
Tests unitaires pour le module serial_utils
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Ajouter le répertoire parent au chemin de recherche des modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from serial_utils import (
    list_available_ports, 
    get_port_info, 
    create_serial_connection,
    format_data_as_hex,
    parse_hex_string
)

class TestSerialUtils(unittest.TestCase):
    """Tests pour les fonctions du module serial_utils"""
    
    @patch('serial.tools.list_ports.comports')
    def test_list_available_ports(self, mock_comports):
        """Test de la fonction list_available_ports"""
        # Configurer le mock
        mock_port1 = MagicMock()
        mock_port1.device = 'COM1'
        mock_port2 = MagicMock()
        mock_port2.device = 'COM2'
        mock_comports.return_value = [mock_port1, mock_port2]
        
        # Appeler la fonction
        ports = list_available_ports()
        
        # Vérifier le résultat
        self.assertEqual(ports, ['COM1', 'COM2'])
        mock_comports.assert_called_once()
    
    @patch('serial.tools.list_ports.comports')
    def test_get_port_info(self, mock_comports):
        """Test de la fonction get_port_info"""
        # Configurer le mock
        mock_port = MagicMock()
        mock_port.device = 'COM1'
        mock_port.description = 'Test Port'
        mock_port.manufacturer = 'Test Manufacturer'
        mock_port.hwid = 'USB VID:PID=1234:5678'
        mock_port.vid = 0x1234
        mock_port.pid = 0x5678
        mock_port.serial_number = '123456'
        mock_comports.return_value = [mock_port]
        
        # Appeler la fonction
        info = get_port_info('COM1')
        
        # Vérifier le résultat
        self.assertEqual(info['name'], 'COM1')
        self.assertEqual(info['description'], 'Test Port')
        self.assertEqual(info['manufacturer'], 'Test Manufacturer')
        self.assertEqual(info['hwid'], 'USB VID:PID=1234:5678')
        self.assertEqual(info['vid'], 0x1234)
        self.assertEqual(info['pid'], 0x5678)
        self.assertEqual(info['serial_number'], '123456')
    
    @patch('serial.Serial')
    def test_create_serial_connection(self, mock_serial):
        """Test de la fonction create_serial_connection"""
        # Configurer le mock
        mock_serial.return_value = MagicMock()
        
        # Appeler la fonction
        result = create_serial_connection('COM1', 115200)
        
        # Vérifier le résultat
        self.assertIsNotNone(result)
        mock_serial.assert_called_once_with(
            port='COM1',
            baudrate=115200,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=0.1
        )
    
    def test_format_data_as_hex(self):
        """Test de la fonction format_data_as_hex"""
        # Données de test
        data = bytes([0x01, 0x02, 0xAB, 0xCD])
        
        # Appeler la fonction
        result = format_data_as_hex(data)
        
        # Vérifier le résultat
        self.assertEqual(result, '01 02 AB CD')
    
    def test_parse_hex_string(self):
        """Test de la fonction parse_hex_string"""
        # Données de test
        hex_string = '01 02 AB CD'
        
        # Appeler la fonction
        result = parse_hex_string(hex_string)
        
        # Vérifier le résultat
        self.assertEqual(result, bytes([0x01, 0x02, 0xAB, 0xCD]))
        
        # Test avec des espaces et caractères non-hex
        hex_string = '01-02:AB CD XYZ'
        result = parse_hex_string(hex_string)
        self.assertEqual(result, bytes([0x01, 0x02, 0xAB, 0xCD]))
        
        # Test avec un nombre impair de caractères
        hex_string = '01 02 A'
        result = parse_hex_string(hex_string)
        self.assertEqual(result, bytes([0x01, 0x02, 0xA0]))

if __name__ == '__main__':
    unittest.main()