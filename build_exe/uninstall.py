import os
from pathlib import Path
import shutil

# Chemins
root = Path(__file__).parent.parent
build_dir = root / "build_exe"
exe_name = "CrazySerialTerm.exe"
exe_path = build_dir / "dist" / exe_name
spec_path = build_dir / "CrazySerialTerm.spec"

# Suppression du .exe généré
if exe_path.exists():
    print(f"Suppression de l'exécutable : {exe_path}")
    exe_path.unlink()
else:
    print(f"Exécutable non trouvé : {exe_path}")

# Suppression du fichier spec
if spec_path.exists():
    print(f"Suppression du fichier spec : {spec_path}")
    spec_path.unlink()

# Suppression des raccourcis
try:
    from win32com.client import Dispatch
except ImportError:
    print("Installation de pywin32 pour la suppression des raccourcis...")
    import subprocess
    subprocess.run(["pip", "install", "pywin32"], check=True)
    from win32com.client import Dispatch

shell = Dispatch('WScript.Shell')

# Menu Démarrer
start_menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
shortcut_path = start_menu / "CrazySerialTerm.lnk"
if shortcut_path.exists():
    print(f"Suppression du raccourci Menu Démarrer : {shortcut_path}")
    shortcut_path.unlink()
else:
    print(f"Raccourci Menu Démarrer non trouvé : {shortcut_path}")

# Bureau
desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
desktop_shortcut = desktop / "CrazySerialTerm.lnk"
if desktop_shortcut.exists():
    print(f"Suppression du raccourci Bureau : {desktop_shortcut}")
    desktop_shortcut.unlink()
else:
    print(f"Raccourci Bureau non trouvé : {desktop_shortcut}")

print("Désinstallation terminée.")
