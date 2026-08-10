import app as app_module
import json

import pytest

app = app_module.app
load_recipes = app_module.load_recipes


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_home_page_renders(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Tavola' in response.data


def test_can_add_recipe_with_structured_ingredients(client, tmp_path, monkeypatch):
    data_file = tmp_path / 'recipes.json'
    data_file.write_text(json.dumps(load_recipes()), encoding='utf-8')
    monkeypatch.setattr(app_module, 'DATA_FILE', data_file)
    monkeypatch.setattr(app_module, 'SUPABASE_URL', '')

    response = client.post('/aggiungi', data={
        'title': 'Pasta della prova',
        'ingredient_quantity[]': ['200 g', '150 g'],
        'ingredient_name[]': ['pasta', 'pomodoro'],
        'instructions': 'Cuoci tutto',
        'difficulty_add': 'Facile',
        'time': '15',
        'meal_type_add': 'Pranzo',
        'tags': 'veloce',
        'password': 'cambiaquesta'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Pasta della prova' in response.data
    saved_recipe = json.loads(data_file.read_text(encoding='utf-8'))[-1]
    assert saved_recipe['ingredienti'] == [
        {'name': 'pasta', 'quantity': '200 g'},
        {'name': 'pomodoro', 'quantity': '150 g'},
    ]


def test_seed_contains_only_curated_recipes():
    recipes = load_recipes()
    assert len(recipes) == 5
    assert {recipe['titolo'] for recipe in recipes} == {
        'Biscotti della longevità',
        'Pasta cremosa al branzino e broccoli',
        'Rigatoni al ragù di coniglio',
        'Spaghetti integrali all’orata, pomodorini e crema di carote',
        'Polpette di carne e spinaci'
    }


def test_recipes_use_array_fields_for_ingredients_and_tags():
    recipes = load_recipes()
    assert any(isinstance(recipe['ingredienti'], list) for recipe in recipes)
    assert any(isinstance(recipe['tags'], list) for recipe in recipes)
