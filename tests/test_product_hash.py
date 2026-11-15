import hashlib
import json
import pathlib

import pytest

from cvgruplac_json import product_hash
from cvgruplac_json.product_hash import hash_key

VECTORS = json.loads((pathlib.Path(__file__).parent / "product_hash_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", VECTORS, ids=[v["key"][:40] for v in VECTORS])
def test_vectors(v):
    """The same vectors are in cvlac-json and gruplac-json: the three copies must agree."""
    assert hash_key(v["title"], v["cod_rh"], v["kind"], v["year"], v.get("n", 1)) == v["key"]
    assert product_hash(v["title"], v["cod_rh"], v["kind"], v["year"], v.get("n", 1)) == v["hash"]
    assert v["hash"] == hashlib.sha1(v["key"].encode("ascii")).hexdigest()
