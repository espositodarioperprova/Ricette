from flask import Flask, redirect, render_template, request, url_for
import json
import os
import re
import unicodedata
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


def _to_text_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _to_ingredient_map(value):
    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get(
                    "ingrediente") or "").strip()
                qty = str(item.get("quantity") or item.get(
                    "quantita") or item.get("q") or "").strip()
                if name:
                    items.append({"name": name, "quantity": qty})
            else:
                text = str(item).strip()
                if text:
                    items.append({"name": text, "quantity": ""})
        return items
    if isinstance(value, str):
        return [{"name": part.strip(), "quantity": ""} for part in value.split(",") if part.strip()]
    return []


def _slugify(text):
    normalized = unicodedata.normalize("NFKD", text).encode(
        "ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "ricetta"


app = Flask(__name__, template_folder="templates", static_folder="static")
app.jinja_env.filters["slugify"] = _slugify

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "recipes.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cambiaquesta")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE", "recipes")

DEFAULT_RECIPES = [
    {
        "titolo": "Biscotti della longevità",
        "ingredienti": [
            {"name": "100 g di okara di macadamia", "quantity": ""},
            {"name": "1 cucchiaio abbondante di olio evo", "quantity": ""},
            {"name": "1 bustina di vanillina", "quantity": ""},
            {"name": "3 datteri", "quantity": ""},
            {"name": "1 cucchiaio di semi di chia", "quantity": ""},
            {"name": "2 cucchiaini di cacao", "quantity": ""},
            {"name": "1 uovo", "quantity": ""},
            {"name": "2 cucchiai o più di fiocchi d'avena", "quantity": ""}
        ],
        "istruzioni": "Frulla l'okara di macadamia con l'olio, la vanillina, i datteri, i semi di chia, il cacao e l'uovo fino a ottenere un impasto omogeneo. Aggiungi gli fiocchi d'avena fino a raggiungere una consistenza abbastanza soda da poter formare dei biscotti. Forma delle palline o piccoli biscotti, disponili su una teglia e cuoci a 180 °C per 12-15 minuti, fino a dorare leggermente.",
        "difficolta": "Facile",
        "tempo_minuti": 20,
        "tipo_pasto": "Spuntino",
        "tags": ["dolce", "snack", "longevità"]
    },
    {
        "titolo": "Pasta cremosa al branzino e broccoli",
        "ingredienti": [
            {"name": "mezzo chilo di pasta integrale", "quantity": ""},
            {"name": "broccoli al vapore", "quantity": ""},
            {"name": "sale", "quantity": ""},
            {"name": "1 cucchiaio di lievito nutrizionale", "quantity": ""},
            {"name": "acqua", "quantity": ""},
            {"name": "mezzo limone", "quantity": ""},
            {"name": "2 cucchiai di olio evo", "quantity": ""},
            {"name": "1 cucchiaio scarso di burro di anacardi", "quantity": ""},
            {"name": "250 g di filetti di branzino cotti", "quantity": ""},
            {"name": "1 spicchio d'aglio", "quantity": ""},
            {"name": "olio per cuocere il pesce", "quantity": ""}
        ],
        "istruzioni": "Lessa i broccoli al vapore fino a renderli morbidi, poi scolali e frullali con sale, lievito nutrizionale, acqua, mezzo limone, olio evo e il burro di anacardi fino ad ottenere una crema liscia. In una padella cuoci il branzino con un filo d'olio e uno spicchio d'aglio, poi sfilacciarlo o lasciarlo a pezzetti. Cuoci la pasta integrale, scolala al dente e condisci con la crema di broccoli. Aggiungi il branzino a cima e servi subito.",
        "difficolta": "Media",
        "tempo_minuti": 35,
        "tipo_pasto": "Pranzo",
        "tags": ["pasta", "pesce", "cremosa"]
    },
    {
        "titolo": "Rigatoni al ragù di coniglio",
        "ingredienti": [
            {"name": "1 coscia di coniglio già cotta e scarnificata", "quantity": ""},
            {"name": "200 g di rigatoni integrali", "quantity": ""},
            {"name": "1 cipolla piccola", "quantity": ""},
            {"name": "1 carota piccola", "quantity": ""},
            {"name": "mezzo cucchiaino scarso di curcuma", "quantity": ""},
            {"name": "polvere d'aglio", "quantity": ""},
            {"name": "mezzo dado", "quantity": ""},
            {"name": "sale", "quantity": ""},
            {"name": "olio", "quantity": ""},
            {"name": "1 bicchiere d'acqua", "quantity": ""}
        ],
        "istruzioni": "Fai soffriggere la cipolla e la carota a cubetti piccoli in un filo d'olio. Aggiungi il coniglio già cotto e scarnificato, la curcuma, la polvere d'aglio, il dado e un bicchiere d'acqua. Cuoci a fuoco lento per circa 50 minuti, mescolando di tanto in tanto fino a ottenere un ragù saporito. Nel frattempo cuoci i rigatoni integrali. Scola la pasta, condisci con il ragù e servi caldo.",
        "difficolta": "Media",
        "tempo_minuti": 60,
        "tipo_pasto": "Cena",
        "tags": ["pasta", "carne", "comfort food"]
    },
    {
        "titolo": "Spaghetti integrali all’orata, pomodorini e crema di carote",
        "ingredienti": [
            {"name": "500 g di spaghetti integrali", "quantity": ""},
            {"name": "250 g di filetti d'orata", "quantity": ""},
            {"name": "400 g di pomodorini", "quantity": ""},
            {"name": "2 carote molto ben lessate", "quantity": ""},
            {"name": "acqua", "quantity": ""},
            {"name": "olio evo", "quantity": ""},
            {"name": "sale", "quantity": ""},
            {"name": "aglio", "quantity": ""},
            {"name": "poco dado in polvere", "quantity": ""},
            {"name": "2-3 cucchiaioni pieni di lievito nutrizionale", "quantity": ""}
        ],
        "istruzioni": "Lessa le carote fino a renderle molto morbide, poi scolale e frullale con acqua, olio, sale, aglio, un po' di dado in polvere e il lievito nutrizionale fino a ottenere una crema liscia e salsosa. In una padella cuoci i pomodorini con un filo d'olio e uno spicchio d'aglio, quindi aggiungi l'orata e cuocila delicatamente. Nel frattempo cuoci gli spaghetti integrali al dente, scolali e condisci con il sughetto di pomodorini e il pesce. Servi con la crema di carote a fianco o sopra, per un piatto ricco e molto saporito.",
        "difficolta": "Media",
        "tempo_minuti": 35,
        "tipo_pasto": "Cena",
        "tags": ["pasta", "pesce", "cremosa", "integrale"]
    },
    {
        "titolo": "Polpette di carne e spinaci",
        "ingredienti": [
            {"name": "500 g di macinato misto", "quantity": ""},
            {"name": "250 g di spinaci surgelati", "quantity": ""},
            {"name": "2 uova", "quantity": ""},
            {"name": "pangrattato", "quantity": ""},
            {"name": "3 cucchiai di latte", "quantity": ""},
            {"name": "aglio", "quantity": ""},
            {"name": "sale", "quantity": ""},
            {"name": "curcuma", "quantity": ""}
        ],
        "istruzioni": "Lessa gli spinaci surgelati, strizzali bene e tritali grossolanamente. In una ciotola mescola il macinato, gli spinaci, le uova, il pangrattato, il latte, l'aglio, il sale e un pizzico di curcuma fino a ottenere un composto compatto. Forma le polpette, sistemale su una teglia e cuoci in forno a 180-200 °C per 20-25 minuti, fino a dorare bene.",
        "difficolta": "Media",
        "tempo_minuti": 30,
        "tipo_pasto": "Cena",
        "tags": ["carne", "comfort", "forno"]
    }
]


def normalize_recipe(raw_recipe):
    return {
        "titolo": raw_recipe.get("titolo") or raw_recipe.get("title") or "",
        "ingredienti": _to_ingredient_map(raw_recipe.get("ingredienti") or raw_recipe.get("ingredients")),
        "istruzioni": raw_recipe.get("istruzioni") or raw_recipe.get("instructions") or "",
        "difficolta": raw_recipe.get("difficolta") or raw_recipe.get("difficulty") or "Facile",
        "tempo_minuti": int(raw_recipe.get("tempo_minuti") or raw_recipe.get("time") or 0),
        "tipo_pasto": raw_recipe.get("tipo_pasto") or raw_recipe.get("meal_type") or "Pranzo",
        "tags": _to_text_list(raw_recipe.get("tags"))
    }


def is_valid_recipe(recipe):
    title = (recipe.get("titolo") or "").strip()
    tags = [t.lower() for t in recipe.get("tags", []) if isinstance(t, str)]
    if not title:
        return False
    if title.lower() == "pasta test" or any("test" in tag for tag in tags):
        return False
    return True


def load_recipes():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            request = urllib_request.Request(
                f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=*",
                headers=headers,
                method="GET"
            )
            with urllib_request.urlopen(request, timeout=10) as response:
                data = json.load(response)
                if isinstance(data, list):
                    cleaned = [normalize_recipe(
                        item) for item in data if is_valid_recipe(normalize_recipe(item))]
                    if cleaned:
                        return cleaned
        except (HTTPError, URLError, TimeoutError, ValueError):
            pass

    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
            if isinstance(data, list) and data:
                cleaned = [normalize_recipe(
                    item) for item in data if is_valid_recipe(normalize_recipe(item))]
                if cleaned:
                    return cleaned
        except json.JSONDecodeError:
            pass

    return [dict(recipe) for recipe in DEFAULT_RECIPES]


def save_recipes(recipes):
    DATA_FILE.write_text(json.dumps(
        recipes, ensure_ascii=False, indent=2), encoding='utf-8')


def save_recipe_to_supabase(recipe):
    if not (SUPABASE_URL and SUPABASE_KEY):
        return
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        payload = json.dumps(recipe).encode("utf-8")
        request = urllib_request.Request(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
            data=payload,
            headers=headers,
            method="POST"
        )
        with urllib_request.urlopen(request, timeout=10):
            pass
    except (HTTPError, URLError, TimeoutError, ValueError):
        pass


recipes = load_recipes()


def recipe_matches(recipe, query, difficulty, max_time, meal_type, tag_filter):
    haystack = " ".join([
        recipe["titolo"],
        " ".join([item.get("name", "")
                 for item in recipe.get("ingredienti", [])]),
        recipe["istruzioni"],
        recipe["difficolta"],
        recipe["tipo_pasto"],
        " ".join(recipe.get("tags", []))
    ]).lower()

    if query and query.lower() not in haystack:
        return False
    if difficulty and recipe["difficolta"].lower() != difficulty.lower():
        return False
    if max_time and recipe["tempo_minuti"] > int(max_time):
        return False
    if meal_type and recipe["tipo_pasto"].lower() != meal_type.lower():
        return False
    if tag_filter:
        wanted_tags = [x.strip().lower()
                       for x in tag_filter.split(",") if x.strip()]
        recipe_tags = [x.strip().lower()
                       for x in recipe.get("tags", []) if x.strip()]
        if not all(any(tag == wanted for tag in recipe_tags) for wanted in wanted_tags):
            return False
    return True


def build_page(filtered_recipes, query, difficulty, max_time, meal_type, tag_filter, message=None, success=True):
    return render_template(
        "index.html",
        recipes=filtered_recipes,
        query=query,
        difficulty=difficulty,
        max_time=max_time,
        meal_type=meal_type,
        tag_filter=tag_filter,
        message=message,
        success=success,
    )


@app.route('/ricetta/<slug>', methods=['GET'])
def recipe_detail(slug):
    recipes = load_recipes()
    recipe = next((item for item in recipes if _slugify(
        item['titolo']) == slug.lower()), None)
    if not recipe:
        return "Ricetta non trovata", 404
    return render_template("recipe_detail.html", recipe=recipe)


@app.route('/aggiungi', methods=['GET', 'POST'])
def add_recipe():
    message = None
    success = True
    recipes = load_recipes()

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        if password != ADMIN_PASSWORD:
            message = 'Password sbagliata. Usa quella impostata come variabile d’ambiente.'
            success = False
        else:
            title = request.form.get('title', '').strip()
            ingredient_names = request.form.getlist('ingredient_name[]')
            ingredient_quantities = request.form.getlist(
                'ingredient_quantity[]')
            ingredients = [
                {"name": name.strip(), "quantity": quantity.strip()}
                for name, quantity in zip(ingredient_names, ingredient_quantities)
                if name.strip()
            ]
            instructions = request.form.get('instructions', '').strip()
            difficulty = request.form.get('difficulty_add', 'Facile').strip()
            time = request.form.get('time', '0').strip()
            meal_type = request.form.get('meal_type_add', 'Pranzo').strip()
            tags = request.form.get('tags', '').strip()

            if not title or not ingredients or not instructions or not time:
                message = 'Compila titolo, ingredienti, procedimento e tempo.'
                success = False
            else:
                recipe = {
                    'titolo': title,
                    'ingredienti': ingredients,
                    'istruzioni': instructions,
                    'difficolta': difficulty,
                    'tempo_minuti': int(time),
                    'tipo_pasto': meal_type,
                    'tags': _to_text_list(tags)
                }
                recipes.append(recipe)
                save_recipes(recipes)
                save_recipe_to_supabase(recipe)
                return redirect(url_for('recipe_detail', slug=_slugify(title)))

    return render_template(
        "add_recipe.html",
        message=message,
        success=success,
        form=request.form,
    )


@app.route('/', methods=['GET'])
def home():
    recipes = load_recipes()

    query = request.args.get('q', '').strip()
    difficulty = request.args.get('difficulty', '').strip()
    max_time = request.args.get('max_time', '').strip()
    meal_type = request.args.get('meal_type', '').strip()
    tag_filter = request.args.get('tag', '').strip()

    filtered_recipes = [
        recipe for recipe in recipes
        if recipe_matches(recipe, query, difficulty, max_time, meal_type, tag_filter)
    ]

    return build_page(filtered_recipes, query, difficulty, max_time, meal_type, tag_filter)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
