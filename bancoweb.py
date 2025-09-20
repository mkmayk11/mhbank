from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import json, os, csv, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

DATA_FILE = "dados_wallet.json"

# -------------------- Persistência --------------------
def carregar_dados():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                dados = json.load(f)
                if not isinstance(dados, dict):
                    raise ValueError("JSON inválido")
                if "clientes" not in dados: dados["clientes"] = {}
                if "historico" not in dados or not isinstance(dados["historico"], list):
                    dados["historico"] = []
                return dados
            except Exception:
                return {"clientes": {}, "historico": []}
    return {"clientes": {}, "historico": []}

def salvar_dados(dados):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

# -------------------- Funções de negócio --------------------
def registrar_historico(dados, usuario, acao, valor=0, destino=None):
    entrada = {
        "usuario": usuario,
        "acao": acao,
        "valor": valor,
        "destino": destino,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }
    dados["historico"].append(entrada)
    salvar_dados(dados)

# -------------------- Rotas --------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]
        dados = carregar_dados()
        if usuario in dados["clientes"] and dados["clientes"][usuario]["senha"] == senha:
            session["usuario"] = usuario
            return redirect(url_for("dashboard"))
        flash("Login inválido")
    return render_template("login.html")

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]
        dados = carregar_dados()
        if usuario in dados["clientes"]:
            flash("Usuário já existe!")
        else:
            dados["clientes"][usuario] = {"senha": senha, "saldo": 0}
            salvar_dados(dados)
            flash("Cadastro realizado!")
            return redirect(url_for("login"))
    return render_template("cadastro.html")

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    saldo = dados["clientes"][usuario]["saldo"]
    return render_template("dashboard.html", usuario=usuario, saldo=saldo, dados=dados)

@app.route("/deposito", methods=["GET", "POST"])
def deposito():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    if request.method == "POST":
        valor = float(request.form["valor"])
        dados["clientes"][usuario]["saldo"] += valor
        registrar_historico(dados, usuario, "Depósito", valor)
        flash("Deposito realizado!")
        return redirect(url_for("dashboard"))
    return render_template("deposito.html")

@app.route("/saque", methods=["GET", "POST"])
def saque():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    if request.method == "POST":
        valor = float(request.form["valor"])
        if valor <= dados["clientes"][usuario]["saldo"]:
            dados["clientes"][usuario]["saldo"] -= valor
            registrar_historico(dados, usuario, "Saque", valor)
            flash("Saque realizado!")
        else:
            flash("Saldo insuficiente!")
        return redirect(url_for("dashboard"))
    return render_template("saque.html")

@app.route("/transferencia", methods=["GET", "POST"])
def transferencia():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    if request.method == "POST":
        destino = request.form["destino"]
        valor = float(request.form["valor"])
        if destino in dados["clientes"] and valor <= dados["clientes"][usuario]["saldo"]:
            dados["clientes"][usuario]["saldo"] -= valor
            dados["clientes"][destino]["saldo"] += valor
            registrar_historico(dados, usuario, "Transferência", valor, destino)
            flash("Transferência realizada!", "success")
        else:
            flash("Erro na transferência!", "danger")
        return redirect(url_for("dashboard"))
    return render_template("transferencia.html", dados=dados)


@app.route("/alterar_senha", methods=["GET", "POST"])
def alterar_senha():
    if "usuario" not in session:
        return redirect(url_for("login"))

    usuario = session["usuario"]

    if request.method == "POST":
        nova_senha = request.form["senha"]
        dados = carregar_dados()
        dados["clientes"][usuario]["senha"] = nova_senha
        salvar_dados(dados)
        flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("dashboard"))

    return render_template("alterar_senha.html", usuario=usuario)

@app.route("/historico")
def historico():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    historico_user = [h for h in dados.get("historico", []) if isinstance(h, dict) and h.get("usuario") == usuario]
    return render_template("historico.html", historico=historico_user)

@app.route("/exportar_csv")
def exportar_csv():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    historico_user = [h for h in dados.get("historico", []) if isinstance(h, dict) and h.get("usuario") == usuario]
    filename = f"historico_{usuario}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["usuario","acao","valor","destino","data"])
        writer.writeheader()
        writer.writerows(historico_user)
    return send_file(filename, as_attachment=True)

@app.route("/roleta", methods=["GET", "POST"])
def roleta():
    if "usuario" not in session:
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    resultado = None
    if request.method == "POST":
        aposta = float(request.form["aposta"])
        if aposta <= dados["clientes"][usuario]["saldo"]:
            dados["clientes"][usuario]["saldo"] -= aposta
            if random.choice([True, False]):
                ganho = aposta * 2
                dados["clientes"][usuario]["saldo"] += ganho
                resultado = f"Ganhou R$ {ganho:.2f}!"
                registrar_historico(dados, usuario, "Roleta (Vitória)", ganho)
            else:
                resultado = "Perdeu!"
                registrar_historico(dados, usuario, "Roleta (Derrota)", aposta)
            salvar_dados(dados)
        else:
            resultado = "Saldo insuficiente!"
    return render_template("roleta.html", resultado=resultado)

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
