import gzip
import json

import pytest

from cvgruplac_json import __version__
from cvgruplac_json.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.parametrize("workers", [1, 2])
def test_folders(tmp_path, gruplac, cvlacs, capsys, workers):
    (tmp_path / "g").mkdir()
    (tmp_path / "c").mkdir()
    with gzip.open(tmp_path / "g" / "gruplac_COL0000001.json.gz", "wt", encoding="utf-8") as f:
        json.dump(gruplac, f)
    for c in cvlacs:
        (tmp_path / "c" / f"cvlac_{c['cod_rh']}.json").write_text(json.dumps(c), encoding="utf-8")
    out = tmp_path / "out"
    rc = main(["--gruplac", str(tmp_path / "g"), "--cvlac", str(tmp_path / "c"), "--out", str(out), "--workers", str(workers)])
    assert rc == 0
    s = json.loads(capsys.readouterr().out)
    assert s["gruplacs"] == 1 and s["cvlacs"] == 2 and s["cvlac_ids_verified"] == 1 and s["errors"] == 0
    with gzip.open(out / "gruplac" / "gruplac_COL0000001.json.gz") as f:
        g = json.load(f)
    a = json.loads((out / "cvlac" / "cvlac_0000000001.json").read_text(encoding="utf-8"))
    assert g["works"][0]["id"] == a["works"][0]["id"]
    assert a["works"][0]["scrapping_ids"][1] == {"id": g["works"][0]["id"], "source": "gruplac", "group": "COL0000001"}
    assert g["cvgruplac"]["cvlac_checked"] is True
    assert json.loads((tmp_path / "c" / "cvlac_0000000001.json").read_text())["works"][0]["id"] == "cvlac:0000000001:1"


def test_bad_file_is_reported(tmp_path, capsys):
    (tmp_path / "gruplac_COL9.json").write_text("{not json", encoding="utf-8")
    assert main(["--gruplac", str(tmp_path / "gruplac_COL9.json"), "--out", str(tmp_path / "o")]) == 1
    assert json.loads(capsys.readouterr().out)["errors"] == 1


@pytest.mark.parametrize("workers", [1, 2])
def test_products_output(tmp_path, gruplac, cvlacs, capsys, workers):
    from cvgruplac_json import link
    from cvgruplac_json.products import product_lines

    (tmp_path / "g").mkdir()
    (tmp_path / "c").mkdir()
    (tmp_path / "g" / "gruplac_COL0000001.json").write_text(json.dumps(gruplac), encoding="utf-8")
    for c in cvlacs:
        (tmp_path / "c" / f"cvlac_{c['cod_rh']}.json").write_text(json.dumps(c), encoding="utf-8")
    out = tmp_path / "out"
    args = ["--gruplac", str(tmp_path / "g"), "--cvlac", str(tmp_path / "c"), "--out", str(out), "--products"]
    assert main([*args, "--workers", str(workers), "--only", "gruplac"]) == 0
    s = json.loads(capsys.readouterr().out)
    with gzip.open(out / "products.jsonl.gz", "rt", encoding="utf-8") as f:
        got = [json.loads(x) for x in f]
    link([gruplac], cvlacs)
    want, _ = product_lines([gruplac], cvlacs)
    assert sorted(x["id"] for x in got) == sorted(x["id"] for x in want)
    assert s["product_lines"] == len(got) and not (out / "cvlac").exists()
    assert s["owners_in_group"] == 1 and s["owners_outside_membership"] == 1
