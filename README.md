# Tavola

Tavola è un ricettario italiano pensato per decidere cosa mangiare e seguire la preparazione senza distrazioni. Permette di:
- cercare ricette per ingrediente, difficoltà, tempo, tag e tipo di pasto
- ottenere un suggerimento quando non sai cosa cucinare
- aggiungere ricette strutturate tramite un editor protetto da password
- caricare, facoltativamente, una foto vera del piatto
- usare checklist, avanzamento e modalità cucina nella scheda ricetta

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

1. Esegui `supabase_seed.sql` nel SQL Editor di Supabase. Lo script normalizza i campi strutturati, inserisce le cinque ricette e crea il bucket pubblico `recipe-images` con limite di 8 MB.
2. Crea un progetto Vercel collegato a questa cartella.
3. Imposta le variabili d’ambiente:
   - `ADMIN_PASSWORD`: password per aggiungere ricette
   - `SUPABASE_URL`: URL del progetto Supabase
   - `SUPABASE_ANON_KEY`: chiave anon usata per leggere e salvare le ricette
   - `SUPABASE_SERVICE_ROLE_KEY`: chiave server privata usata per caricare le foto
   - `SUPABASE_TABLE`: nome della tabella, facoltativo; il valore predefinito è `recipes`
   - `SUPABASE_STORAGE_BUCKET`: nome del bucket, facoltativo; il valore predefinito è `recipe-images`
4. Fai un nuovo deploy dopo aver salvato le variabili.

`SUPABASE_SERVICE_ROLE_KEY` deve restare esclusivamente nelle variabili server di Vercel e non deve mai essere inserita nel frontend o nel repository. In sviluppo, senza Supabase configurato, le ricette vengono salvate in `recipes.json` e le foto in `static/uploads`.
