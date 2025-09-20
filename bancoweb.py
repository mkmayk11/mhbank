from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import sqlite3, csv, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "segredo_super_seguro"

DB_FILE = "dados_wallet.db"

# -------------------- Banco de dados --------------------
def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Tabela de clientes
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            usuario TEXT PRIMARY KEY,
            senha TEXT NOT NULL,
            saldo REAL DEFAULT 0
        )
    """)
    
    # Insere admin se não existir
    c.execute("INSERT OR IGNORE INTO clientes (usuario, senha, saldo) VALUES (?, ?, ?)",
              ("admin", "411269", 0))
    
    # Tabela de histórico
    c.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            acao TEXT,
            valor REAL,
            destino TEXT,
            data TEXT
        )
    """)
    
    # Tabela de depósitos pendentes
    c.execute("""
        CREATE TABLE IF NOT EXISTS depositos_pendentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            valor REAL,
            data TEXT,
            aprovado INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

# Inicializa o banco
init_db()

# -------------------- Funções de persistência --------------------
def carregar_dados():
    conn = get_connection()
    c = conn.cursor()
    
    # Clientes
    c.execute("SELECT * FROM clientes")
    clientes = {row["usuario"]: {"senha": row["senha"], "saldo": row["saldo"]} for row in c.fetchall()}
    
    # Histórico
    c.execute("SELECT * FROM historico")
    historico = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return {"clientes": clientes, "historico": historico}

def salvar_cliente(usuario, senha=None, saldo=None):
    conn = get_connection()
    c = conn.cursor()
    
    if senha is not None and saldo is not None:
        c.execute("INSERT OR REPLACE INTO clientes (usuario, senha, saldo) VALUES (?, ?, ?)", 
                  (usuario, senha, saldo))
    elif saldo is not None:
        c.execute("UPDATE clientes SET saldo = ? WHERE usuario = ?", (saldo, usuario))
    elif senha is not None:
        c.execute("UPDATE clientes SET senha = ? WHERE usuario = ?", (senha, usuario))
    
    conn.commit()
    conn.close()

def registrar_historico(usuario, acao, valor=0, destino=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO historico (usuario, acao, valor, destino, data) VALUES (?, ?, ?, ?, ?)",
              (usuario, acao, valor, destino, datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
    conn.commit()
    conn.close()

# -------------------- Rotas --------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]
        dados = carregar_dados()
        if usuario in dados["clientes"] and dados["clientes"][usuario]["senha"] == senha:
            session["usuario"] = usuario
            # Se for admin, redireciona para admin de depósitos
            if usuario == "admin":
                return redirect(url_for("admin_depositos"))
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
            salvar_cliente(usuario, senha=senha, saldo=0)
            flash("Cadastro realizado!")
            return redirect(url_for("login"))
    return render_template("cadastro.html")

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    saldo = dados["clientes"][usuario]["saldo"]
    return render_template("dashboard.html", usuario=usuario, saldo=saldo, dados=dados)

# -------------------- Depósito pendente --------------------
@app.route("/deposito", methods=["GET", "POST"])
def deposito():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    if request.method == "POST":
        valor = float(request.form["valor"])
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO depositos_pendentes (usuario, valor, data, aprovado) VALUES (?, ?, ?, 0)",
                  (usuario, valor, datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        conn.commit()
        conn.close()
        flash("Depósito enviado para aprovação do admin!")
        return redirect(url_for("dashboard"))
    return render_template("deposito.html")

@app.route("/saque", methods=["GET", "POST"])
def saque():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    if request.method == "POST":
        valor = float(request.form["valor"])
        if valor <= dados["clientes"][usuario]["saldo"]:
            saldo_atual = dados["clientes"][usuario]["saldo"] - valor
            salvar_cliente(usuario, saldo=saldo_atual)
            registrar_historico(usuario, "Saque", valor)
            flash("Saque realizado!")
        else:
            flash("Saldo insuficiente!")
        return redirect(url_for("dashboard"))
    return render_template("saque.html")

@app.route("/transferencia", methods=["GET", "POST"])
def transferencia():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    if request.method == "POST":
        destino = request.form["destino"]
        valor = float(request.form["valor"])
        if destino in dados["clientes"] and valor <= dados["clientes"][usuario]["saldo"]:
            saldo_origem = dados["clientes"][usuario]["saldo"] - valor
            saldo_destino = dados["clientes"][destino]["saldo"] + valor
            salvar_cliente(usuario, saldo=saldo_origem)
            salvar_cliente(destino, saldo=saldo_destino)
            registrar_historico(usuario, "Transferência", valor, destino)
            flash("Transferência realizada!", "success")
        else:
            flash("Erro na transferência!", "danger")
        return redirect(url_for("dashboard"))
    return render_template("transferencia.html", dados=dados)

@app.route("/alterar_senha", methods=["GET", "POST"])
def alterar_senha():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    if request.method == "POST":
        nova_senha = request.form["senha"]
        salvar_cliente(usuario, senha=nova_senha)
        flash("Senha alterada com sucesso!", "success")
        return redirect(url_for("dashboard"))
    return render_template("alterar_senha.html", usuario=usuario)

@app.route("/historico")
def historico():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM historico WHERE usuario = ?", (usuario,))
    historico_user = [dict(row) for row in c.fetchall()]
    conn.close()
    return render_template("historico.html", historico=historico_user)

@app.route("/exportar_csv")
def exportar_csv():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM historico WHERE usuario = ?", (usuario,))
    historico_user = [dict(row) for row in c.fetchall()]
    conn.close()
    
    filename = f"historico_{usuario}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["usuario","acao","valor","destino","data"])
        writer.writeheader()
        writer.writerows(historico_user)
    return send_file(filename, as_attachment=True)

@app.route("/roleta", methods=["GET", "POST"])
def roleta():
    if "usuario" not in session or session["usuario"] == "admin":
        return redirect(url_for("login"))
    usuario = session["usuario"]
    dados = carregar_dados()
    resultado = None

    if request.method == "POST":
        aposta = float(request.form["aposta"])
        numero_escolhido = int(request.form["numero_escolhido"])
        numero_sorteado = int(request.form["numero_sorteado"])

        if aposta > dados["clientes"][usuario]["saldo"]:
            resultado = "Saldo insuficiente!"
        else:
            saldo_atual = dados["clientes"][usuario]["saldo"] - aposta
            salvar_cliente(usuario, saldo=saldo_atual)

            if numero_escolhido == numero_sorteado:
                ganho = aposta * 12  # paga 12x a aposta
                saldo_atual += ganho
                salvar_cliente(usuario, saldo=saldo_atual)
                resultado = f"Parabéns! Número sorteado: {numero_sorteado}. Você ganhou R$ {ganho:.2f}!"
                registrar_historico(usuario, f"Roleta (Vitória no {numero_sorteado})", ganho)
            else:
                resultado = f"Número sorteado: {numero_sorteado}. Você perdeu R$ {aposta:.2f}."
                registrar_historico(usuario, f"Roleta (Derrota no {numero_sorteado})", aposta)

    return render_template("roleta.html", resultado=resultado)


@app.route("/logout")
def logout():
    session.pop("usuario", None)
    return redirect(url_for("login"))

# -------------------- Rotas admin para aprovar depósitos --------------------
@app.route("/admin/depositos")
def admin_depositos():
    if "usuario" not in session or session["usuario"] != "admin":
        return redirect(url_for("login"))
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM depositos_pendentes WHERE aprovado = 0")
    depositos = [dict(row) for row in c.fetchall()]
    conn.close()
    return render_template("admin_depositos.html", depositos=depositos)

@app.route("/admin/aprovar/<int:id>")
def aprovar_deposito(id):
    if "usuario" not in session or session["usuario"] != "admin":
        return redirect(url_for("login"))
    conn = get_connection()
    c = conn.cursor()
    
    # Pega o depósito
    c.execute("SELECT * FROM depositos_pendentes WHERE id = ?", (id,))
    dep = c.fetchone()
    if dep:
        # Atualiza saldo do usuário
        c.execute("UPDATE clientes SET saldo = saldo + ? WHERE usuario = ?", (dep["valor"], dep["usuario"]))
        # Marca como aprovado
        c.execute("UPDATE depositos_pendentes SET aprovado = 1 WHERE id = ?", (id,))
        # Adiciona no histórico
        c.execute("INSERT INTO historico (usuario, acao, valor, destino, data) VALUES (?, ?, ?, ?, ?)",
                  (dep["usuario"], "Depósito Aprovado", dep["valor"], None, datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        conn.commit()
    
    conn.close()
    flash("Depósito aprovado!")
    return redirect(url_for("admin_depositos"))

if __name__ == "__main__":
    app.run(debug=True)
