import os
import urllib.request
import winreg
import shutil

def download_and_install_raleway_variable():
    # Google Fonts official github repository URLs for Raleway Variable Fonts
    urls = {
        "Raleway[wght].ttf": "https://github.com/google/fonts/raw/main/ofl/raleway/Raleway%5Bwght%5D.ttf",
        "Raleway-Italic[wght].ttf": "https://github.com/google/fonts/raw/main/ofl/raleway/Raleway-Italic%5Bwght%5D.ttf"
    }
    
    user_fonts_dir = os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\Fonts")
    os.makedirs(user_fonts_dir, exist_ok=True)
    
    reg_key_path = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
    
    installed_count = 0
    
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key_path, 0, winreg.KEY_SET_VALUE) as key:
            for filename, url in urls.items():
                dest_path = os.path.join(user_fonts_dir, filename)
                print(f"Downloading {filename} from Github...")
                
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )
                
                try:
                    with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
                        shutil.copyfileobj(response, out_file)
                    print(f"Downloaded to {dest_path}")
                except Exception as e:
                    print(f"Failed to download {filename}: {e}")
                    continue
                
                # Determine font name for registry entry
                font_name_clean = os.path.splitext(filename)[0]
                formatted_name = font_name_clean.replace("-", " ") + " (TrueType)"
                
                # Register in HKCU Fonts
                winreg.SetValueEx(key, formatted_name, 0, winreg.REG_SZ, dest_path)
                print(f"Installed & Registered: {formatted_name}")
                installed_count += 1
                
    except Exception as e:
        print(f"Error registering fonts: {e}")
        return
        
    if installed_count > 0:
        print(f"\nSuccessfully installed {installed_count} Raleway Variable fonts!")
        print("Note: You may need to restart Illustrator to see the new font.")
    else:
        print("\nNo fonts were installed.")

if __name__ == "__main__":
    download_and_install_raleway_variable()
