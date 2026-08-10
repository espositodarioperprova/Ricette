import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_home_page_renders(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Ricettario italiano' in response.data


def test_can_add_recipe_with_admin_password(client):
    response = client.post('/', data={
        'title': 'Pasta test',
        'ingredients': 'pasta, pomodoro',
        'instructions': 'Cuoci tutto',
        'difficulty_add': 'Facile',
        'time': '15',
        'meal_type_add': 'Pranzo',
        'tags': 'test, veloce',
        'password': 'cambiaquesta'
    })
    assert response.status_code == 200
    assert b'Ricetta aggiunta con successo.' in response.data
