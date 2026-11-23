"""Sesion 4 - compactacion manual del historial."""
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()
llm = anthropic.Anthropic()
MODELO = os.environ["ANTHROPIC_MODEL"]
SISTEMA = "Eres el asistente comercial de Tostadero Retiro. Responde en espanol, con brevedad."
UMBRAL_TOKENS = 1000
MANTENER = 6


def compactar(mensajes: list[dict]) -> list[dict]:
    if MANTENER <= 0 or MANTENER % 2 != 0:
        raise ValueError("MANTENER debe ser positivo y par para conservar pares usuario/asistente")
    antiguos, recientes = mensajes[:-MANTENER], mensajes[-MANTENER:]
    transcripcion = "\n".join(f"{m['role']}: {m['content']}" for m in antiguos)
    if not transcripcion:
        return mensajes
    r = llm.messages.create(
        model=MODELO,
        max_tokens=600,
        system=("Resume esta conversacion de atencion al cliente. Conserva datos concretos: "
                "nombres, ids, cantidades, fechas, compromisos adquiridos y temas pendientes."),
        messages=[{"role": "user", "content": transcripcion}],
    )
    resumen = "".join(b.text for b in r.content if b.type == "text")
    return [
        {"role": "user", "content": f"[Resumen de la conversacion hasta aqui]\n{resumen}"},
        {"role": "assistant", "content": "Entendido. Continuo con ese contexto."},
        *recientes,
    ]


if __name__ == "__main__":
    historial: list[dict] = []
    tokens_historial = 0
    while texto := input("Cliente: ").strip():
        if len(historial) > MANTENER and tokens_historial > UMBRAL_TOKENS:
            antes = tokens_historial
            historial = compactar(historial)
            print(f"   (historial compactado; entrada previa: {antes} tokens)")
        historial.append({"role": "user", "content": texto})
        r = llm.messages.create(model=MODELO, max_tokens=800, system=SISTEMA, messages=historial)
        tokens_historial = r.usage.input_tokens + r.usage.output_tokens
        respuesta = "".join(b.text for b in r.content if b.type == "text")
        historial.append({"role": "assistant", "content": respuesta})
        print(f"Asistente: {respuesta}\n   [{r.usage.input_tokens} tokens de entrada en esta llamada]")
