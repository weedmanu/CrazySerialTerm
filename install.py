import os
import sys
import subprocess
from pathlib import Path

# Chemins
root = Path(__file__).parent
venv_dir = root / "venv"
requirements = root / "requirements.txt"

# Création de l'environnement virtuel si nécessaire
if not venv_dir.exists():
    print("Création de l'environnement virtuel...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
else:
    print("L'environnement virtuel existe déjà.")

# Détermination des chemins python/pip du venv
if os.name == "nt":
    python_bin = venv_dir / "Scripts" / "python.exe"
    pip_bin = venv_dir / "Scripts" / "pip.exe"
else:
    python_bin = venv_dir / "bin" / "python"
    pip_bin = venv_dir / "bin" / "pip"

# Mise à jour de pip
print("Mise à jour de pip dans le venv...")
subprocess.run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], check=True)

# Installation des dépendances du projet
print("Installation des dépendances du projet...")
subprocess.run([str(pip_bin), "install", "-r", str(requirements)], check=True)

print("Installation terminée. Pour lancer le programme :")
print(f"{python_bin} CrazySerialTerm.py")


