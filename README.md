# Ricettario POC

Questo progetto è una versione semplice e italiana di un ricettario web per:
- cercare ricette per ingrediente, difficoltà, tempo, tag e tipo di pasto
- aggiungere nuove ricette tramite un modulo admin protetto da password
- avere già alcune ricette iniziali, incluse quelle che hai scritto

## Esecuzione locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Apri http://127.0.0.1:8000

## Test

```bash
source .venv/bin/activate
pytest -q
```

## Deploy su Vercel

1. Crea un progetto Vercel collegato a questa cartella.
2. Imposta la variabile d’ambiente `ADMIN_PASSWORD` con la password desiderata.
3. Fai il deploy.

Nota: in questa versione demo le ricette vengono salvate in un file locale. Per un rilascio più robusto, il prossimo passo naturale è aggiungere un database o Vercel KV.
