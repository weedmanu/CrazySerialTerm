import os
import sys
import subprocess
from pathlib import Path
import shutil

# Chemins
root = Path(__file__).parent.parent
build_dir = root / "build_exe"
icon_path = root / "LogoFreeTermIco.ico"
requirements_build = build_dir / "requirements_build.txt"
requirements_proj = root / "requirements.txt"
exe_name = "CrazySerialTerm.exe"
exe_path = build_dir / "dist" / exe_name
spec_path = build_dir / f"{exe_name.replace('.exe', '.spec')}"

# Purge des dossiers __pycache__ et build
def purge_folder(folder):
    if folder.exists():
        for item in folder.rglob("*"):
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception:
                pass
        try:
            folder.rmdir()
        except Exception:
            pass

print("Purge des dossiers __pycache__ et build...")
for d in [root / "__pycache__", root / "build", build_dir / "__pycache__", build_dir / "build"]:
    purge_folder(d)

# Mise à jour de pip
print("Mise à jour de pip...")
subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)

# Installation des dépendances build
print("Installation des dépendances de build...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_build)], check=True)

# Installation des dépendances du projet
print("Installation des dépendances du projet...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements_proj)], check=True)

# Création de l'exécutable avec PyInstaller
print("Création de l'exécutable...")
pyinstaller_cmd = [
    sys.executable,  # Utiliser l'interpréteur Python actuel
    "-m",
    "PyInstaller",
    "--onefile",
    "--windowed",
    # inclure l'icône et toutes ressources nécessaires
    f"--icon={icon_path}",
    f"--add-data={icon_path};.",
    "--distpath", str(build_dir / "dist"),
    "--workpath", str(build_dir / "build"),
    "--specpath", str(build_dir),
    str(root / "CrazySerialTerm.py")
]
subprocess.run(pyinstaller_cmd, check=True)

if not exe_path.exists():
    print("Erreur : l'exécutable n'a pas été généré.")
    sys.exit(1)
print(f"Exécutable créé : {exe_path}")

# Suppression des fichiers de build inutiles
print("Nettoyage des fichiers de build...")
for d in [root / "build", build_dir / "build", root / "__pycache__", build_dir / "__pycache__"]:
    purge_folder(d)
if spec_path.exists():
    spec_path.unlink()

# Création des raccourcis Menu Démarrer et Bureau
try:
    from win32com.client import Dispatch
except ImportError:
    print("Installation de pywin32 pour la création des raccourcis...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pywin32"], check=True)
    
    # Exécuter le script de post-installation de pywin32
    print("Configuration de pywin32...")
    import site
    pywin32_postinstall = os.path.join(site.getsitepackages()[0], "Scripts", "pywin32_postinstall.py")
    subprocess.run([sys.executable, pywin32_postinstall, "-install"], check=True)
    
    # Réessayer l'import
    from win32com.client import Dispatch

shell = Dispatch('WScript.Shell')

# Menu Démarrer
try:
    start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    shortcut_path = start_menu / "CrazySerialTerm.lnk"
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.Targetpath = str(exe_path)
    shortcut.IconLocation = str(icon_path)
    shortcut.save()
    print(f"Raccourci ajouté au menu Démarrer : {shortcut_path}")
except Exception as e:
    print(f"Erreur lors de la création du raccourci Menu Démarrer : {e}")

# Bureau
try:
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    desktop_shortcut = desktop / "CrazySerialTerm.lnk"
    shortcut = shell.CreateShortCut(str(desktop_shortcut))
    shortcut.Targetpath = str(exe_path)
    shortcut.IconLocation = str(icon_path)
    shortcut.save()
    print(f"Raccourci ajouté sur le Bureau : {desktop_shortcut}")
except Exception as e:
    print(f"Erreur lors de la création du raccourci Bureau : {e}")

print("Installation et build terminés.")