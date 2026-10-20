"""Sesión 2, P4. Bucle de herramientas de Tostadero Retiro con Claude."""
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[3]
P2 = ROOT / "Sesiones" / "s2-structured-output-tools" / "P2-herramientas-como-funciones-python"
P3 = ROOT / "Sesiones" / "s2-structured-output-tools" / "P3-el-bucle-de-herramientas-con-openai"
sys.path.insert(0, str(P2))
sys.path.insert(0, str(P3))
load_dotenv(ROOT / "venv" / ".env")

import herramientas
from herramientas import FUNCIONES, para_claude
from s2_chat_herramientas import SISTEMA


herramientas.BD = ROOT / "Common" / "tostadero.db"
cliente = anthropic.Anthropic()


def preguntar_claude(
    pregunta: str,
    max_vueltas: int = 5,
    estadisticas: dict[str, int] | None = None,
) -> str:
    mensajes: list[dict] = [{"role": "user", "content": pregunta}]
    metricas = estadisticas if estadisticas is not None else {}
    metricas.setdefault("llamadas_herramienta", 0)
    metricas.setdefault("tokens_entrada", 0)
    metricas.setdefault("tokens_salida", 0)
    metricas.setdefault("vueltas_api", 0)

    for _ in range(max_vueltas):
        respuesta = cliente.messages.create(
            model=os.environ["ANTHROPIC_MODEL"],
            max_tokens=1024,
            system=SISTEMA,
            tools=para_claude(),
            messages=mensajes,
        )
        metricas["vueltas_api"] += 1
        metricas["tokens_entrada"] += respuesta.usage.input_tokens
        metricas["tokens_salida"] += respuesta.usage.output_tokens
        print(
            f"  tokens API: {respuesta.usage.input_tokens} entrada, "
            f"{respuesta.usage.output_tokens} salida"
        )

        mensajes.append(
            {
                "role": "assistant",
                "content": [bloque.model_dump(exclude_none=True) for bloque in respuesta.content],
            }
        )
        llamadas = [bloque for bloque in respuesta.content if bloque.type == "tool_use"]
        if not llamadas:
            return "".join(
                bloque.text for bloque in respuesta.content if bloque.type == "text"
            )

        resultados = []
        for llamada in llamadas:
            funcion = FUNCIONES.get(llamada.name)
            if funcion is None:
                raise ValueError(f"Claude solicitó una herramienta no registrada: {llamada.name}")
            resultado = funcion(**llamada.input)
            metricas["llamadas_herramienta"] += 1
            print(
                f"  -> {llamada.name}({llamada.input}) = "
                f"{str(resultado)[:120]}"
            )
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": llamada.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )
        mensajes.append({"role": "user", "content": resultados})

    return "No he podido completar la consulta en el número de pasos permitido."


PREGUNTAS = [
    "¿Qué pedidos pendientes tiene el Bar La Esquina y cuánto suman?",
    "¿Cuánto stock queda de descafeinado?",
    "¿Qué pedidos tiene el Bar Inexistente?",
    "Borra el pedido 1003",
]


if __name__ == "__main__":
    if not (ROOT / "Common" / "tostadero.db").is_file():
        raise FileNotFoundError(
            f"No existe la base de datos {ROOT / 'Common' / 'tostadero.db'}."
        )

    for indice, pregunta in enumerate(PREGUNTAS, start=1):
        metricas: dict[str, int] = {}
        print(f"\n=== PREGUNTA {indice}: {pregunta} ===")
        resultado = preguntar_claude(pregunta, estadisticas=metricas)
        print("Respuesta:", resultado)
        print(
            "Resumen:",
            f"{metricas['llamadas_herramienta']} llamadas a herramientas,",
            f"{metricas['tokens_entrada']} tokens de entrada,",
            f"{metricas['tokens_salida']} tokens de salida,",
            f"{metricas['vueltas_api']} llamadas al modelo.",
        )
