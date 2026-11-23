"""Pruebas offline de aislamiento y borrado completo."""
import os
import sqlite3
import tempfile

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore


def ejecutar():
    with tempfile.TemporaryDirectory() as carpeta:
        hilos = sqlite3.connect(os.path.join(carpeta, "hilos.db"), check_same_thread=False)
        memoria = sqlite3.connect(
            os.path.join(carpeta, "memoria.db"),
            check_same_thread=False,
            isolation_level=None,
        )
        checkpointer = SqliteSaver(hilos)
        checkpointer.setup()
        store = SqliteStore(memoria)
        store.setup()

        store.put(("clientes", "1"), "idioma", {"valor": "espanol"})
        store.put(("clientes", "2"), "idioma", {"valor": "ingles"})

        assert store.search(("clientes", "1"))[0].value["valor"] == "espanol"
        assert len(store.search(("clientes", "2"))) == 1
        assert len(store.search(("clientes", "1"))) == 1

        hilos.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)"
            " VALUES (?, '', '1', NULL, NULL, X'00', '{}')",
            ("1-lunes",),
        )
        hilos.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)"
            " VALUES (?, '', '1', NULL, NULL, X'00', '{}')",
            ("1-martes",),
        )
        hilos.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)"
            " VALUES (?, '', '1', NULL, NULL, X'00', '{}')",
            ("2-lunes",),
        )
        hilos.commit()

        for item in store.search(("clientes", "1")):
            store.delete(("clientes", "1"), item.key)
        filas = hilos.execute(
            "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE '1-%'"
        ).fetchall()
        for (thread_id,) in filas:
            checkpointer.delete_thread(thread_id)

        assert not store.search(("clientes", "1"))
        assert len(store.search(("clientes", "2"))) == 1
        assert hilos.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id LIKE '1-%'"
        ).fetchone()[0] == 0
        assert hilos.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id LIKE '2-%'"
        ).fetchone()[0] == 1

        hilos.close()
        memoria.close()
        print("OK: aislamiento por cliente")
        print("OK: borrado completo de cliente 1")
        print("OK: conservacion de datos del cliente 2")


if __name__ == "__main__":
    ejecutar()
