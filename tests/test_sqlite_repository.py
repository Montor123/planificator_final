from repositories.sqlite_repository import SQLiteRepository

def test_save_load(tmp_path):
    db = SQLiteRepository(str(tmp_path/"t.db"))
    db.save_json("k",{"a":1})
    assert db.load_json("k",{}) == {"a":1}
    assert db.load_json("nope",{"d":True}) == {"d":True}
