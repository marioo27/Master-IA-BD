"""Route simple customer questions to an LLM and complex cases to the agent."""
import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import openai
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
S3_DIR = Path(__file__).resolve().parent
S1_DIR = ROOT / "Practicas" / "S1"
S2_DIR = ROOT / "Practicas" / "S2" / "e2"
load_dotenv(ROOT / "venv" / ".env")
sys.path[:0] = [str(S3_DIR), str(S2_DIR), str(S1_DIR)]

from llm_client import LLM
from s2_extraer_correo import CorreoClasificado, SISTEMA as SISTEMA_CLASIFICACION
from s3_agente import Agente, Herramienta, SISTEMA
from herramientas import DEFINICIONES, FUNCIONES


SISTEMA_CONSULTAS = """Respondes consultas sencillas de clientes de Tostadero Retiro S.L.
Sé cordial y conciso, en español. No inventes precios, existencias, facturas, pedidos ni
fechas de entrega. Si el correo no aporta datos suficientes para responder con certeza,
explícalo y pide la información necesaria o indica que el equipo lo confirmará."""


@dataclass
class Resultado:
    texto: str
    tipo: str
    ruta: str
    llamadas: int
    tokens_entrada: int
    tokens_salida: int


def clasificar_con_uso(correo: str) -> tuple[CorreoClasificado, int, int]:
    respuesta = openai.OpenAI().responses.parse(
        model=os.environ["OPENAI_MODEL"],
        instructions=SISTEMA_CLASIFICACION,
        input=correo,
        text_format=CorreoClasificado,
    )
    if respuesta.output_parsed is None:
        raise ValueError("OpenAI no devolvió una salida estructurada.")
    uso = respuesta.usage
    return (respuesta.output_parsed,
            uso.input_tokens if uso else 0,
            uso.output_tokens if uso else 0)


def crear_agente() -> Agente:
    herramientas = [
        Herramienta(
            definicion["name"], definicion["description"], definicion["parameters"],
            FUNCIONES[definicion["name"]],
            requiere_aprobacion=(definicion["name"] == "crear_incidencia"),
        )
        for definicion in DEFINICIONES
    ]
    return Agente(SISTEMA, herramientas)


def atender(correo: str, proveedor: str = "gemini", solo_agente: bool = False) -> Resultado:
    agente = crear_agente()
    if solo_agente:
        texto = agente.ejecutar(correo)
        return Resultado(texto, "sin clasificar", "agente directo", agente.llamadas_modelo,
                         agente.tokens_entrada, agente.tokens_salida)

    clasificacion, tokens_clasificador_in, tokens_clasificador_out = clasificar_con_uso(correo)
    if clasificacion.tipo == "consulta":
        modelo = "openai/gpt-5.4-nano" if proveedor == "openai" else None
        respuesta = LLM(proveedor, modelo=modelo).responder(SISTEMA_CONSULTAS, correo)
        return Resultado(
            respuesta.texto,
            clasificacion.tipo,
            f"consulta con {proveedor}",
            2,
            tokens_clasificador_in + respuesta.tokens_entrada,
            tokens_clasificador_out + respuesta.tokens_salida,
        )

    texto = agente.ejecutar(correo)
    return Resultado(
        texto,
        clasificacion.tipo,
        "agente",
        1 + agente.llamadas_modelo,
        tokens_clasificador_in + agente.tokens_entrada,
        tokens_clasificador_out + agente.tokens_salida,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Route an email or compare with the direct agent.")
    parser.add_argument(
        "--correo",
        default="¿Tenéis café descafeinado de especialidad?",
        help="Customer email to process.",
    )
    parser.add_argument("--proveedor", choices=("gemini", "openai"), default="gemini")
    parser.add_argument(
        "--solo-agente",
        action="store_true",
        help="Skip classification to measure the agent-only path for comparison.",
    )
    argumentos = parser.parse_args()

    resultado = atender(argumentos.correo, argumentos.proveedor, argumentos.solo_agente)
    print(f"Tipo: {resultado.tipo} | ruta: {resultado.ruta}")
    print(f"Llamadas al modelo: {resultado.llamadas}")
    print(f"Tokens: {resultado.tokens_entrada} entrada / {resultado.tokens_salida} salida")
    print(resultado.texto)


if __name__ == "__main__":
    main()