# cvgruplac-json

[![CI](https://github.com/restrepo/cvgruplac-json/actions/workflows/ci.yml/badge.svg)](https://github.com/restrepo/cvgruplac-json/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cvgruplac-json.svg)](https://pypi.org/project/cvgruplac-json/)
[![Python](https://img.shields.io/pypi/pyversions/cvgruplac-json.svg)](https://pypi.org/project/cvgruplac-json/)

Une los JSON de [cvlac-json](https://github.com/restrepo/cvlac-json) (el CvLAC de una persona) y de
[gruplac-json](https://github.com/restrepo/gruplac-json) (el GrupLAC de un grupo) de Minciencias: cada producto de
los dos recibe un `id` y una lista `scrapping_ids` con sus ids en una y otra fuente, así que un producto del grupo
apunta al mismo producto en el CV de cada integrante que lo firmó, y al revés.

No descarga nada ni llama a ninguna API: lee los JSON que ya escribieron los dos paquetes y escribe copias unidas,
sin tocar los originales. Solo usa la biblioteca estándar.

## Instalación

```bash
pip install cvgruplac-json
```

## Uso

```bash
cvgruplac-json --cvlac cvlac/ --gruplac gruplac/ --out unidos/
cvgruplac-json --cvlac cvlac_udea/ cvlac_colombia/json/ --gruplac gruplac/json/ --out unidos/ --workers 4
cvgruplac-json --gruplac gruplac_COL0008423.json --cvlac cvlac_0000707619.json --out unidos/
cvgruplac-json --gruplac gruplac/ --out unidos/        # sin CvLAC: ids de CvLAC sin verificar
```

- `--cvlac` y `--gruplac` reciben archivos o carpetas (`cvlac_*.json[.gz]`, `gruplac_*.json[.gz]`). Si un COD_RH o
  un grupo está en más de una entrada, gana la primera.
- Escribe `unidos/gruplac/` y `unidos/cvlac/` con el mismo nombre y compresión de cada entrada, y
  `unidos/cvgruplac_summary.json` con los conteos y los archivos que no pudo leer. `--only gruplac` escribe solo los
  GrupLAC.
- Hace tres pasadas: lee los hashes de los CvLAC, une los GrupLAC y luego los CvLAC.

En Python:

```python
from cvgruplac_json import link, link_gruplac, link_cvlac, id_hash

index = link(gruplacs, cvlacs)   # listas de dicts de gruplac-json y cvlac-json, unidos en su lugar
```

## Los identificadores

Cada producto (obras, proyectos, eventos, patentes y cada ítem de `other_products`) empieza con dos claves:

```json
"id": "efc8d0bb2fa50a617767aa814a57a7a40c1c956f",
"scrapping_ids": [
  {"id": "efc8d0bb2fa50a617767aa814a57a7a40c1c956f", "source": "cvlac"},
  {"id": "efc8d0bb2fa50a617767aa814a57a7a40c1c956f", "source": "gruplac"}
]
```

**En un GrupLAC**

- `source: "cvlac"`: una por integrante autor con `product_hash`, en el orden de los autores. Es el id del producto
  en el CvLAC de ese integrante (el `product_hash` que cvlac-json pone en la entrada del dueño). Si el CvLAC del
  integrante está entre las entradas, se pone solo si el producto está en él; si no está, se pone con
  `"verified": false`. No hay ninguna en las secciones que solo tiene el GrupLAC
  ([`data/sections.json`](src/cvgruplac_json/data/sections.json)), ni en proyectos y eventos, que el GrupLAC lista
  sin autores.
- `source: "gruplac"`, siempre la última: el primer id de CvLAC si lo hay, así que un producto que está en los dos
  tiene el mismo id. Si no, el SHA-1 de `título|código COL|tipo|año` (abajo).
- `id` es el de `source: "gruplac"`.

**En un CvLAC**

- `source: "cvlac"`: el `product_hash` del dueño. Los productos sin él (los eventos) usan el SHA-1 de
  `título|COD_RH|event|año`.
- `source: "gruplac"`, con `group` (código COL): una por cada producto de un GrupLAC que lo lista como id de CvLAC
  verificado. Un artículo del CV que está en dos grupos tiene dos.
- `id` es el de `source: "cvlac"` y reemplaza el `id` por posición de cvlac-json (`cvlac:COD_RH:n`).

**El hash.** `id_hash(título, dueño, tipo, año, n)` es la receta del `product_hash` con el dueño que corresponda: el
SHA-1 de

```
<título>|<dueño>|<tipo>|<año>
```

- título en minúsculas, sin tildes y solo con letras y dígitos; un ítem sin título usa su nombre (eventos) o su texto;
- dueño: el código COL del grupo (el número GrupLAC de 14 dígitos si no tiene), o el COD_RH con 10 dígitos (con un
  COD_RH y los tipos `work`, `project`, `patent` y `other` da exactamente el `product_hash`);
- tipo: `work`, `project`, `event`, `patent` u `other`;
- año: `year_published`, `year`, el año de `start` o el de `date`.

Si varios productos del mismo JSON dan la misma clave, el n-ésimo, en el orden de la página, lleva `|n` al final; y
un candidato ya usado en ese JSON pasa al siguiente `n`. Por eso `id` es único dentro de cada GrupLAC y de cada
CvLAC. Ejemplo de clave de un evento: `juevesdelaciencia|COL0008423|event|2023`.

`product_hash.py` es una copia sin cambios del de cvlac-json y gruplac-json; `tests/product_hash_vectors.json` fija
su resultado en los tres paquetes.

## Desarrollo

```bash
python -m pip install -e ".[dev]"
python -m pytest
ruff check . && ruff format --check .
```

Las versiones se publican en PyPI desde GitHub Actions al subir una etiqueta `v*`; ver
[PUBLISHING.md](PUBLISHING.md) y [CHANGELOG.md](CHANGELOG.md).
