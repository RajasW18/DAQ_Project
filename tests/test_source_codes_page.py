import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.settings.source_codes_page import SourceCodesPage


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.objects = {}

    def query(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return []

    def get(self, model, entry_no):
        return self.objects.get(entry_no)

    def add(self, obj):
        self.objects[obj.entry_no] = obj

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def test_editing_cell_persists_to_json(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    fake_session = FakeSession()

    monkeypatch.setattr("ui.settings.source_codes_page.get_session", lambda: fake_session)

    exported_path = tmp_path / "source_codes.json"

    def fake_export(rows):
        exported_path.write_text(str(rows), encoding="utf-8")

    monkeypatch.setattr("ui.settings.source_codes_page.export_source_codes", fake_export)

    page = SourceCodesPage(main_window=None)
    page.table.item(0, 1).setText("Alpha")
    page.table.itemChanged.emit(page.table.item(0, 1))

    assert fake_session.commits >= 1
    assert exported_path.exists()
    assert "Alpha" in exported_path.read_text(encoding="utf-8")

    app.quit()
