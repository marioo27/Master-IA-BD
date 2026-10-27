"""Run the five experiments from Session 3, Practice 2."""
import argparse
import copy

from herramientas import DEFINICIONES, FUNCIONES
from s3_agente import Agente, Herramienta, SISTEMA


CORREO_AVERIA_Y_PEDIDO = (
    "Buenas, os escribo del Restaurante Lumbre. La cafetera de dos grupos no "
    "calienta y hoy no podemos servir cafés. ¿Además, cuándo llega el pedido pendiente?"
)

EXPERIMENTOS = {
    1: "Run the example email and observe tool calls, priority, and final response.",
    2: "Run the example email with max_pasos=2 and observe how the agent stops.",
    3: "Reject the create_incidencia approval with 'n' and observe the response.",
    4: "Ask about August maintenance after removing the incident-use restriction.",
    5: "Run the example email without the system instruction to identify the customer first.",
}


def configurar_experimento(numero: int) -> tuple[str, list[dict], int, str]:
    definiciones = copy.deepcopy(DEFINICIONES)
    sistema = SISTEMA
    max_pasos = 8
    objetivo = CORREO_AVERIA_Y_PEDIDO

    if numero == 2:
        max_pasos = 2
    elif numero == 4:
        herramienta = next(d for d in definiciones if d["name"] == "crear_incidencia")
        herramienta["description"] = herramienta["description"].replace(
            " Úsala solo si el cliente describe una avería concreta.", "")
        objetivo = "¿Revisáis las máquinas en agosto?"
    elif numero == 5:
        sistema = sistema.replace(
            "1. Identifica al cliente con buscar_cliente antes de usar su id.\n", "")

    return sistema, definiciones, max_pasos, objetivo


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Session 3, Practice 2 experiment.")
    parser.add_argument("experimento", type=int, choices=EXPERIMENTOS)
    numero = parser.parse_args().experimento

    sistema, definiciones, max_pasos, objetivo = configurar_experimento(numero)
    herramientas = [
        Herramienta(
            definicion["name"], definicion["description"], definicion["parameters"],
            FUNCIONES[definicion["name"]],
            requiere_aprobacion=(definicion["name"] == "crear_incidencia"),
        )
        for definicion in definiciones
    ]

    print(f"Experimento {numero}: {EXPERIMENTOS[numero]}")
    if numero == 3:
        print("Cuando se solicite aprobación para crear_incidencia, responde n.")
    if numero == 4:
        print("Si propone una incidencia preventiva, responde n para no guardarla en la BD.")
    print(Agente(sistema, herramientas, max_pasos=max_pasos).ejecutar(objetivo))


if __name__ == "__main__":
    main()