
# secure_shell.py
from flask import Flask, request, render_template_string, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
import subprocess, shlex, json, os, secrets

APP_PORT = 5000
CREDS_FILE = "creds.json"

app = Flask(__name__)
# secret_key -> usado para assinar cookies (session). Gerado aleatoriamente a cada arranque.
# Se quiseres persistir sessões entre reinícios, define manualmente uma chave fixa.
app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # ou 'Strict' se preferires

# --- HTML templates simples ---
HTML_SETUP = """
<!doctype html>
<body style="background-color: yellow; color: black; font-family: monospace;>
<title>Configurar Utilizador</title>
<h2>Primeiro arranque — cria uma conta</h2>
<form method="post">
  Username: <input name="username"><br>
  Password: <input name="password" type="password"><br>
  <button type="submit">Criar conta</button>
</body>
</form>
"""

HTML_LOGIN = """
<!doctype html>
<title>Login</title>

<h2>Login</h2>
<form method="post">
  Username: <input name="username"><br>
  Password: <input name="password" type="password"><br>
  <button type="submit">Entrar</button>
</form>

"""

HTML_INDEX = """
<!doctype html>
<html>
<head><title>Shell Local Seguro</title></head>
<body style="background-color: yellow; color: black; font-family: monospace;">
  <h2>Bem-vindo {{ user }}</h2>
  <form method="post" action="{{ url_for('run_command') }}">
    <input type="text" name="cmd" style="width:400px;">
    <button type="submit">OK</button>
  </form>
  <p><a href="{{ url_for('logout') }}">Logout</a></p>
</body>
</html>
"""

HTML_RESULT = """
<!doctype html>
<html>
<head><title>Resultado</title></head>
<body style="background-color: yellow; color: black; font-family: monospace;">
  <h2>Resultado do Comando:</h2>
  <pre>{{ output }}</pre>
  <a href="{{ url_for('index') }}">Voltar</a>
</body>
</html>
"""

# --- Helpers para credenciais ---
def creds_exist():
    return os.path.exists(CREDS_FILE)

def save_creds(username, password_plain):
    # Gera hash e grava em JSON local
    hashed = generate_password_hash(password_plain)
    data = {"username": username, "password_hash": hashed}
    with open(CREDS_FILE, "w") as f:
        json.dump(data, f)

def load_creds():
    if not creds_exist():
        return None
    with open(CREDS_FILE, "r") as f:
        return json.load(f)

def verify_creds(username, password_plain):
    data = load_creds()
    if not data:
        return False
    return data["username"] == username and check_password_hash(data["password_hash"], password_plain)

# --- Before request: proteger rotas ---
from functools import wraps
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        # rotas públicas: /setup (se não existir creds) e /login
        if request.endpoint in ('setup', 'login', 'static'):
            return f(*args, **kwargs)
        # Verifica sessão
        if session.get("auth") and session.get("username"):
            # opcional: verificar username ainda coincide com ficheiro
            data = load_creds()
            if data and data.get("username") == session.get("username"):
                return f(*args, **kwargs)
        return redirect(url_for("login"))
    return wrapped

@app.route("/setup", methods=["GET", "POST"])
def setup():
    # Se já existir credenciais, não permitir re-criação por esta rota
    if creds_exist():
        return redirect(url_for("login"))
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()
        if not user or not pwd:
            return "Username e password obrigatórios", 400
        save_creds(user, pwd)
        # iniciar sessão
        session['username'] = user
        session['auth'] = True
        return redirect(url_for("index"))
    return render_template_string(HTML_SETUP)

@app.route("/login", methods=["GET", "POST"])
def login():
    if not creds_exist():
        return redirect(url_for("setup"))
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()
        if verify_creds(user, pwd):
            session['username'] = user
            session['auth'] = True
            return redirect(url_for("index"))
        else:
            return "Login falhou", 403
    return render_template_string(HTML_LOGIN)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET"])
@login_required
def index():
    # Só permite mostrar index se a sessão estiver autenticada
    # Verifica origem (local)
    if request.remote_addr != "127.0.0.1" and request.remote_addr != "localhost":
        return "Acesso negado: apenas localhost pode aceder.", 403
    return render_template_string(HTML_INDEX, user=session.get("username"))

@app.route("/run", methods=["POST"])
@login_required
def run_command():
    # Segurança: só aceitar pedidos de localhost
    if request.remote_addr != "127.0.0.1" and request.remote_addr != "localhost":
        return "Acesso negado: apenas localhost pode executar comandos.", 403

    # comando
    cmd = request.form.get("cmd", "")
    if not cmd.strip():
        return "Nenhum comando fornecido.", 400

    # Opcional: re-verificar sessão com ficheiro de creds (já feito por login_required)
    # Aqui executamos o comando com shell=False para maior segurança.
    # Se precisares de usar shell=True para comandos compostos, lê as notas abaixo.
    try:
        args = shlex.split(cmd)
        proc = subprocess.run(args, capture_output=True, text=True, timeout=10)
        output = proc.stdout + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    except FileNotFoundError:
        output = "Comando não encontrado."
    except subprocess.TimeoutExpired:
        output = "Comando excedeu o tempo limite."
    except Exception as e:
        output = f"Erro ao executar: {e}"

    return render_template_string(HTML_RESULT, output=output)

# Aplicar wrapper de login em todas as rotas (simplificação)
for rule in list(app.url_map.iter_rules()):
    # Não interferir com static, setup e login rotas
    pass

# --- main ---
if __name__ == "__main__":
    # Se não existir ficha de credenciais, forçamos o utilizador a usar /setup
    if not creds_exist():
        print("Nenhuma credencial encontrada. Acede a /setup para criar a conta.")
    else:
        print("Credenciais carregadas. Acede a /login para iniciar sessão.")
    # Só escuta localhost (como querias)
    app.run(host="127.0.0.1", port=APP_PORT, debug=True)
