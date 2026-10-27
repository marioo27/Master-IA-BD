"""The P1 technical-support agent implemented with LangChain 1.x."""
import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
S3_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT / "venv" / ".env")
sys.path.insert(0, str(S3_DIR))

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, ModelCallLimitMiddleware
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import herramientas as h
from s3_agente import SISTEMA


@tool
def buscar_cliente(texto: str) -> list[dict]:
    """Busca clientes por nombre (coincidencia parcial). Devuelve id, nombre, tipo y distrito."""
    return h.buscar_cliente(texto)


@tool
def consultar_pedidos(cliente_id: int) -> list[dict]:
    """Lista los pedidos de un cliente con fecha, estado y total en euros."""
    return h.consultar_pedidos(cliente_id)


@tool
def crear_incidencia(cliente_id: int, maquina: str, descripcion: str,
                     prioridad: Literal["baja", "media", "alta"]) -> dict:
    """Registra una avería de una máquina de un cliente (maquina = SKU, p. ej. MAQ-010)."""
    return h.crear_incidencia(cliente_id, maquina, descripcion, prioridad)


agente = create_agent(
    model=f"anthropic:{os.environ['ANTHROPIC_MODEL']}",
    tools=[buscar_cliente, consultar_pedidos, crear_incidencia],
    system_prompt=SISTEMA,
    middleware=[
        HumanInTheLoopMiddleware(interrupt_on={"crear_incidencia": True}),
        ModelCallLimitMiddleware(run_limit=8),
    ],
    checkpointer=InMemorySaver(),
)


def ejecutar(correo: str, thread_id: str = "correo-lumbre-001") -> str:
    config = {"configurable": {"thread_id": thread_id}}
    estado = agente.invoke({"messages": [{"role": "user", "content": correo}]}, config)
    while "__interrupt__" in estado:
        decisiones = []
        for peticion in estado["__interrupt__"][0].value["action_requests"]:
            aprobado = input(
                f"¿Aprobar {peticion['name']}({peticion['args']})? [s/N] "
            ).strip().lower() == "s"
            decisiones.append({"type": "approve" if aprobado else "reject"})
        estado = agente.invoke(Command(resume={"decisions": decisiones}), config)
    return estado["messages"][-1].text


if __name__ == "__main__":
    correo = (
        "Os escribo del Restaurante Lumbre: la cafetera de dos grupos no calienta "
        "y hoy no podemos servir cafés."
    )
    print(ejecutar(correo))