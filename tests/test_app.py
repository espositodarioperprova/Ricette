import app as app_module

import pytest

app = app_module.app

SAMPLE_RECIPES = [
    {
        "titolo": "Bocconcini di tacchino in crema",
        "ingredienti": [
            {"name": "bocconcini di tacchino", "quantity": "500 g"},
            {"name": "acqua", "quantity": "1 bicchiere abbondante"},
        ],
        "istruzioni": "Cuoci lentamente. Completa con il lievito nutrizionale.",
        "difficolta": "Facile",
        "tempo_minuti": 70,
        "tipo_pasto": "Cena",
        "tags": ["carne", "cremosa"],
        "immagine": "",
        "descrizione": "Tacchino tenero e cremoso.",
    },
    {
        "titolo": "Carciofi al gratin",
        "ingredienti": [
            {"name": "cuori di carciofo surgelati", "quantity": "250 g"},
        ],
        "istruzioni": "Cuoci dolcemente. Completa con il lievito nutrizionale.",
        "difficolta": "Facile",
        "tempo_minuti": 40,
        "tipo_pasto": "Cena",
        "tags": ["contorno", "verdure"],
        "immagine": "",
        "descrizione": "Carciofi teneri e dorati.",
    },
]


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client


def test_home_page_renders_supabase_recipes(client, monkeypatch):
    monkeypatch.setattr(app_module, 'load_recipes', lambda: SAMPLE_RECIPES)

    response = client.get('/')

    assert response.status_code == 200
    assert b'Tavola' in response.data
    assert b'Bocconcini di tacchino in crema' in response.data
    assert b'Carciofi al gratin' in response.data


def test_home_returns_503_without_supabase(client, monkeypatch):
    monkeypatch.setattr(app_module, 'SUPABASE_URL', '')
    monkeypatch.setattr(app_module, 'SUPABASE_KEY', '')

    response = client.get('/')

    assert response.status_code == 503
    assert b'Supabase' in response.data


def test_can_add_recipe_with_structured_ingredients(client, monkeypatch):
    saved = []
    monkeypatch.setattr(app_module, 'load_recipes', lambda: SAMPLE_RECIPES)
    monkeypatch.setattr(
        app_module,
        'persist_recipe',
        lambda recipe: saved.append(recipe) or True,
    )

    response = client.post('/aggiungi', data={
        'title': 'Pasta della prova',
        'description': 'Una pasta creata per verificare il salvataggio.',
        'ingredient_quantity[]': ['200 g', '150 g'],
        'ingredient_name[]': ['pasta', 'pomodoro'],
        'instructions': 'Cuoci tutto',
        'difficulty_add': 'Facile',
        'time': '15',
        'meal_type_add': 'Pranzo',
        'tags': 'veloce',
        'password': 'cambiaquesta'
    })

    assert response.status_code == 302
    assert saved[0]['ingredienti'] == [
        {'name': 'pasta', 'quantity': '200 g'},
        {'name': 'pomodoro', 'quantity': '150 g'},
    ]
    assert saved[0]['descrizione'] == 'Una pasta creata per verificare il salvataggio.'


def test_normalize_recipe_uses_only_supabase_fields():
    recipe = app_module.normalize_recipe({
        'titolo': 'Ricetta remota',
        'ingredienti': [{'name': 'ingrediente', 'quantity': '1'}],
        'istruzioni': 'Procedimento remoto.',
        'difficolta': 'Media',
        'tempo_minuti': 25,
        'tipo_pasto': 'Cena',
        'tags': ['remota'],
        'immagine': '',
        'descrizione': 'Descrizione modificata direttamente in Supabase.',
    })

    assert recipe['descrizione'] == 'Descrizione modificata direttamente in Supabase.'
    assert recipe['ingredienti'] == [{'name': 'ingrediente', 'quantity': '1'}]
