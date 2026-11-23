"""Sesion 4 - hilos persistentes y preferencias aisladas por cliente."""
import os
import sqlite3
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore

load_dotenv()

HILOS_DB = "hilos.db"
MEMORIA_DB = "memoria.db"


@dataclass
class Contexto:
    cliente_id: str


def _espacio(runtime: ToolRuntime[Contexto]) -> tuple[str, str]:
    return ("clientes", runtime.context.cliente_id)


hilos_conexion = sqlite3.connect(HILOS_DB, check_same_thread=False)
memoria_conexion = sqlite3.connect(MEMORIA_DB, check_same_thread=False, isolation_level=None)
checkpointer = SqliteSaver(hilos_conexion)
checkpointer.setup()
store = SqliteStore(memoria_conexion)
store.setup()


def _hilos_cliente(cliente_id: str) -> list[str]:
    filas = hilos_conexion.execute(
        "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE ?",
        (f"{cliente_id}-%",),
    ).fetchall()
    return [fila[0] for fila in filas]


def borrar_datos_cliente(cliente_id: str) -> None:
    namespace = ("clientes", cliente_id)
    for item in store.search(namespace):
        store.delete(namespace, item.key)
    for thread_id in _hilos_cliente(cliente_id):
        checkpointer.delete_thread(thread_id)


@tool
def recordar_preferencia(clave: str, valor: str, runtime: ToolRuntime[Contexto]) -> str:
    """Guarda solo una preferencia estable y no sensible del cliente actual."""
    runtime.store.put(_espacio(runtime), clave, {"valor": valor})
    return f"Preferencia '{clave}' guardada."


@tool
def ver_preferencias(runtime: ToolRuntime[Contexto]) -> dict:
    """Devuelve las preferencias del cliente actual."""
    return {item.key: item.value["valor"] for item in runtime.store.search(_espacio(runtime))}


@tool
def olvidar_preferencias(runtime: ToolRuntime[Contexto]) -> str:
    """Borra las preferencias y todos los hilos del cliente actual si lo solicita."""
    borrar_datos_cliente(runtime.context.cliente_id)
    return "Datos eliminados: preferencias y hilos del cliente."


SISTEMA = """Eres el asistente comercial de Tostadero Retiro.
Al empezar cada conversacion consulta ver_preferencias y tenlas en cuenta.
Cuando el cliente exprese una preferencia estable, guardala con recordar_preferencia.
No almacenes datos sensibles ni datos de pago.
Si pide que olvides sus datos, usa olvidar_preferencias y confirmano."""


def crear_agente():
    modelo = f"anthropic:{os.environ['ANTHROPIC_MODEL']}"
    return create_agent(
        model=modelo,
        tools=[recordar_preferencia, ver_preferencias, olvidar_preferencias],
        system_prompt=SISTEMA,
        context_schema=Contexto,
        checkpointer=checkpointer,
        store=store,
        middleware=[SummarizationMiddleware(
            model=modelo,
            trigger=("tokens", 3000),
            keep=("messages", 10),
        )],
    )


def es_solicitud_borrado(texto: str) -> bool:
    palabras = ("olvid", "borr", "elimin", "suprimir", "mis datos")
    normalizado = texto.lower()
    return any(palabra in normalizado for palabra in palabras)


def cerrar():
    hilos_conexion.close()
    memoria_conexion.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python s4_memoria_langchain.py <cliente_id> <hilo>")
    cliente_id, hilo = sys.argv[1], sys.argv[2]
    thread_id = f"{cliente_id}-{hilo}"
    config = {"configurable": {"thread_id": thread_id}}
    agente = crear_agente()
    try:
        while texto := input("Cliente: ").strip():
            estado = agente.invoke(
                {"messages": [{"role": "user", "content": texto}]},
                config,
                context=Contexto(cliente_id=cliente_id),
            )
            print("Asistente:", estado["messages"][-1].text)

            # El hilo actual puede recrearse al guardar el ultimo estado.
            # Se elimina despues de invoke para garantizar el borrado completo.
            if es_solicitud_borrado(texto):
                borrar_datos_cliente(cliente_id)
    finally:
        cerrar()
