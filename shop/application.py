from flask import Flask, jsonify
import hashlib, time, socket

application = Flask(__name__)
HOST = socket.gethostname()

PRODUCTS = [
    {"id": 1, "name": "Laptop", "price": 55000},
    {"id": 2, "name": "Headphones", "price": 2500},
    {"id": 3, "name": "Keyboard", "price": 1800},
]

def burn_cpu(ms=150):
    end = time.time() + ms / 1000
    n = 0
    while time.time() < end:
        hashlib.sha256(str(n).encode()).hexdigest()
        n += 1

@application.route("/")
def home():
    items = "".join(f"<li>{p['name']} - Rs {p['price']}</li>" for p in PRODUCTS)
    return f"<h1>CloudMart</h1><ul>{items}</ul><p>Served by: {HOST}</p>"

@application.route("/api/products")
def products():
    return jsonify(PRODUCTS)

@application.route("/checkout")
def checkout():
    burn_cpu(150)  # simulates heavy order processing
    return jsonify({"status": "order placed", "served_by": HOST})

@application.route("/health")
def health():
    return "ok"
