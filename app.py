from flask import Flask, render_template, request
import json
import os
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

app = Flask(__name__, template_folder="templates", static_folder="static")

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
        "ingredienti": "100 g di okara di macadamia, 1 cucchiaio abbondante di olio evo, 1 bustina di vanillina, 3 datteri, 1 cucchiaio di semi di chia, 2 cucchiaini di cacao, 1 uovo, 2 cucchiai o più di fiocchi d'avena",
        "istruzioni": "Frulla l'okara di macadamia con l'olio, la vanillina, i datteri, i semi di chia, il cacao e l'uovo fino a ottenere un impasto omogeneo. Aggiungi gli fiocchi d'avena fino a raggiungere una consistenza abbastanza soda da poter formare dei biscotti. Forma delle palline o piccoli biscotti, disponili su una teglia e cuoci a 180 °C per 12-15 minuti, fino a dorare leggermente.",
        "difficolta": "Facile",
        "tempo_minuti": 20,
        "tipo_pasto": "Spuntino",
        "tags": "dolce, snack, longevità"
    },
    {
        "titolo": "Pasta cremosa al branzino e broccoli",
        "ingredienti": "per mezzo chilo di pasta integrale, abbondanti broccoli al vapore, sale, 1 cucchiaio di lievito nutrizionale, acqua, mezzo limone, 2 cucchiai di olio evo, 1 cucchiaio scarso di burro di anacardi, 250 g di filetti di branzino cotti, 1 spicchio d'aglio, olio per cuocere il pesce",
        "istruzioni": "Lessa i broccoli al vapore fino a renderli morbidi, poi scolali e frullali con sale, lievito nutrizionale, acqua, mezzo limone, olio evo e il burro di anacardi fino ad ottenere una crema liscia. In una padella cuoci il branzino con un filo d'olio e uno spicchio d'aglio, poi sfilacciarlo o lasciarlo a pezzetti. Cuoci la pasta integrale, scolala al dente e condisci con la crema di broccoli. Aggiungi il branzino a cima e servi subito.",
        "difficolta": "Media",
        "tempo_minuti": 35,
        "tipo_pasto": "Pranzo",
        "tags": "pasta, pesce, cremosa"
    },
    {
        "titolo": "Rigatoni al ragù di coniglio",
        "ingredienti": "1 coscia di coniglio già cotta e scarnificata, 200 g di rigatoni integrali, 1 cipolla piccola, 1 carota piccola, mezzo cucchiaino scarso di curcuma, un po' di polvere d'aglio, mezzo dado, sale, olio, 1 bicchiere d'acqua",
        "istruzioni": "Fai soffriggere la cipolla e la carota a cubetti piccoli in un filo d'olio. Aggiungi il coniglio già cotto e scarnificato, la curcuma, la polvere d'aglio, il dado e un bicchiere d'acqua. Cuoci a fuoco lento per circa 50 minuti, mescolando di tanto in tanto fino a ottenere un ragù saporito. Nel frattempo cuoci i rigatoni integrali. Scola la pasta, condisci con il ragù e servi caldo.",
        "difficolta": "Media",
        "tempo_minuti": 60,
        "tipo_pasto": "Cena",
        "tags": "pasta, carne, comfort food"
    }
]


def normalize_recipe(raw_recipe):
    return {
        "titolo": raw_recipe.get("titolo") or raw_recipe.get("title") or "",
        "ingredienti": raw_recipe.get("ingredienti") or raw_recipe.get("ingredients") or "",
        "istruzioni": raw_recipe.get("istruzioni") or raw_recipe.get("instructions") or "",
        "difficolta": raw_recipe.get("difficolta") or raw_recipe.get("difficulty") or "Facile",
        "tempo_minuti": int(raw_recipe.get("tempo_minuti") or raw_recipe.get("time") or 0),
        "tipo_pasto": raw_recipe.get("tipo_pasto") or raw_recipe.get("meal_type") or "Pranzo",
        "tags": raw_recipe.get("tags") or ""
    }


def is_valid_recipe(recipe):
    title = (recipe.get("titolo") or "").strip()
    tags = (recipe.get("tags") or "").lower()
    if not title:
        return False
    if title.lower() == "pasta test" or "test" in tags:
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
        recipe["ingredienti"],
        recipe["istruzioni"],
        recipe["difficolta"],
        recipe["tipo_pasto"],
        recipe["tags"]
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
                       for x in recipe["tags"].split(",") if x.strip()]
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


@app.route('/', methods=['GET', 'POST'])
def home():
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
            ingredients = request.form.get('ingredients', '').strip()
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
                    'tags': tags
                }
                recipes.append(recipe)
                save_recipes(recipes)
                save_recipe_to_supabase(recipe)
                message = 'Ricetta aggiunta con successo.'

    query = request.args.get('q', '').strip(
    ) or request.form.get('q', '').strip()
    difficulty = request.args.get('difficulty', '').strip(
    ) or request.form.get('difficulty', '').strip()
    max_time = request.args.get('max_time', '').strip(
    ) or request.form.get('max_time', '').strip()
    meal_type = request.args.get('meal_type', '').strip(
    ) or request.form.get('meal_type', '').strip()
    tag_filter = request.args.get('tag', '').strip(
    ) or request.form.get('tag', '').strip()

    filtered_recipes = [
        recipe for recipe in recipes
        if recipe_matches(recipe, query, difficulty, max_time, meal_type, tag_filter)
    ]

    return build_page(filtered_recipes, query, difficulty, max_time, meal_type, tag_filter, message, success)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
