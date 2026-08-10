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

1. Esegui `supabase_seed.sql` nel SQL Editor di Supabase. Lo script configura in modo non distruttivo la tabella `recipes` e il bucket pubblico `recipe-images` con limite di 8 MB. Non inserisce né sostituisce ricette.
2. Crea un progetto Vercel collegato a questa cartella.
3. Imposta le variabili d’ambiente:
   - `ADMIN_PASSWORD`: password per aggiungere ricette
   - `SUPABASE_URL`: URL del progetto Supabase
   - `SUPABASE_ANON_KEY`: chiave anon usata esclusivamente per leggere le ricette
   - `SUPABASE_SERVICE_ROLE_KEY`: chiave server privata usata per salvare ricette, caricare foto e associarle ai record esistenti
   - `SUPABASE_TABLE`: nome della tabella, facoltativo; il valore predefinito è `recipes`
   - `SUPABASE_STORAGE_BUCKET`: nome del bucket, facoltativo; il valore predefinito è `recipe-images`
   - `SECRET_KEY`: chiave casuale usata per firmare la sessione admin; se assente viene usata `ADMIN_PASSWORD`
4. Fai un nuovo deploy dopo aver salvato le variabili.

`SUPABASE_SERVICE_ROLE_KEY` deve restare esclusivamente nelle variabili server di Vercel e non deve mai essere inserita nel frontend o nel repository. Supabase è l'unica fonte delle ricette in ogni ambiente: senza `SUPABASE_URL` e una chiave valida, Tavola restituisce un errore `503` invece di mostrare dati locali obsoleti.

Le immagini caricate dall'app sono limitate a 4 MB per restare sotto il limite di 4,5 MB delle richieste Vercel. Il bucket mantiene un limite superiore di sicurezza di 8 MB.
