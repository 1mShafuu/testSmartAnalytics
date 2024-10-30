import json
from gui.editor import TableEditorApp
from db.database import Database, DatabaseConfig


def load_db_config(file_path="db_config.json"):
    with open(file_path, "r") as file:
        config_data = json.load(file)
    return DatabaseConfig(**config_data)


if __name__ == "__main__":
    DB_CONFIG = load_db_config()
    db_manager = Database(DB_CONFIG)
    app = TableEditorApp(db_manager)
    app.mainloop()
