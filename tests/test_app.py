import app as app_module
from io import BytesIO
import json
from urllib.error import HTTPError

import pytest
from werkzeug.datastructures import FileStorage

app = app_module.app

SAMPLE_RECIPES = [
    {
        "id": 1,
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
        "id": 2,
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
def client(monkeypatch):
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-session-secret'
    monkeypatch.setattr(app_module, 'ADMIN_PASSWORD', 'cambiaquesta')
    monkeypatch.setattr(app_module, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(app_module, 'SUPABASE_SERVICE_ROLE_KEY', 'service-key')
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


def test_photo_controls_are_hidden_until_admin_login(client, monkeypatch):
    monkeypatch.setattr(app_module, 'load_recipes', lambda: SAMPLE_RECIPES)
    recipe_url = '/ricetta/bocconcini-di-tacchino-in-crema'

    public_response = client.get(recipe_url)
    login_response = client.post('/admin', data={
        'password': 'cambiaquesta',
        'next': recipe_url,
    })
    admin_response = client.get(recipe_url)

    assert b'Gestione ricetta' not in public_response.data
    assert login_response.status_code == 302
    assert login_response.headers['Location'].endswith(recipe_url)
    assert b'Gestione ricetta' in admin_response.data
    assert b'Aggiungi una fotografia' in admin_response.data


def test_admin_can_update_existing_recipe_photo(client, monkeypatch):
    updated = []
    monkeypatch.setattr(app_module, 'load_recipes', lambda: SAMPLE_RECIPES)
    monkeypatch.setattr(
        app_module,
        'save_uploaded_image',
        lambda image, title: ('https://example.com/recipe.png', None),
    )
    monkeypatch.setattr(
        app_module,
        'update_recipe_image',
        lambda title, image_url: updated.append((title, image_url)) or True,
    )
    with client.session_transaction() as admin_session:
        admin_session['is_admin'] = True

    response = client.post(
        '/ricetta/bocconcini-di-tacchino-in-crema/foto',
        data={'recipe_image': (BytesIO(b'photo'), 'recipe.png')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 302
    assert updated == [(
        1,
        'https://example.com/recipe.png',
    )]


def test_photo_update_requires_admin_session(client, monkeypatch):
    monkeypatch.setattr(app_module, 'load_recipes', lambda: SAMPLE_RECIPES)

    response = client.post(
        '/ricetta/bocconcini-di-tacchino-in-crema/foto',
        data={'recipe_image': (BytesIO(b'photo'), 'recipe.png')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 302
    assert '/admin?' in response.headers['Location']


def test_update_recipe_image_requires_exact_returned_row(monkeypatch):
    requests = []
    monkeypatch.setattr(app_module, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(app_module, 'SUPABASE_SERVICE_ROLE_KEY', 'service-key')

    def successful_urlopen(request, timeout):
        requests.append(request)
        return BytesIO(json.dumps([{
            'id': 7,
            'immagine': 'https://example.com/photo.png',
        }]).encode())

    monkeypatch.setattr(app_module.urllib_request, 'urlopen', successful_urlopen)

    assert app_module.update_recipe_image(7, 'https://example.com/photo.png') is True
    assert requests[0].method == 'PATCH'
    assert requests[0].get_header('Prefer') == 'return=representation'
    assert requests[0].full_url.endswith('/recipes?id=eq.7')

    monkeypatch.setattr(
        app_module.urllib_request,
        'urlopen',
        lambda request, timeout: BytesIO(b'[]'),
    )
    assert app_module.update_recipe_image(7, 'https://example.com/photo.png') is False

    monkeypatch.setattr(
        app_module.urllib_request,
        'urlopen',
        lambda request, timeout: BytesIO(json.dumps([{
            'id': 8,
            'immagine': 'https://example.com/photo.png',
        }]).encode()),
    )
    assert app_module.update_recipe_image(7, 'https://example.com/photo.png') is False


def test_update_recipe_image_handles_http_error(monkeypatch):
    monkeypatch.setattr(app_module, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(app_module, 'SUPABASE_SERVICE_ROLE_KEY', 'service-key')
    monkeypatch.setattr(
        app_module.urllib_request,
        'urlopen',
        lambda request, timeout: (_ for _ in ()).throw(
            HTTPError(request.full_url, 500, 'error', None, None)
        ),
    )

    assert app_module.update_recipe_image(7, 'https://example.com/photo.png') is False


def test_failed_photo_update_deletes_only_new_upload(client, monkeypatch):
    deleted = []
    recipe_with_photo = {**SAMPLE_RECIPES[0], 'immagine': 'https://example.com/old.png'}
    monkeypatch.setattr(app_module, 'load_recipes', lambda: [recipe_with_photo])
    monkeypatch.setattr(
        app_module,
        'save_uploaded_image',
        lambda image, title: ('https://example.com/new.png', None),
    )
    monkeypatch.setattr(app_module, 'update_recipe_image', lambda recipe_id, image_url: False)
    monkeypatch.setattr(app_module, 'delete_uploaded_image', deleted.append)
    with client.session_transaction() as admin_session:
        admin_session['is_admin'] = True

    response = client.post(
        '/ricetta/bocconcini-di-tacchino-in-crema/foto',
        data={'recipe_image': (BytesIO(b'photo'), 'recipe.png')},
        content_type='multipart/form-data',
    )

    assert response.status_code == 302
    assert deleted == ['https://example.com/new.png']


def test_successful_replacement_deletes_only_previous_photo(client, monkeypatch):
    deleted = []
    recipe_with_photo = {**SAMPLE_RECIPES[0], 'immagine': 'https://example.com/old.png'}
    monkeypatch.setattr(app_module, 'load_recipes', lambda: [recipe_with_photo])
    monkeypatch.setattr(
        app_module,
        'save_uploaded_image',
        lambda image, title: ('https://example.com/new.png', None),
    )
    monkeypatch.setattr(app_module, 'update_recipe_image', lambda recipe_id, image_url: True)
    monkeypatch.setattr(app_module, 'delete_uploaded_image', deleted.append)
    with client.session_transaction() as admin_session:
        admin_session['is_admin'] = True

    client.post(
        '/ricetta/bocconcini-di-tacchino-in-crema/foto',
        data={'recipe_image': (BytesIO(b'photo'), 'recipe.png')},
        content_type='multipart/form-data',
    )

    assert deleted == ['https://example.com/old.png']


def test_upload_validation_rejects_invalid_and_oversized_files():
    invalid_file = FileStorage(
        stream=BytesIO(b'not an image'),
        filename='fake.png',
        content_type='image/png',
    )
    oversized_file = FileStorage(
        stream=BytesIO(b'\x89PNG\r\n\x1a\n' + b'0' * app_module.MAX_IMAGE_BYTES),
        filename='large.png',
        content_type='image/png',
    )

    assert 'foto valida' in app_module.save_uploaded_image(invalid_file, 'Test')[1]
    assert '4 MB' in app_module.save_uploaded_image(oversized_file, 'Test')[1]


def test_storage_upload_and_delete_use_expected_supabase_contract(monkeypatch):
    requests = []
    monkeypatch.setattr(app_module, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(app_module, 'SUPABASE_STORAGE_KEY', 'service-key')
    monkeypatch.setattr(app_module, 'SUPABASE_STORAGE_BUCKET', 'recipe-images')
    monkeypatch.setattr(app_module, 'uuid4', lambda: type('UUID', (), {'hex': 'abc123'})())

    def capture_urlopen(request, timeout):
        requests.append(request)
        return BytesIO(b'{}')

    monkeypatch.setattr(app_module.urllib_request, 'urlopen', capture_urlopen)
    image = FileStorage(
        stream=BytesIO(b'\x89PNG\r\n\x1a\ncontent'),
        filename='photo.png',
        content_type='image/png',
    )

    image_url, error = app_module.save_uploaded_image(image, 'Crêpes di okara')
    app_module.delete_uploaded_image(image_url)

    assert error is None
    assert image_url == (
        'https://example.supabase.co/storage/v1/object/public/'
        'recipe-images/crepes-di-okara/abc123.png'
    )
    assert requests[0].method == 'POST'
    assert requests[0].full_url.endswith(
        '/storage/v1/object/recipe-images/crepes-di-okara/abc123.png'
    )
    assert requests[0].get_header('Authorization') == 'Bearer service-key'
    assert requests[0].get_header('Content-type') == 'image/png'
    assert requests[1].method == 'DELETE'
    assert requests[1].full_url.endswith(
        '/storage/v1/object/recipe-images/crepes-di-okara/abc123.png'
    )


def test_admin_logout_clears_session(client):
    with client.session_transaction() as admin_session:
        admin_session['is_admin'] = True

    response = client.post('/admin/esci')

    assert response.status_code == 302
    with client.session_transaction() as admin_session:
        assert 'is_admin' not in admin_session


def test_admin_fails_closed_without_server_credentials(client, monkeypatch):
    monkeypatch.setattr(app_module, 'ADMIN_PASSWORD', '')

    response = client.post('/admin', data={
        'password': 'cambiaquesta',
        'next': '/',
    })

    assert response.status_code == 503
    assert b'non' in response.data


def test_failed_login_revokes_existing_admin_session(client):
    with client.session_transaction() as admin_session:
        admin_session['is_admin'] = True

    response = client.post('/admin', data={
        'password': 'wrong-password',
        'next': '/',
    })

    assert response.status_code == 401
    with client.session_transaction() as admin_session:
        assert 'is_admin' not in admin_session
