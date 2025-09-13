
from flask import Flask, request, render_template_string
import subprocess
import socket
import random
num=""
for n in range(10):
   numbers=random.randrange(99999999)
   num=num+hex(numbers)
num1="/"+num
print(num)
app = Flask(__name__)

# Página inicial com formulário
HTML_FORM = """
<!doctype html>
<html>
<head>
    <title>Shell Local</title>
</head>
<body style="background-color: yellow; color: black; font-family: monospace;">
    <h2>Executar Comando</h2>
    <form method="POST" action="$num">
        <input type="text" name="cmd" style="width:400px;">
        <button type="submit">OK</button>
    </form>
</body>
</html>
"""
HTML_FORM = HTML_FORM.replace("$num",num1)
# Página para mostrar resultados
HTML_RESULT = """
<!doctype html>
<html>
<head>
    <title>Resultado</title>
</head>
<body style="background-color: yellow; color: black; font-family: monospace;">
    <h2>Resultado do Comando:</h2>
    <pre>{{ output }}</pre>
    <a href="/">Voltar</a>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return HTML_FORM

@app.route(str(num1), methods=["POST"])
def run_command():
    # Verifica se vem do localhost
    if request.remote_addr != "127.0.0.1":
        return "Acesso negado: apenas localhost pode executar comandos.", 403

    cmd = request.form.get("cmd", "")
    if not cmd.strip():
        return "Nenhum comando fornecido.", 400

    try:
        # Executa o comando no shell
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        output = f"Erro ao executar o comando:\n{e.output}"

    return render_template_string(HTML_RESULT, output=output)

if __name__ == "__main__":
    # Executa apenas local
    app.run(host="127.0.0.1", port=5000, debug=True)
