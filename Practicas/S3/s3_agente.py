"""Agente de atención técnica con límite de pasos, trazas y aprobación humana."""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import anthropic
from dotenv import load_dotenv

from herramientas import DEFINICIONES, FUNCIONES

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "venv" / ".env")


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    esquema: dict
    funcion: Callable
    requiere_aprobacion: bool = False


class Agente:
    def __init__(self, sistema: str, herramientas: list[Herramienta], max_pasos: int = 8):
        self.llm = anthropic.Anthropic()
        self.modelo = os.environ["ANTHROPIC_MODEL"]
        self.sistema, self.max_pasos = sistema, max_pasos
        self.herramientas = {herramienta.nombre: herramienta for herramienta in herramientas}
        self.llamadas_modelo = 0
        self.tokens_entrada = 0
        self.tokens_salida = 0

    def _definiciones(self) -> list[dict]:
        return [{"name": herramienta.nombre,
                 "description": herramienta.descripcion,
                 "input_schema": herramienta.esquema}
                for herramienta in self.herramientas.values()]

    def _ejecutar(self, nombre: str, args: dict) -> tuple[object, bool]:
        """Return the result and an error flag so the model can recover from tool errors."""
        herramienta = self.herramientas.get(nombre)
        if herramienta is None:
            return f"La herramienta {nombre} no existe.", True
        if herramienta.requiere_aprobacion:
            aprobado = input(f"  ¿Aprobar {nombre}({args})? [s/N] ").strip().lower() == "s"
            if not aprobado:
                return "Un operador humano ha rechazado esta acción. No la repitas.", True
        try:
            return herramienta.funcion(**args), False
        except Exception as error:
            return f"Error al ejecutar {nombre}: {error}", True

    def ejecutar(self, objetivo: str) -> str:
        mensajes: list = [{"role": "user", "content": objetivo}]
        for paso in range(1, self.max_pasos + 1):
            respuesta = self.llm.messages.create(
                model=self.modelo,
                max_tokens=2048,
                system=self.sistema,
                tools=self._definiciones(),
                messages=mensajes,
            )
            self.llamadas_modelo += 1
            if respuesta.usage:
                self.tokens_entrada += respuesta.usage.input_tokens
                self.tokens_salida += respuesta.usage.output_tokens
            mensajes.append({"role": "assistant", "content": respuesta.content})
            if respuesta.stop_reason != "tool_use":
                return "".join(bloque.text for bloque in respuesta.content if bloque.type == "text")

            resultados = []
            for bloque in respuesta.content:
                if bloque.type == "text" and bloque.text.strip():
                    print(f"[paso {paso}] razonamiento visible: {bloque.text.strip()[:100]}")
                if bloque.type != "tool_use":
                    continue
                salida, es_error = self._ejecutar(bloque.name, bloque.input)
                print(f"[paso {paso}] {bloque.name}({bloque.input}) -> {str(salida)[:90]}")
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": bloque.id,
                    "is_error": es_error,
                    "content": json.dumps(salida, ensure_ascii=False, default=str),
                })
            mensajes.append({"role": "user", "content": resultados})
        return "He alcanzado el límite de pasos sin terminar. Paso el caso a una persona."


SISTEMA = """Eres el agente de atención técnica de Tostadero Retiro S.L.
Objetivo: resolver correos de clientes usando las herramientas.
Procedimiento:
1. Identifica al cliente con buscar_cliente antes de usar su id.
2. Si hay una avería, registra una incidencia con la prioridad adecuada
   (alta si el local no puede servir café).
3. Si preguntan por pedidos, consulta los datos reales; no inventes cifras.
4. Termina con una respuesta breve al cliente, en español y con tono cordial."""


if __name__ == "__main__":
    herramientas = [
        Herramienta(
            definicion["name"], definicion["description"], definicion["parameters"],
            FUNCIONES[definicion["name"]],
            requiere_aprobacion=(definicion["name"] == "crear_incidencia"),
        )
        for definicion in DEFINICIONES
    ]
    agente = Agente(SISTEMA, herramientas)
    correo = (
        "Buenas, os escribo del Restaurante Lumbre. La cafetera de dos grupos no "
        "calienta y hoy no podemos servir cafés. ¿Además, cuándo llega el pedido pendiente?"
    )
    print(agente.ejecutar(correo))