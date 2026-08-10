from flask import Flask, request
from html import escape
import json
import os
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "recipes.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "cambiaquesta")

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


def load_recipes():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return [dict(recipe) for recipe in DEFAULT_RECIPES]


def save_recipes(recipes):
    DATA_FILE.write_text(json.dumps(
        recipes, ensure_ascii=False, indent=2), encoding='utf-8')


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
    cards = []
    if filtered_recipes:
        for recipe in filtered_recipes:
            tags_html = "".join(
                f"<span class='tag'>{escape(tag.strip())}</span>"
                for tag in recipe["tags"].split(",")
                if tag.strip()
            )
            cards.append(f"""
            <article class='card'>
                <div class='card-top'>
                    <h3>{escape(recipe['titolo'])}</h3>
                    <span class='pill'>{escape(recipe['difficolta'])}</span>
                </div>
                <p><strong>Tempo:</strong> {recipe['tempo_minuti']} minuti</p>
                <p><strong>Pasto:</strong> {escape(recipe['tipo_pasto'])}</p>
                <p><strong>Ingredienti:</strong> {escape(recipe['ingredienti'])}</p>
                <p><strong>Procedimento:</strong> {escape(recipe['istruzioni'])}</p>
                <div class='tags'>{tags_html}</div>
            </article>
            """)
    else:
        cards.append("<p class='empty'>Nessuna ricetta trovata.</p>")

    message_html = ""
    if message:
        message_html = f"<div class='message {'success' if success else 'error'}'>{escape(message)}</div>"

    return f"""<!doctype html>
<html lang='it'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Ricettario italiano</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #f7f7f2; color: #222; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    header {{ background: linear-gradient(135deg, #2e7d32, #66bb6a); color: white; padding: 24px; border-radius: 12px; margin-bottom: 20px; }}
    h1, h2 {{ margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    .panel {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
    form {{ display: grid; gap: 10px; }}
    input, select, textarea, button {{ padding: 10px; border: 1px solid #ccc; border-radius: 8px; font-size: 14px; }}
    button {{ background: #2e7d32; color: white; border: none; cursor: pointer; }}
    .cards {{ display: grid; gap: 14px; margin-top: 20px; }}
    .card {{ background: white; padding: 16px; border-radius: 12px; border: 1px solid #ddd; }}
    .card-top {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
    .pill {{ background: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 999px; font-size: 12px; }}
    .tag {{ display: inline-block; margin-right: 6px; margin-top: 6px; background: #f1f1f1; padding: 4px 8px; border-radius: 999px; font-size: 12px; }}
    .message {{ padding: 12px; border-radius: 8px; margin-bottom: 12px; }}
    .success {{ background: #e8f5e9; color: #2e7d32; }}
    .error {{ background: #ffebee; color: #c62828; }}
    .empty {{ color: #777; }}
    .small {{ color: #666; font-size: 13px; }}
    @media (max-width: 800px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class='container'>
    <header>
      <h1>Ricettario italiano</h1>
      <p>Un piccolo POC per cercare ricette facilmente, filtrare per ingrediente, difficoltà, tempo, tipo di pasto e tag, e aggiungere nuove ricette in modo rapido.</p>
      <p class='small'>Le ricette vengono caricate da un file locale in questa versione demo.</p>
    </header>

    {message_html}

    <div class='grid'>
      <section class='panel'>
        <h2>Cerca ricette</h2>
        <form method='get'>
          <input type='text' name='q' value='{escape(query)}' placeholder='Cerca per ingrediente, nome o tag'>
          <select name='difficulty'>
            <option value=''>Difficoltà</option>
            <option value='Facile' {'selected' if difficulty == 'Facile' else ''}>Facile</option>
            <option value='Media' {'selected' if difficulty == 'Media' else ''}>Media</option>
            <option value='Difficile' {'selected' if difficulty == 'Difficile' else ''}>Difficile</option>
          </select>
          <select name='max_time'>
            <option value=''>Tempo massimo</option>
            <option value='15' {'selected' if max_time == '15' else ''}>Fino a 15 minuti</option>
            <option value='30' {'selected' if max_time == '30' else ''}>Fino a 30 minuti</option>
            <option value='60' {'selected' if max_time == '60' else ''}>Fino a 60 minuti</option>
          </select>
          <select name='meal_type'>
            <option value=''>Tipo pasto</option>
            <option value='Colazione' {'selected' if meal_type == 'Colazione' else ''}>Colazione</option>
            <option value='Pranzo' {'selected' if meal_type == 'Pranzo' else ''}>Pranzo</option>
            <option value='Cena' {'selected' if meal_type == 'Cena' else ''}>Cena</option>
            <option value='Spuntino' {'selected' if meal_type == 'Spuntino' else ''}>Spuntino</option>
          </select>
          <input type='text' name='tag' value='{escape(tag_filter)}' placeholder='Tag: veloce, famiglia'>
          <button type='submit'>Cerca</button>
        </form>
      </section>

      <section class='panel'>
        <h2>Aggiungi ricetta (admin)</h2>
        <form method='post'>
          <input type='text' name='title' placeholder='Titolo ricetta' required>
          <textarea name='ingredients' rows='3' placeholder='Ingredienti' required></textarea>
          <textarea name='instructions' rows='4' placeholder='Procedimento' required></textarea>
          <select name='difficulty_add'>
            <option value='Facile'>Facile</option>
            <option value='Media'>Media</option>
            <option value='Difficile'>Difficile</option>
          </select>
          <input type='number' name='time' min='1' placeholder='Tempo in minuti' required>
          <select name='meal_type_add'>
            <option value='Colazione'>Colazione</option>
            <option value='Pranzo'>Pranzo</option>
            <option value='Cena'>Cena</option>
            <option value='Spuntino'>Spuntino</option>
          </select>
          <input type='text' name='tags' placeholder='Tag separati da virgola'>
          <input type='password' name='password' placeholder='Password admin' required>
          <button type='submit'>Salva ricetta</button>
        </form>
      </section>
    </div>

    <section class='cards'>
      {''.join(cards)}
    </section>
  </div>
</body>
</html>
"""


@app.route('/', methods=['GET', 'POST'])
def home():
    global recipes
    message = None
    success = True

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
                recipes.append({
                    'titolo': title,
                    'ingredienti': ingredients,
                    'istruzioni': instructions,
                    'difficolta': difficulty,
                    'tempo_minuti': int(time),
                    'tipo_pasto': meal_type,
                    'tags': tags
                })
                save_recipes(recipes)
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
