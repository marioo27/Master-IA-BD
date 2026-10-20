"""Práctica 1 de la sesión 2: clasificador de correos con evaluación."""
import os
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Literal

import anthropic
import openai
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT / "venv" / ".env"
DATABASE = ROOT / "Common" / "tostadero.db"

if not ENV_FILE.is_file():
    raise FileNotFoundError(f"No se encuentra el archivo de configuración: {ENV_FILE}")
load_dotenv(ENV_FILE)


class Linea(BaseModel):
    producto: str = Field(description="Producto tal y como lo menciona el cliente")
    cantidad: int = Field(description="Unidades o kilos pedidos")


class CorreoClasificado(BaseModel):
    tipo: Literal["pedido", "incidencia", "consulta", "mixto"]
    cliente: str | None = Field(description="Nombre del negocio si aparece; si no, null")
    lineas: list[Linea] = Field(description="Vacía si no hay pedido")
    urgente: bool
    resumen: str = Field(description="Una sola frase en español")


SISTEMA = (
    "Extraes información de correos de clientes de un distribuidor de café para "
    "hostelería. Clasifica el propósito principal como pedido, incidencia, consulta "
    "o mixto. Si aparecen varios negocios, intenta incluir sus nombres en cliente. "
    "Si no se indica ningún negocio, cliente debe ser null. El resumen debe estar "
    "en español, incluso si el correo está en otro idioma."
)


def con_openai(correo: str) -> CorreoClasificado:
    respuesta = openai.OpenAI().responses.parse(
        model=os.environ["OPENAI_MODEL"],
        instructions=SISTEMA,
        input=correo,
        text_format=CorreoClasificado,
    )
    if respuesta.output_parsed is None:
        raise ValueError("OpenAI no devolvió una salida estructurada.")
    return respuesta.output_parsed


def con_claude(correo: str) -> CorreoClasificado:
    respuesta = anthropic.Anthropic().messages.parse(
        model=os.environ["ANTHROPIC_MODEL"],
        max_tokens=1024,
        system=SISTEMA,
        messages=[{"role": "user", "content": correo}],
        output_format=CorreoClasificado,
    )
    if respuesta.parsed_output is None:
        raise ValueError("Claude no devolvió una salida estructurada.")
    return respuesta.parsed_output


def con_gemini(correo: str) -> CorreoClasificado:
    if os.getenv("GEMINI_API_KEY"):
        cliente = genai.Client()
        respuesta = cliente.interactions.create(
            model=os.environ["GEMINI_MODEL"].removeprefix("google/"),
            system_instruction=SISTEMA,
            input=correo,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": CorreoClasificado.model_json_schema(),
            },
        )
        return CorreoClasificado.model_validate_json(respuesta.output_text)

    cliente = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
    respuesta = cliente.chat.completions.parse(
        model=os.environ["GEMINI_MODEL"],
        messages=[
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": correo},
        ],
        response_format=CorreoClasificado,
    )
    resultado = respuesta.choices[0].message.parsed
    if resultado is None:
        raise ValueError("Gemini no devolvió una salida estructurada.")
    return resultado


CASOS: list[tuple[str, str]] = [
    ("Necesito 20 kg del blend de hostelería para el viernes. Bar La Esquina.", "pedido"),
    ("El molino hace un ruido raro desde ayer, ¿podéis venir?", "incidencia"),
    ("¿Tenéis café descafeinado de especialidad?", "consulta"),
    ("Mandadme 5 kg de Etiopía y, de paso, la cafetera gotea. Restaurante Lumbre.", "mixto"),
    ("URGENTE: sin café para mañana, 10 kg de blend. Hotel Prado Suites.", "pedido"),
    ("Buenas, ¿la factura de septiembre ya está emitida?", "consulta"),
    (
        "Fantástico, el molino vuelve a pararse justo antes del desayuno; necesitamos "
        "que venga un técnico. Cafetería Atocha 12.",
        "incidencia",
    ),
    (
        "Bar La Esquina pide 5 kg de blend y Restaurante Lumbre 8 kg de Etiopía "
        "para el viernes.",
        "pedido",
    ),
    ("Hi, could you send 12 kg of decaf to Hotel Prado Suites before Friday?", "pedido"),
    ("Necesito 3 kg de descafeinado para mañana, por favor.", "pedido"),
    ("Somos un negocio nuevo, Bar El Faro: queremos 6 kg de blend para el lunes.", "pedido"),
    (
        "No mandéis café todavía; solo quería saber si tenéis descafeinado en grano. "
        "Panadería Ibiza.",
        "consulta",
    ),
    (
        "¿Podéis enviarme dos cajas de vasos compostables junto con el pedido de "
        "mañana? Bar La Esquina.",
        "pedido",
    ),
    (
        "La cafetera pierde presión y, además, necesitamos 4 kg de Etiopía. "
        "Hotel Prado Suites.",
        "mixto",
    ),
    ("¿Por qué ha subido el precio del blend en la última factura? Restaurante Lumbre.", "consulta"),
    ("El pedido 1004 no ha llegado y lo necesitamos para el servicio de hoy. Bar La Esquina.", "incidencia"),
    ("¿Cuál es el horario de reparto en Arganzuela? Cafetería Atocha 12.", "consulta"),
    ("Mandad 2 kg de Etiopía el jueves. No es urgente. Panadería Ibiza.", "pedido"),
]


def _normalizar_nombre(nombre: str) -> list[str]:
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", nombre.casefold())
        if not unicodedata.combining(caracter)
    )
    return re.findall(r"[a-z0-9]+", sin_acentos)


def buscar_cliente(nombre: str) -> bool:
    """Comprueba si el nombre extraído corresponde a algún cliente de la BD."""
    if not DATABASE.is_file():
        raise FileNotFoundError(
            f"No existe {DATABASE}. Créala primero ejecutando "
            f"'{ROOT / 'Common' / 'crear_bd.py'}'."
        )

    nombres_extraidos = [
        parte.strip()
        for parte in re.split(r"[,;/]|\s+y\s+|\s+and\s+", nombre, flags=re.IGNORECASE)
        if parte.strip()
    ]
    if not nombres_extraidos:
        return False

    with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as conexion:
        nombres = conexion.execute("SELECT nombre FROM clientes").fetchall()

    nombres_bd = [_normalizar_nombre(nombre_bd) for (nombre_bd,) in nombres]
    for nombre_extraido in nombres_extraidos:
        tokens_extraidos = _normalizar_nombre(nombre_extraido)
        if not tokens_extraidos:
            return False
        coincide = any(
            any(
                tokens_bd[inicio:inicio + len(tokens_extraidos)] == tokens_extraidos
                for inicio in range(len(tokens_bd) - len(tokens_extraidos) + 1)
            )
            for tokens_bd in nombres_bd
        )
        if not coincide:
            return False
    return True


def evaluar(nombre: str, extraer) -> None:
    aciertos = 0
    for correo, esperado in CASOS:
        resultado = extraer(correo)
        aciertos += resultado.tipo == esperado

        if any(linea.cantidad <= 0 for linea in resultado.lineas):
            print(f"  [{nombre}] cantidad no válida en: {correo[:60]}...")
        if resultado.cliente and not buscar_cliente(resultado.cliente):
            print(
                f"  [{nombre}] cliente no encontrado en la base de datos: "
                f"{resultado.cliente!r} (correo: {correo[:60]}...)"
            )

    print(f"{nombre}: {aciertos}/{len(CASOS)} tipos correctos")


if __name__ == "__main__":
    for nombre, extraer in [
        ("OpenAI", con_openai),
        ("Claude", con_claude),
        ("Gemini", con_gemini),
    ]:
        evaluar(nombre, extraer)
