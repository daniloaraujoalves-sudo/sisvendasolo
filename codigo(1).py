from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "mercado_2026"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'venda.db')

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, senha TEXT, cargo TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT UNIQUE, senha TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, preco REAL, estoque INTEGER, imagem TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS carrinho (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, produto_id INTEGER, quantidade INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS vendas (id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, quantidade INTEGER, total REAL, cliente_id INTEGER, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        if not c.execute("SELECT * FROM usuarios WHERE usuario='admin'").fetchone():
            c.execute("INSERT INTO usuarios VALUES (NULL,?,?,?)", ('admin', generate_password_hash('admin123'), 'admin'))
        conn.commit()

init_db()

@app.route('/')
def index():
    q = request.args.get('q')
    aba = request.args.get('aba', 'loja') # Sistema de abas simples
    
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        
        # Busca de produtos
        if q:
            produtos = conn.execute("SELECT * FROM produtos WHERE nome LIKE ?", ('%' + q + '%',)).fetchall()
        else:
            produtos = conn.execute("SELECT * FROM produtos").fetchall()

        carrinho_qtd = 0
        historico = []
        faturamento = 0

        if session.get('cargo') == 'cliente':
            res = conn.execute("SELECT SUM(quantidade) FROM carrinho WHERE cliente_id=?", (session['user_id'],)).fetchone()[0]
            carrinho_qtd = res if res else 0
            # Busca histórico do cliente
            historico = conn.execute("""
                SELECT v.*, p.nome FROM vendas v 
                JOIN produtos p ON v.produto_id = p.id 
                WHERE v.cliente_id=? ORDER BY v.id DESC""", (session['user_id'],)).fetchall()

        if session.get('cargo') == 'admin':
            res = conn.execute("SELECT SUM(total) FROM vendas").fetchone()[0]
            faturamento = res if res else 0
            # Admin vê todas as vendas
            historico = conn.execute("SELECT v.*, p.nome, c.nome as cliente FROM vendas v JOIN produtos p ON v.produto_id = p.id JOIN clientes c ON v.cliente_id = c.id").fetchall()

    return render_template("index.html", produtos=produtos, carrinho_qtd=carrinho_qtd, faturamento=faturamento, aba=aba, historico=historico)

@app.route('/login', methods=['POST'])
def login():
    user = request.form['u']
    senha = request.form['s']
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        adm = conn.execute("SELECT * FROM usuarios WHERE usuario=?", (user,)).fetchone()
        if adm and check_password_hash(adm['senha'], senha):
            session.update({'user_id': adm['id'], 'nome': 'Admin', 'cargo': 'admin'})
            return redirect('/')
        
        cli = conn.execute("SELECT * FROM clientes WHERE email=?", (user,)).fetchone()
        if cli and check_password_hash(cli['senha'], senha):
            session.update({'user_id': cli['id'], 'nome': cli['nome'], 'cargo': 'cliente'})
            return redirect('/')
    flash("Acesso negado!", "danger")
    return redirect('/')

@app.route('/register', methods=['POST'])
def register():
    nome, email, senha = request.form['nome'], request.form['email'], generate_password_hash(request.form['senha'])
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO clientes (nome,email,senha) VALUES (?,?,?)", (nome, email, senha))
        flash("Conta criada!", "success")
    except: flash("Erro ao cadastrar!", "danger")
    return redirect('/')

@app.route('/add_carrinho/<int:id>', methods=['POST'])
def add_carrinho(id):
    if session.get('cargo') != 'cliente': return redirect('/')
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO carrinho (cliente_id,produto_id,quantidade) VALUES (?,?,1)", (session['user_id'], id))
    return redirect('/')

@app.route('/finalizar')
def finalizar():
    if session.get('cargo') != 'cliente': return redirect('/')
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        itens = c.execute("SELECT produto_id, quantidade FROM carrinho WHERE cliente_id=?", (session['user_id'],)).fetchall()
        for p_id, qtd in itens:
            p = c.execute("SELECT preco, estoque FROM produtos WHERE id=?", (p_id,)).fetchone()
            if p and int(p[1]) >= int(qtd):
                c.execute("UPDATE produtos SET estoque = estoque - ? WHERE id=?", (qtd, p_id))
                c.execute("INSERT INTO vendas (produto_id, quantidade, total, cliente_id) VALUES (?,?,?,?)", (p_id, qtd, p[0]*qtd, session['user_id']))
        c.execute("DELETE FROM carrinho WHERE cliente_id=?", (session['user_id'],))
        conn.commit()
    flash("Compra realizada!", "success")
    return redirect('/?aba=historico')

@app.route('/admin/add', methods=['POST'])
def add_produto():
    if session.get('cargo') == 'admin':
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO produtos (nome,preco,estoque,imagem) VALUES (?,?,?,?)", 
                         (request.form['nome'], request.form['preco'], request.form['estoque'], request.form['imagem']))
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)
