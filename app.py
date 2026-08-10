from flask import Flask, redirect, render_template, request, url_for
import json
import os
import random
import re
import unicodedata
from datetime import date
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename


def _to_text_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _split_ingredient(text):
    text = text.strip()
    quantity_pattern = (
        r"^(?P<quantity>(?:\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+)?|mezzo|mezza|un|una)"
        r"\s*(?:g|gr|kg|ml|l|cucchiai?o?n?i?|cucchiaini?|bicchieri?|bustine?|"
        r"spicchi?|cosce?|carote?|cipolle?|uova?|datteri?)?)\s+(?:di\s+)?(?P<name>.+)$"
    )
    match = re.match(quantity_pattern, text, flags=re.IGNORECASE)
    if not match:
        return {"name": text, "quantity": ""}
    return {
        "name": match.group("name").strip(),
        "quantity": match.group("quantity").strip(),
    }


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
                    items.append({"name": name, "quantity": qty}
                                 if qty else _split_ingredient(name))
            else:
                text = str(item).strip()
                if text:
                    items.append(_split_ingredient(text))
        return items
    if isinstance(value, str):
        return [_split_ingredient(part) for part in value.split(",") if part.strip()]
    return []


def _slugify(text):
    normalized = unicodedata.normalize("NFKD", text).encode(
        "ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "ricetta"


app = Flask(__name__, template_folder="templates", static_folder="static")
app.jinja_env.filters["slugify"] = _slugify
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "recipes.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cambiaquesta")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STORAGE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE", "recipes")
SUPABASE_STORAGE_BUCKET = os.environ.get(
    "SUPABASE_STORAGE_BUCKET", "recipe-images")
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "avif"}
LOCAL_PASTA_CREMOSA_IMAGE_URL = (
    "/static/pasta-cremosa-al-branzino-e-broccoli/crema_di_broccolo.png"
)

RECIPE_DESCRIPTIONS = {
    "Biscotti della longevità": "Un biscotto intenso e naturalmente dolce, pensato per una pausa che sa davvero di buono.",
    "Pasta cremosa al branzino e broccoli": "Cremosa senza essere pesante, con il branzino che rende speciale anche un pranzo feriale.",
    "Rigatoni al ragù di coniglio": "Un ragù lento, profondo e rassicurante per quando hai voglia di cucinare sul serio.",
    "Spaghetti integrali all’orata, pomodorini e crema di carote": "Pesce, pomodorini e una crema luminosa: un pranzo completo che sembra da ristorante.",
    "Polpette di carne e spinaci": "Morbide dentro, dorate fuori e abbastanza pratiche da risolvere la cena di tutti.",
}

DEFAULT_DESCRIPTION = "Una ricetta da tenere a portata di mano quando vuoi portare qualcosa di buono in tavola."

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
        "tags": ["pasta", "pesce", "cremosa"],
        "immagine": LOCAL_PASTA_CREMOSA_IMAGE_URL
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
        "tipo_pasto": "Pranzo",
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
        "tipo_pasto": "Pranzo",
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
    title = raw_recipe.get("titolo") or raw_recipe.get("title") or ""
    image = str(raw_recipe.get("immagine") or "").strip()
    if "images.unsplash.com" in image:
        image = ""
    return {
        "titolo": title,
        "ingredienti": _to_ingredient_map(raw_recipe.get("ingredienti") or raw_recipe.get("ingredients")),
        "istruzioni": raw_recipe.get("istruzioni") or raw_recipe.get("instructions") or "",
        "difficolta": raw_recipe.get("difficolta") or raw_recipe.get("difficulty") or "Facile",
        "tempo_minuti": int(raw_recipe.get("tempo_minuti") or raw_recipe.get("time") or 0),
        "tipo_pasto": raw_recipe.get("tipo_pasto") or raw_recipe.get("meal_type") or "Pranzo",
        "tags": _to_text_list(raw_recipe.get("tags")),
        "immagine": image,
        "descrizione": raw_recipe.get("descrizione") or RECIPE_DESCRIPTIONS.get(title, DEFAULT_DESCRIPTION),
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

    return [normalize_recipe(recipe) for recipe in DEFAULT_RECIPES]


def save_recipes(recipes):
    DATA_FILE.write_text(json.dumps(
        recipes, ensure_ascii=False, indent=2), encoding='utf-8')


def save_recipe_to_supabase(recipe):
    if not (SUPABASE_URL and SUPABASE_KEY):
        return False
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
            return True
    except (HTTPError, URLError, TimeoutError, ValueError):
        return False


def detect_image_extension(image_data):
    if image_data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if image_data.startswith(b"RIFF") and image_data[8:12] == b"WEBP":
        return "webp"
    if len(image_data) >= 12 and image_data[4:8] == b"ftyp" and image_data[8:12] in {b"avif", b"avis"}:
        return "avif"
    return ""


def save_uploaded_image(image_file, title):
    if not image_file or not image_file.filename:
        return "", None

    filename = secure_filename(image_file.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return "", "La foto deve essere JPG, PNG, WebP o AVIF."
    if not (image_file.mimetype or "").startswith("image/"):
        return "", "Il file scelto non sembra essere un’immagine valida."

    image_data = image_file.read(MAX_IMAGE_BYTES + 1)
    if len(image_data) > MAX_IMAGE_BYTES:
        return "", "La foto supera 8 MB. Riducila e riprova."
    detected_extension = detect_image_extension(image_data)
    comparable_extension = "jpg" if extension == "jpeg" else extension
    if not detected_extension or detected_extension != comparable_extension:
        return "", "Il contenuto del file non corrisponde a una foto valida."

    object_name = f"{_slugify(title)}/{uuid4().hex}.{detected_extension}"
    if SUPABASE_URL and SUPABASE_STORAGE_KEY:
        encoded_path = "/".join(quote(part, safe="")
                                for part in object_name.split("/"))
        upload_url = (
            f"{SUPABASE_URL}/storage/v1/object/"
            f"{quote(SUPABASE_STORAGE_BUCKET, safe='')}/{encoded_path}"
        )
        headers = {
            "apikey": SUPABASE_STORAGE_KEY,
            "Authorization": f"Bearer {SUPABASE_STORAGE_KEY}",
            "Content-Type": image_file.mimetype,
            "x-upsert": "false",
        }
        try:
            upload_request = urllib_request.Request(
                upload_url,
                data=image_data,
                headers=headers,
                method="POST",
            )
            with urllib_request.urlopen(upload_request, timeout=20):
                public_url = (
                    f"{SUPABASE_URL}/storage/v1/object/public/"
                    f"{quote(SUPABASE_STORAGE_BUCKET, safe='')}/{encoded_path}"
                )
                return public_url, None
        except (HTTPError, URLError, TimeoutError, ValueError):
            return "", "Non sono riuscito a caricare la foto. Controlla Supabase Storage e riprova."

    if os.environ.get("VERCEL"):
        return "", "Per caricare foto in produzione devi configurare Supabase Storage."

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    local_name = f"{_slugify(title)}-{uuid4().hex}.{extension}"
    (UPLOAD_DIR / local_name).write_bytes(image_data)
    return url_for("static", filename=f"uploads/{local_name}"), None


def delete_uploaded_image(image_url):
    public_prefix = (
        f"{SUPABASE_URL}/storage/v1/object/public/"
        f"{quote(SUPABASE_STORAGE_BUCKET, safe='')}/"
    )
    if not image_url.startswith(public_prefix) or not SUPABASE_STORAGE_KEY:
        return
    object_path = image_url.removeprefix(public_prefix)
    delete_url = (
        f"{SUPABASE_URL}/storage/v1/object/"
        f"{quote(SUPABASE_STORAGE_BUCKET, safe='')}/{object_path}"
    )
    headers = {
        "apikey": SUPABASE_STORAGE_KEY,
        "Authorization": f"Bearer {SUPABASE_STORAGE_KEY}",
    }
    try:
        delete_request = urllib_request.Request(
            delete_url, headers=headers, method="DELETE")
        with urllib_request.urlopen(delete_request, timeout=10):
            pass
    except (HTTPError, URLError, TimeoutError, ValueError):
        pass


def persist_recipe(recipe, recipes):
    if SUPABASE_URL and SUPABASE_KEY:
        return save_recipe_to_supabase(recipe)
    if os.environ.get("VERCEL"):
        return False
    recipes.append(recipe)
    save_recipes(recipes)
    return True


recipes = load_recipes()


@app.errorhandler(RequestEntityTooLarge)
def handle_oversized_upload(error):
    return render_template(
        "add_recipe.html",
        message="La foto è troppo grande. Il limite massimo è 8 MB.",
        success=False,
        form=MultiDict(),
    ), 413


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


def build_page(filtered_recipes, all_recipes, query, difficulty, max_time, meal_type, tag_filter):
    featured = all_recipes[date.today().toordinal() %
                           len(all_recipes)] if all_recipes else None
    return render_template(
        "index.html",
        recipes=filtered_recipes,
        featured=featured,
        query=query,
        difficulty=difficulty,
        max_time=max_time,
        meal_type=meal_type,
        tag_filter=tag_filter,
    )


@app.route('/ricetta/<slug>', methods=['GET'])
def recipe_detail(slug):
    recipes = load_recipes()
    recipe = next((item for item in recipes if _slugify(
        item['titolo']) == slug.lower()), None)
    if not recipe:
        return "Ricetta non trovata", 404
    steps = [
        step.strip()
        for step in re.split(r"(?<=[.!?])\s+", recipe["istruzioni"])
        if step.strip()
    ]
    recipe_tags = set(recipe.get("tags", []))
    related = sorted(
        (item for item in recipes if item["titolo"] != recipe["titolo"]),
        key=lambda item: len(recipe_tags.intersection(item.get("tags", []))),
        reverse=True,
    )[:3]
    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        steps=steps,
        related=related,
    )


@app.route('/suggeriscimi', methods=['GET'])
def suggest_recipe():
    recipes = load_recipes()
    mood = request.args.get('mood', 'sorpresa').strip().lower()
    if mood == 'veloce':
        candidates = [
            recipe for recipe in recipes if recipe['tempo_minuti'] <= 30]
    elif mood in {'pesce', 'carne', 'pasta', 'comfort'}:
        candidates = [
            recipe for recipe in recipes
            if mood in " ".join(recipe.get('tags', [])).lower()
            or mood in recipe['titolo'].lower()
        ]
    else:
        candidates = recipes
    choice = random.choice(candidates or recipes)
    return redirect(url_for('recipe_detail', slug=_slugify(choice['titolo'])))


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
                image_url, image_error = save_uploaded_image(
                    request.files.get('recipe_image'),
                    title,
                )
                if image_error:
                    return render_template(
                        "add_recipe.html",
                        message=image_error,
                        success=False,
                        form=request.form,
                    )
                recipe = {
                    'titolo': title,
                    'ingredienti': ingredients,
                    'istruzioni': instructions,
                    'difficolta': difficulty,
                    'tempo_minuti': int(time),
                    'tipo_pasto': meal_type,
                    'tags': _to_text_list(tags),
                    'immagine': image_url,
                }
                if persist_recipe(recipe, recipes):
                    return redirect(url_for('recipe_detail', slug=_slugify(title)))
                delete_uploaded_image(image_url)
                message = 'Non sono riuscito a salvare la ricetta. Controlla la configurazione Supabase.'
                success = False

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

    return build_page(
        filtered_recipes,
        recipes,
        query,
        difficulty,
        max_time,
        meal_type,
        tag_filter,
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
