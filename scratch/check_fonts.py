import os
import winreg

def check_fonts_registry_and_files():
    targets = ["raleway", "abhaya", "globe gothic", "ltc globe"]
    found_fonts = []

    # 1. Check registry
    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts")
    ]
    
    print("--- Searching in Windows Registry ---")
    for hkey, subkey in registry_paths:
        try:
            with winreg.OpenKey(hkey, subkey) as key:
                num_values = winreg.QueryInfoKey(key)[1]
                for i in range(num_values):
                    name, val, _ = winreg.EnumValue(key, i)
                    name_lower = name.lower()
                    val_lower = str(val).lower()
                    for t in targets:
                        if t in name_lower or t in val_lower:
                            print(f"Registry Match: {name} -> {val}")
                            found_fonts.append(name)
        except Exception as e:
            print(f"Error opening registry: {e}")

    # 2. Check font folders
    folders = [
        r"C:\Windows\Fonts",
        os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\Fonts")
    ]
    print("\n--- Searching in Font Folders ---")
    for folder in folders:
        if os.path.exists(folder):
            print(f"Scanning: {folder}")
            for root, _, files in os.walk(folder):
                for file in files:
                    file_lower = file.lower()
                    for t in targets:
                        if t in file_lower:
                            print(f"File Match: {os.path.join(root, file)}")
                            found_fonts.append(file)
                            
    if not found_fonts:
        print("\nNo matching fonts found.")

if __name__ == "__main__":
    check_fonts_registry_and_files()
