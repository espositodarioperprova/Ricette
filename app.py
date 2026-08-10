from flask import Flask, flash, redirect, render_template, request, session, url_for
from hmac import compare_digest
import json
import os
import random
import re
import unicodedata
from datetime import date
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

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cambiaquesta")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or ADMIN_PASSWORD
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("VERCEL"))
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STORAGE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE", "recipes")
SUPABASE_STORAGE_BUCKET = os.environ.get(
    "SUPABASE_STORAGE_BUCKET", "recipe-images")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "avif"}


class RecipeStoreError(RuntimeError):
    pass


def normalize_recipe(raw_recipe):
    title = raw_recipe.get("titolo") or raw_recipe.get("title") or ""
    image = str(raw_recipe.get("immagine") or "").strip()
    if "images.unsplash.com" in image:
        image = ""
    return {
        "id": raw_recipe.get("id"),
        "titolo": title,
        "ingredienti": _to_ingredient_map(raw_recipe.get("ingredienti") or raw_recipe.get("ingredients")),
        "istruzioni": raw_recipe.get("istruzioni") or raw_recipe.get("instructions") or "",
        "difficolta": raw_recipe.get("difficolta") or raw_recipe.get("difficulty") or "Facile",
        "tempo_minuti": int(raw_recipe.get("tempo_minuti") or raw_recipe.get("time") or 0),
        "tipo_pasto": raw_recipe.get("tipo_pasto") or raw_recipe.get("meal_type") or "Pranzo",
        "tags": _to_text_list(raw_recipe.get("tags")),
        "immagine": image,
        "descrizione": raw_recipe.get("descrizione") or "",
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
    if not (SUPABASE_URL and SUPABASE_KEY):
        raise RecipeStoreError("Supabase non è configurato.")
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
    try:
        with urllib_request.urlopen(request, timeout=10) as response:
            data = json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise RecipeStoreError(
            "Non è stato possibile leggere le ricette da Supabase."
        ) from error
    if not isinstance(data, list):
        raise RecipeStoreError(
            "Supabase ha restituito una risposta non valida.")
    return [
        recipe
        for item in data
        if is_valid_recipe(recipe := normalize_recipe(item))
    ]


def save_recipe_to_supabase(recipe):
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        return False
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
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


def update_recipe_image(recipe_id, image_url):
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        return False
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    request_url = (
        f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
        f"?id=eq.{quote(str(recipe_id), safe='')}"
    )
    try:
        update_request = urllib_request.Request(
            request_url,
            data=json.dumps({"immagine": image_url}).encode("utf-8"),
            headers=headers,
            method="PATCH",
        )
        with urllib_request.urlopen(update_request, timeout=10):
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

    return "", "Per caricare foto devi configurare Supabase Storage."


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


def persist_recipe(recipe):
    return save_recipe_to_supabase(recipe)


@app.errorhandler(RequestEntityTooLarge)
def handle_oversized_upload(error):
    if request.endpoint == "update_recipe_photo":
        flash("La foto è troppo grande. Il limite massimo è 8 MB.", "error")
        return redirect(url_for("recipe_detail", slug=request.view_args["slug"]))
    return render_template(
        "add_recipe.html",
        message="La foto è troppo grande. Il limite massimo è 8 MB.",
        success=False,
        form=MultiDict(),
    ), 413


@app.errorhandler(RecipeStoreError)
def handle_recipe_store_error(error):
    return (
        "Tavola non riesce a collegarsi a Supabase. Controlla la configurazione del servizio.",
        503,
    )


@app.context_processor
def inject_admin_state():
    return {"is_admin": session.get("is_admin", False)}


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


@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    next_url = request.values.get('next', '').strip()
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('home')
    if request.method == 'POST':
        password = request.form.get('password', '')
        if compare_digest(password, ADMIN_PASSWORD):
            session['is_admin'] = True
            return redirect(next_url)
        return render_template(
            'admin_login.html',
            message='Password non corretta.',
            next_url=next_url,
        ), 401
    return render_template('admin_login.html', message=None, next_url=next_url)


@app.post('/admin/esci')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('home'))


@app.post('/ricetta/<slug>/foto')
def update_recipe_photo(slug):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login', next=url_for('recipe_detail', slug=slug)))

    recipes = load_recipes()
    recipe = next((item for item in recipes if _slugify(
        item['titolo']) == slug.lower()), None)
    if not recipe:
        return "Ricetta non trovata", 404

    image_file = request.files.get('recipe_image')
    if not image_file or not image_file.filename:
        flash('Scegli una foto da caricare.', 'error')
        return redirect(url_for('recipe_detail', slug=slug))

    image_url, image_error = save_uploaded_image(image_file, recipe['titolo'])
    if image_error:
        flash(image_error, 'error')
        return redirect(url_for('recipe_detail', slug=slug))
    if not recipe.get('id') or not update_recipe_image(recipe['id'], image_url):
        delete_uploaded_image(image_url)
        flash('La foto è stata caricata, ma non associata alla ricetta.', 'error')
        return redirect(url_for('recipe_detail', slug=slug))

    previous_image = recipe.get('immagine', '')
    if previous_image and previous_image != image_url:
        delete_uploaded_image(previous_image)
    flash('Foto aggiornata.', 'success')
    return redirect(url_for('recipe_detail', slug=slug))


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
            description = request.form.get('description', '').strip()
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

            if not title or not description or not ingredients or not instructions or not time:
                message = 'Compila titolo, descrizione, ingredienti, procedimento e tempo.'
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
                    'descrizione': description,
                    'ingredienti': ingredients,
                    'istruzioni': instructions,
                    'difficolta': difficulty,
                    'tempo_minuti': int(time),
                    'tipo_pasto': meal_type,
                    'tags': _to_text_list(tags),
                    'immagine': image_url,
                }
                if persist_recipe(recipe):
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
