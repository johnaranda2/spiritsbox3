
from flask import Flask, request, jsonify, Blueprint
from flask_cors import CORS
from pymongo import MongoClient
from bson.regex import Regex
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from datetime import datetime
import cohere
import re, requests
from bson import ObjectId

app = Flask(__name__)
CORS(app)

from flask import render_template
@app.route("/")
def home():
    return render_template("index.html")

co = cohere.Client("aETls8igPmzPY9xfiowlOdTKzdxcD86Faunjbdts")

# MongoDB connection
client = MongoClient("mongodb+srv://admin:FpybIN95mvvtJbVr@spiritsbox.hp9nflo.mongodb.net/spiritsbox?retryWrites=true&w=majority")
db = client["SpiritsBox"]
customers_col = db["customers"]
drinks_col = db["drinks"]
history_col = db["recommendation_history"]

session_data = {}

def build_profile_vector(prefix, items):
    return " ".join([f"{prefix}_{item}" for item in items])

customer_bp = Blueprint("customers", __name__)

def extraer_preferencias(texto):
    texto = texto.lower()
    tipos = []
    sabores = []
    origenes = []

    posibles_tipos = ["beer", "wine", "whisky", "rum", "vodka", "brandy", "tequila", "cocktail", "gin"]
    posibles_sabores = ["sweet", "bitter", "spicy", "smoky", "fruity", "floral", "herbal"]
    posibles_origenes = ["mexico", "chile", "france", "scotland", "japan", "spain", "italy", "usa", "germany"]

    for tipo in posibles_tipos:
        if tipo in texto:
            tipos.append(tipo)

    for sabor in posibles_sabores:
        if sabor in texto:
            sabores.append(sabor)

    for origen in posibles_origenes:
        if origen in texto:
            origenes.append(origen.capitalize())

    return tipos, sabores, origenes

@app.route("/test_cliente")
def test_cliente():
    nombre = "Amelia Martin"
    cliente = customers_col.find_one({
        "name": { "$regex": f"^{re.escape(nombre.strip())}$", "$options": "i" }
    })
    if cliente:
        cliente["_id"] = str(cliente["_id"])  # 💡 CONVIERTE EL ObjectId A TEXTO
        return jsonify({"encontrado": True, "datos": cliente})
    return jsonify({"encontrado": False})

@customer_bp.route("/api/customers", methods=["GET"])
def get_customers():
    clientes = list(customers_col.find({}, {"_id": 0}))
    return jsonify(clientes)

@customer_bp.route("/api/customers/<name>", methods=["GET"])
def get_customer_detail(name):
    cliente = customers_col.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}, {"_id": 0})
    if not cliente:
        return jsonify({"error": "Cliente no encontrado"}), 404
    return jsonify(cliente)

@customer_bp.route("/api/customers/<name>/update", methods=["POST"])
def update_customer(name):
    data = request.get_json()
    preferencias = data.get("preferences", {})
    result = customers_col.update_one(
        {"name": {"$regex": f"^{name}$", "$options": "i"}},
        {"$set": {"preferences": preferencias}}
    )
    if result.matched_count:
        return jsonify({"success": True})
    return jsonify({"error": "No se encontró el cliente"}), 404

@app.route("/clientes")
def clientes_page():
    return render_template("clientes.html")

@app.route("/web")
def web():
    return render_template("/web.html")

@app.route("/recommendations_llm", methods=["POST"])
def recommendations_llm():
    data = request.get_json()
    messages = data.get("messages", [])
    nombre = None

    patrones_nombre = [
        r"my name is ([a-zA-ZÀ-ÿ\s]+)",
        r"i[’']?m ([a-zA-ZÀ-ÿ\s]+)",
        r"me llamo ([a-zA-ZÀ-ÿ\s]+)",
        r"mi nombre es ([a-zA-ZÀ-ÿ\s]+)",
        r"soy ([a-zA-ZÀ-ÿ\s]+)"
    ]

    for msg in messages:
        if msg["role"] == "user":
            texto = msg["content"].strip()
            for patron in patrones_nombre:
                match = re.search(patron, texto, re.IGNORECASE)
                if match:
                    nombre = match.group(1).strip().title()
                    break
            if not nombre and len(texto.split()) >= 2 and texto.replace(" ", "").isalpha():
                nombre = texto.title()
        if nombre:
            break

    if not nombre:
        return jsonify({"reply": "Hi! What's your name so I can help you with drink recommendations?"})

    nombre = nombre.strip()

    # Preparar estado si no existe
    if nombre not in session_data:
        session_data[nombre] = {
            "types": [],
            "flavor_profiles": [],
            "origins": [],
            "actualizando": False
        }

    # Ver último mensaje
    last_msg = messages[-1]["content"].strip().lower()

    cliente = customers_col.find_one({ "name": { "$regex": f"^{re.escape(nombre)}$", "$options": "i" } })

    # MODO ACTUALIZACIÓN
    if session_data[nombre].get("actualizando", False):
        tipos, sabores, origenes = extraer_preferencias(last_msg)
        estado = session_data[nombre]
        estado["types"] += [t for t in tipos if t not in estado["types"]]
        estado["flavor_profiles"] += [s for s in sabores if s not in estado["flavor_profiles"]]
        estado["origins"] += [o for o in origenes if o not in estado["origins"]]

        if estado["types"] and estado["flavor_profiles"] and estado["origins"]:
            customers_col.update_one(
                { "name": { "$regex": f"^{re.escape(nombre)}$", "$options": "i" }},
                { "$set": { "preferences": {
                    "types": estado["types"],
                    "flavor_profiles": estado["flavor_profiles"],
                    "origins": estado["origins"]
                }}}
            )
            del session_data[nombre]
            return jsonify({"reply": f"Thanks {nombre}, your preferences were updated. Would you like a new recommendation?"})
        else:
            faltantes = []
            if not estado["types"]: faltantes.append("drink type (e.g., wine, beer)")
            if not estado["flavor_profiles"]: faltantes.append("flavor (e.g., sweet, smoky)")
            if not estado["origins"]: faltantes.append("origin (e.g., Chile, France)")
            return jsonify({"reply": f"Got it. Please tell me your " + " and ".join(faltantes) + "."})

    # ACTIVAR ACTUALIZACIÓN
    if last_msg in ["yes", "sí", "i want to update", "update my preferences"]:
        session_data[nombre] = {
            "types": [],
            "flavor_profiles": [],
            "origins": [],
            "actualizando": True
        }
        return jsonify({"reply": f"Sure, {nombre}. Let's update your preferences. What type of drinks do you enjoy?"})

    if last_msg in ["no", "no thanks", "not now"]:
        return jsonify({"reply": f"Alright, {nombre}. Let me know if you need anything else!"})

    # CLIENTE YA EXISTE
    if cliente:
        prefs = cliente.get("preferences", {})
        tipos = ", ".join(prefs.get("types", [])) or "not specified"
        sabores = ", ".join(prefs.get("flavor_profiles", [])) or "not specified"
        origenes = ", ".join(prefs.get("origins", [])) or "not specified"

        try:
            res = requests.get(f"http://localhost:5050/api/recommendations?name={nombre}")
            recomendaciones = res.json() if res.ok else []
        except Exception as e:
            recomendaciones = []

        lista_recs = "\n".join([
            f"- {r['name']} ({r['type']}, {r['origin']}) — {round(r['similarity'] * 100)}%"
            for r in recomendaciones[:3]
        ])

        return jsonify({"reply": (
            f"Hi {nombre}, I found your preferences:\n"
            f"• Type: {tipos}\n• Flavor: {sabores}\n• Origin: {origenes}\n\n"
            f"Here are your top recommendations:\n{lista_recs}\n\n"
            f"Would you like to update your preferences?"
        )})

    # CLIENTE NUEVO → recolectar paso a paso
    tipos, sabores, origenes = extraer_preferencias(last_msg)
    estado = session_data[nombre]
    estado["types"] += [t for t in tipos if t not in estado["types"]]
    estado["flavor_profiles"] += [s for s in sabores if s not in estado["flavor_profiles"]]
    estado["origins"] += [o for o in origenes if o not in estado["origins"]]

    if estado["types"] and estado["flavor_profiles"] and estado["origins"]:
        customers_col.insert_one({
            "name": nombre,
            "preferences": estado,
            "history": [],
            "feedback": {},
        })
        del session_data[nombre]

        try:
            res = requests.get(f"http://localhost:5050/api/recommendations?name={nombre}")
            recomendaciones = res.json() if res.ok else []
        except Exception as e:
            recomendaciones = []

        lista_recs = "\n".join([
            f"- {r['name']} ({r['type']}, {r['origin']}) — {round(r['similarity'] * 100)}%"
            for r in recomendaciones[:3]
        ])

        return jsonify({"reply": (
            f"Thanks {nombre}! I've saved your preferences:\n"
            f"• Type: {', '.join(estado['types'])}\n"
            f"• Flavor: {', '.join(estado['flavor_profiles'])}\n"
            f"• Origin: {', '.join(estado['origins'])}\n\n"
            f"Here are your top recommendations:\n{lista_recs}"
        )})
    else:
        faltantes = []
        if not estado["types"]: faltantes.append("drink type (e.g., wine, beer)")
        if not estado["flavor_profiles"]: faltantes.append("flavor (e.g., sweet, smoky)")
        if not estado["origins"]: faltantes.append("origin (e.g., Chile, France)")
        return jsonify({"reply": f"Great, {nombre}! Could you tell me your " + " and ".join(faltantes) + "?"})



@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html", titulo="Chatbot")

@app.route("/cliente")
def cliente():
    return render_template("cliente.html", titulo="Gestión de Clientes")

@app.route("/recomendacion")
def recomendacion():
    return render_template("recomendacion.html", titulo="Módulo de Recomendaciones")

@app.route("/historial")
def historial():
    return render_template("index.html", titulo="Historial de Recomendaciones")

@app.route("/estadisticas")
def estadisticas():
    return render_template("estadisticas.html", titulo="Dashboard de Estadísticas")

@app.route("/api/estadisticas")
def api_estadisticas():
    try:
        clientes = list(customers_col.find())
        tipos = {}
        sabores = {}
        origenes = {}

        for cliente in clientes:
            prefs = cliente.get("preferences", {})
            for t in prefs.get("types", []):
                if t:
                    tipos[t] = tipos.get(t, 0) + 1
            for s in prefs.get("flavor_profiles", []):
                if s:
                    sabores[s] = sabores.get(s, 0) + 1
            for o in prefs.get("origins", []):
                if o:
                    origenes[o] = origenes.get(o, 0) + 1

        total_recomendaciones = history_col.count_documents({})
        total_clientes = len(clientes)

        return jsonify({
            "tipos": tipos,
            "sabores": sabores,
            "origenes": origenes,
            "total_recomendaciones": total_recomendaciones,
            "total_clientes": total_clientes
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing 'name' parameter"}), 400

    cliente = customers_col.find_one({"name": Regex(f"^{name}$", "i")})
    if not cliente:
        return jsonify({"error": "Client not found"}), 404

    prefs = cliente.get("preferences", {})
    prefs_text = (
        build_profile_vector("type", prefs.get("types", [])) + " " +
        build_profile_vector("profile", prefs.get("flavor_profiles", [])) + " " +
        build_profile_vector("origin", prefs.get("origins", []))
    )

    bebidas = list(drinks_col.find())
    if not bebidas:
        return jsonify({"error": "No drinks found in database"}), 500

    df = pd.DataFrame(bebidas)
    df["text"] = df.apply(
        lambda row: f"type_{row.get('type', '')} " +
                    " ".join([f"profile_{p}" for p in row.get('flavor_profile', [])]) +
                    f" origin_{row.get('origin', '')}",
        axis=1
    )
    df["name"] = df["name"].fillna("Unnamed")

    vectorizer = CountVectorizer()
    vectors = vectorizer.fit_transform([prefs_text] + df["text"].tolist())
    similarity = cosine_similarity(vectors[0:1], vectors[1:]).flatten()

    df["similarity"] = similarity
    top_matches = df.sort_values(by="similarity", ascending=False).head(5)

    results = top_matches[["name", "type", "origin", "similarity"]].to_dict(orient="records")

    history_entry = {
        "customer_name": cliente["name"],
        "date": datetime.utcnow().isoformat(),
        "recommendations": results
    }
    history_col.insert_one(history_entry)

    return jsonify(results)

@app.route("/history", methods=["GET"])
def get_history():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing 'name' parameter"}), 400

    history = list(history_col.find({"customer_name": Regex(f"^{name}$", "i")}).sort("date", -1))
    for entry in history:
        entry["_id"] = str(entry["_id"])
    return jsonify(history)

@app.route("/customer")
def get_customer():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing 'name' parameter"}), 400
    cliente = customers_col.find_one({"name": Regex(f"^{name}$", "i")})
    if not cliente:
        return jsonify({"error": "Client not found"}), 404
    cliente["_id"] = str(cliente["_id"])
    return jsonify(cliente)

@app.route("/customer/update", methods=["POST"])
def update_customer():
    data = request.json
    name = data.get("name", "")
    prefs = data.get("preferences", {})
    result = customers_col.update_one({"name": Regex(f"^{name}$", "i")}, {"$set": {"preferences": prefs}})
    return jsonify({"success": result.modified_count > 0})

@app.route("/recommend_all", methods=["POST"])
def recommend_all():
    clientes = list(customers_col.find())
    bebidas = list(drinks_col.find())
    
    if not bebidas:
        return jsonify({"error": "No drinks found"}), 500

    df = pd.DataFrame(bebidas)
    df["text"] = df.apply(
        lambda row: f"type_{row.get('type', '')} " +
                    " ".join([f"profile_{p}" for p in row.get('flavor_profile', [])]) +
                    f" origin_{row.get('origin', '')}",
        axis=1
    )
    df["name"] = df["name"].fillna("Unnamed")

    vectorizer = CountVectorizer()
    text_corpus = df["text"].tolist()

    resultados = []

    for cliente in clientes:
        prefs = cliente.get("preferences", {})
        prefs_text = (
            build_profile_vector("type", prefs.get("types", [])) + " " +
            build_profile_vector("profile", prefs.get("flavor_profiles", [])) + " " +
            build_profile_vector("origin", prefs.get("origins", []))
        )
        if not prefs_text.strip():
            continue  # Skip cliente sin preferencias

        vectors = vectorizer.fit_transform([prefs_text] + text_corpus)
        similarity = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
        df["similarity"] = similarity
        top_matches = df.sort_values(by="similarity", ascending=False).head(5)
        recs = top_matches[["name", "type", "origin", "similarity"]].to_dict(orient="records")

        history_entry = {
            "customer_name": cliente["name"],
            "date": datetime.utcnow().isoformat(),
            "recommendations": recs
        }
        history_col.insert_one(history_entry)
        resultados.append({"cliente": cliente["name"], "total": len(recs)})

    return jsonify({
        "clientes_procesados": len(resultados),
        "detalle": resultados
    })

app.register_blueprint(customer_bp)
if __name__ == "__main__":
    app.run(debug=True, port=5050)
