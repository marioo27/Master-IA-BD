"""Sesión 1. Una interfaz común para varios proveedores (patrón Adapter).

El resto del bloque usará LLM.responder() cuando el proveedor dé igual."""
import os
import time
from dataclasses import dataclass

import anthropic
import openai
from dotenv import load_dotenv
from google import genai

load_dotenv()

OPENROUTER = "https://openrouter.ai/api/v1"

# Precios en USD por millón de tokens (entrada, salida), con el id del modelo tal y como
# va en .env, p. ej. "openai/gpt-5.4-mini". Se usan para estimar coste_usd.
# Valores orientativos, revisables en https://openrouter.ai/models.
PRECIOS: dict[str, tuple[float, float]] = {
    "openai/gpt-5.4-mini": (0.15, 0.60),
    "anthropic/claude-haiku-4.5": (0.15, 0.75),
    "google/gemini-3.8-flash": (0.10, 0.40),
}


@dataclass
class Respuesta:
    texto: str
    tokens_entrada: int
    tokens_salida: int
    segundos: float
    modelo: str

    @property
    def coste_usd(self) -> float | None:
        if self.modelo not in PRECIOS:
            return None
        p_in, p_out = PRECIOS[self.modelo]
        return (self.tokens_entrada * p_in + self.tokens_salida * p_out) / 1_000_000


class LLM:
    """proveedor: 'openai' | 'claude' | 'gemini' | 'ollama'.

    Cada proveedor habla un formato de API: Responses (OpenAI), Messages (Claude),
    Interactions (Gemini nativo) o Chat Completions (Gemini vía OpenRouter y Ollama)."""

    def __init__(self, proveedor: str, modelo: str | None = None):
        self.proveedor = proveedor
        defecto = {
            "openai": os.getenv("OPENAI_MODEL"),
            "claude": os.getenv("ANTHROPIC_MODEL"),
            "gemini": os.getenv("GEMINI_MODEL"),
            "ollama": "llama3.2",
        }
        self.modelo = modelo or defecto[proveedor]
        if proveedor == "openai":
            self.formato = "responses"
            self._c = openai.OpenAI(max_retries=3)  # reintentos con espera exponencial
        elif proveedor == "claude":
            self.formato = "messages"
            self._c = anthropic.Anthropic(max_retries=3)
        elif proveedor == "gemini" and os.getenv("GEMINI_API_KEY"):  # opcional: API nativa
            self.formato = "interactions"
            self.modelo = self.modelo.removeprefix("google/")
            self._c = genai.Client()
        elif proveedor == "gemini":  # por defecto, vía OpenRouter
            self.formato = "chat"
            self._c = openai.OpenAI(base_url=OPENROUTER, api_key=os.environ["OPENROUTER_API_KEY"],
                                    max_retries=3)
        elif proveedor == "ollama":  # Ollama expone una API compatible con OpenAI
            self.formato = "chat"
            self._c = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        else:
            raise ValueError(f"Proveedor no soportado: {proveedor}")

    def responder(self, sistema: str, prompt: str, temperatura: float | None = None,
                  max_tokens: int | None = None) -> Respuesta:
        extra = {} if temperatura is None else {"temperature": temperatura}
        t0 = time.perf_counter()
        if self.formato == "responses":
            llamada = {
                "model": self.modelo,
                "instructions": sistema,
                "input": prompt,
            }
            if temperatura is not None:
                llamada["temperature"] = temperatura
            if max_tokens is not None:
                llamada["max_output_tokens"] = max_tokens
            r = self._c.responses.create(**llamada)
            texto = r.output_text
            t_in = r.usage.input_tokens
            t_out = r.usage.output_tokens
        elif self.formato == "messages":
            llamada = {
                "model": self.modelo,
                "max_tokens": max_tokens if max_tokens is not None else 512,
                "system": sistema,
                "messages": [{"role": "user", "content": prompt}],
            }
            if temperatura is not None:
                llamada["temperature"] = temperatura
            r = self._c.messages.create(**llamada)
            texto = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
            t_in = r.usage.input_tokens
            t_out = r.usage.output_tokens
        elif self.formato == "interactions":
            config = {"generation_config": extra.copy()}
            if max_tokens is not None:
                config["generation_config"]["max_output_tokens"] = max_tokens
            if not config["generation_config"]:
                config = {}
            r = self._c.interactions.create(
                model=self.modelo, system_instruction=sistema, input=prompt, **config
            )
            texto, t_in, t_out = r.output_text, r.usage.total_input_tokens, r.usage.total_output_tokens
        else:  # Chat Completions, el formato "clásico" de OpenAI que imitan casi todos
            payload = {
                "model": self.modelo,
                "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": prompt}],
            }
            if temperatura is not None:
                payload["temperature"] = temperatura
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            r = self._c.chat.completions.create(**payload)
            texto = r.choices[0].message.content
            t_in, t_out = r.usage.prompt_tokens, r.usage.completion_tokens
        return Respuesta(texto, t_in, t_out, time.perf_counter() - t0, self.modelo)

    def responder_stream(self, sistema: str, prompt: str, temperatura: float | None = None,
                         max_tokens: int | None = None):
        extra = {} if temperatura is None else {"temperature": temperatura}
        if self.formato == "responses":
            llamada = {"model": self.modelo, "instructions": sistema, "input": prompt}
            if temperatura is not None:
                llamada["temperature"] = temperatura
            if max_tokens is not None:
                llamada["max_output_tokens"] = max_tokens
            for evento in self._c.responses.create(**llamada, stream=True):
                if evento.type == "response.output_text.delta":
                    yield evento.delta
        elif self.formato == "messages":
            llamada = {
                "model": self.modelo,
                "max_tokens": max_tokens if max_tokens is not None else 512,
                "system": sistema,
                "messages": [{"role": "user", "content": prompt}],
            }
            if temperatura is not None:
                llamada["temperature"] = temperatura
            with self._c.messages.stream(**llamada) as flujo:
                for trozo in flujo.text_stream:
                    yield trozo
        elif self.formato == "interactions":
            config = {"generation_config": extra.copy()}
            if max_tokens is not None:
                config["generation_config"]["max_output_tokens"] = max_tokens
            if not config["generation_config"]:
                config = {}
            for evento in self._c.interactions.create(
                model=self.modelo, system_instruction=sistema, input=prompt, stream=True, **config
            ):
                if evento.event_type == "step.delta" and getattr(evento.delta, "type", None) == "text":
                    yield evento.delta.text
        else:
            payload = {
                "model": self.modelo,
                "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": prompt}],
            }
            if temperatura is not None:
                payload["temperature"] = temperatura
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            for trozo in self._c.chat.completions.create(**payload, stream=True):
                if trozo.choices and trozo.choices[0].delta.content:
                    yield trozo.choices[0].delta.content


if __name__ == "__main__":
    for proveedor in ["openai", "claude", "gemini"]:
        try:
            r = LLM(proveedor).responder("Responde en una frase.", "¿Qué es un token?")
        except NotImplementedError as e:
            print(f"{proveedor:7} pendiente: {e}")
            continue
        print(f"{proveedor:7} {r.segundos:5.2f} s  {r.tokens_entrada:4}/{r.tokens_salida:<4} {r.texto}")
