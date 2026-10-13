"""Sesión 1. Streaming y modelo local."""
import time

from llm_client import LLM

SISTEMA = ("Eres el asistente de atención al cliente de Tostadero Retiro S.L. "
           "Responde en español y en dos frases como máximo.")
PROMPT = "La máquina del bar La Esquina pierde presión y mañana entregan un pedido; ¿qué hago?"


if __name__ == "__main__":
    for proveedor in ["openai", "claude", "gemini"]:
        llm = LLM(proveedor)
        print(f"\n=== {proveedor} ===")
        inicio = time.perf_counter()
        texto = ""
        for trozo in llm.responder_stream(SISTEMA, PROMPT, max_tokens=120):
            print(trozo, end="", flush=True)
            texto += trozo
        print(f"\n\n{time.perf_counter() - inicio:.2f} s")
