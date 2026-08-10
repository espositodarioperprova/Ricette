begin;

do $$
declare
  ingredient_type text;
  tag_type text;
begin
  select udt_name into ingredient_type
  from information_schema.columns
  where table_schema = 'public'
    and table_name = 'recipes'
    and column_name = 'ingredienti';

  if ingredient_type = '_text' then
    alter table public.recipes add column ingredienti_new jsonb not null default '[]'::jsonb;
    update public.recipes recipe
    set ingredienti_new = coalesce(
      (
        select jsonb_agg(jsonb_build_object('name', ingredient, 'quantity', ''))
        from unnest(recipe.ingredienti) as ingredient
      ),
      '[]'::jsonb
    );
    alter table public.recipes drop column ingredienti;
    alter table public.recipes rename column ingredienti_new to ingredienti;
  elsif ingredient_type = 'text' then
    alter table public.recipes add column ingredienti_new jsonb not null default '[]'::jsonb;
    update public.recipes recipe
    set ingredienti_new = coalesce(
      (
        select jsonb_agg(jsonb_build_object('name', trim(ingredient), 'quantity', ''))
        from unnest(string_to_array(recipe.ingredienti, ',')) as ingredient
        where trim(ingredient) <> ''
      ),
      '[]'::jsonb
    );
    alter table public.recipes drop column ingredienti;
    alter table public.recipes rename column ingredienti_new to ingredienti;
  elsif ingredient_type not in ('json', 'jsonb') then
    raise exception 'Tipo non supportato per recipes.ingredienti: %', ingredient_type;
  end if;

  select udt_name into tag_type
  from information_schema.columns
  where table_schema = 'public'
    and table_name = 'recipes'
    and column_name = 'tags';

  if tag_type = 'text' then
    alter table public.recipes add column tags_new text[] not null default '{}';
    update public.recipes
    set tags_new = string_to_array(tags, ',');
    alter table public.recipes drop column tags;
    alter table public.recipes rename column tags_new to tags;
  elsif tag_type = 'jsonb' then
    alter table public.recipes add column tags_new text[] not null default '{}';
    update public.recipes recipe
    set tags_new = coalesce(
      (
        select array_agg(tag)
        from jsonb_array_elements_text(recipe.tags) as tag
      ),
      '{}'
    );
    alter table public.recipes drop column tags;
    alter table public.recipes rename column tags_new to tags;
  elsif tag_type <> '_text' then
    raise exception 'Tipo non supportato per recipes.tags: %', tag_type;
  end if;
end $$;

alter table public.recipes add column if not exists immagine text;

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'recipe-images',
  'recipe-images',
  true,
  8388608,
  array['image/jpeg', 'image/png', 'image/webp', 'image/avif']
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

delete from public.recipes
where titolo = any(array[
  'Biscotti della longevità',
  'Pasta cremosa al branzino e broccoli',
  'Rigatoni al ragù di coniglio',
  'Spaghetti integrali all’orata, pomodorini e crema di carote',
  'Polpette di carne e spinaci'
]);

insert into public.recipes (
  titolo,
  ingredienti,
  istruzioni,
  difficolta,
  tempo_minuti,
  tipo_pasto,
  tags,
  immagine
)
values
  (
    'Biscotti della longevità',
    $json$[
      {"name":"100 g di okara di macadamia","quantity":""},
      {"name":"1 cucchiaio abbondante di olio evo","quantity":""},
      {"name":"1 bustina di vanillina","quantity":""},
      {"name":"3 datteri","quantity":""},
      {"name":"1 cucchiaio di semi di chia","quantity":""},
      {"name":"2 cucchiaini di cacao","quantity":""},
      {"name":"1 uovo","quantity":""},
      {"name":"2 cucchiai o più di fiocchi d'avena","quantity":""}
    ]$json$::jsonb,
    $text$Frulla l'okara di macadamia con l'olio, la vanillina, i datteri, i semi di chia, il cacao e l'uovo fino a ottenere un impasto omogeneo. Aggiungi gli fiocchi d'avena fino a raggiungere una consistenza abbastanza soda da poter formare dei biscotti. Forma delle palline o piccoli biscotti, disponili su una teglia e cuoci a 180 °C per 12-15 minuti, fino a dorare leggermente.$text$,
    'Facile',
    20,
    'Spuntino',
    array['dolce', 'snack', 'longevità'],
    null
  ),
  (
    'Pasta cremosa al branzino e broccoli',
    $json$[
      {"name":"mezzo chilo di pasta integrale","quantity":""},
      {"name":"broccoli al vapore","quantity":""},
      {"name":"sale","quantity":""},
      {"name":"1 cucchiaio di lievito nutrizionale","quantity":""},
      {"name":"acqua","quantity":""},
      {"name":"mezzo limone","quantity":""},
      {"name":"2 cucchiai di olio evo","quantity":""},
      {"name":"1 cucchiaio scarso di burro di anacardi","quantity":""},
      {"name":"250 g di filetti di branzino cotti","quantity":""},
      {"name":"1 spicchio d'aglio","quantity":""},
      {"name":"olio per cuocere il pesce","quantity":""}
    ]$json$::jsonb,
    $text$Lessa i broccoli al vapore fino a renderli morbidi, poi scolali e frullali con sale, lievito nutrizionale, acqua, mezzo limone, olio evo e il burro di anacardi fino ad ottenere una crema liscia. In una padella cuoci il branzino con un filo d'olio e uno spicchio d'aglio, poi sfilacciarlo o lasciarlo a pezzetti. Cuoci la pasta integrale, scolala al dente e condisci con la crema di broccoli. Aggiungi il branzino a cima e servi subito.$text$,
    'Media',
    35,
    'Pranzo',
    array['pasta', 'pesce', 'cremosa'],
    null
  ),
  (
    'Rigatoni al ragù di coniglio',
    $json$[
      {"name":"1 coscia di coniglio già cotta e scarnificata","quantity":""},
      {"name":"200 g di rigatoni integrali","quantity":""},
      {"name":"1 cipolla piccola","quantity":""},
      {"name":"1 carota piccola","quantity":""},
      {"name":"mezzo cucchiaino scarso di curcuma","quantity":""},
      {"name":"polvere d'aglio","quantity":""},
      {"name":"mezzo dado","quantity":""},
      {"name":"sale","quantity":""},
      {"name":"olio","quantity":""},
      {"name":"1 bicchiere d'acqua","quantity":""}
    ]$json$::jsonb,
    $text$Fai soffriggere la cipolla e la carota a cubetti piccoli in un filo d'olio. Aggiungi il coniglio già cotto e scarnificato, la curcuma, la polvere d'aglio, il dado e un bicchiere d'acqua. Cuoci a fuoco lento per circa 50 minuti, mescolando di tanto in tanto fino a ottenere un ragù saporito. Nel frattempo cuoci i rigatoni integrali. Scola la pasta, condisci con il ragù e servi caldo.$text$,
    'Media',
    60,
    'Pranzo',
    array['pasta', 'carne', 'comfort food'],
    null
  ),
  (
    'Spaghetti integrali all’orata, pomodorini e crema di carote',
    $json$[
      {"name":"500 g di spaghetti integrali","quantity":""},
      {"name":"250 g di filetti d'orata","quantity":""},
      {"name":"400 g di pomodorini","quantity":""},
      {"name":"2 carote molto ben lessate","quantity":""},
      {"name":"acqua","quantity":""},
      {"name":"olio evo","quantity":""},
      {"name":"sale","quantity":""},
      {"name":"aglio","quantity":""},
      {"name":"poco dado in polvere","quantity":""},
      {"name":"2-3 cucchiaioni pieni di lievito nutrizionale","quantity":""}
    ]$json$::jsonb,
    $text$Lessa le carote fino a renderle molto morbide, poi scolale e frullale con acqua, olio, sale, aglio, un po' di dado in polvere e il lievito nutrizionale fino a ottenere una crema liscia e salsosa. In una padella cuoci i pomodorini con un filo d'olio e uno spicchio d'aglio, quindi aggiungi l'orata e cuocila delicatamente. Nel frattempo cuoci gli spaghetti integrali al dente, scolali e condisci con il sughetto di pomodorini e il pesce. Servi con la crema di carote a fianco o sopra, per un piatto ricco e molto saporito.$text$,
    'Media',
    35,
    'Pranzo',
    array['pasta', 'pesce', 'cremosa', 'integrale'],
    null
  ),
  (
    'Polpette di carne e spinaci',
    $json$[
      {"name":"500 g di macinato misto","quantity":""},
      {"name":"250 g di spinaci surgelati","quantity":""},
      {"name":"2 uova","quantity":""},
      {"name":"pangrattato","quantity":""},
      {"name":"3 cucchiai di latte","quantity":""},
      {"name":"aglio","quantity":""},
      {"name":"sale","quantity":""},
      {"name":"curcuma","quantity":""}
    ]$json$::jsonb,
    $text$Lessa gli spinaci surgelati, strizzali bene e tritali grossolanamente. In una ciotola mescola il macinato, gli spinaci, le uova, il pangrattato, il latte, l'aglio, il sale e un pizzico di curcuma fino a ottenere un composto compatto. Forma le polpette, sistemale su una teglia e cuoci in forno a 180-200 °C per 20-25 minuti, fino a dorare bene.$text$,
    'Media',
    30,
    'Cena',
    array['carne', 'comfort', 'forno'],
    null
  );

commit;

select titolo, tipo_pasto, tempo_minuti
from public.recipes
order by titolo;