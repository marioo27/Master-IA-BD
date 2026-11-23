# Entregable E4

## Requisitos

- P1: compactacion manual del historial.
- P2: hilos persistentes y preferencias aisladas por cliente.
- Ampliacion: borrado completo de preferencias e hilos.
- Pruebas en al menos dos sesiones.
- Apartado de privacidad RGPD.

## Puesta en marcha

Desde la raiz del repositorio:

```powershell
.\venv\Scripts\python.exe Practicas\S4\e4\pruebas.py
```

Para ejecutar P1:

```powershell
.\venv\Scripts\python.exe Practicas\S4\e4\s4_compactar.py
```

Para ejecutar P2:

```powershell
.\venv\Scripts\python.exe Practicas\S4\e4\s4_memoria_langchain.py 1 lunes
```

La ejecucion P1/P2 necesita variables `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL` y `ANTHROPIC_API_KEY` cargadas desde el entorno o desde `.env`, sin incluir el `.env` en Git.

## Pruebas funcionales

Ejecutar desde carpetas separadas para demostrar persistencia entre sesiones:

1. `1 lunes`: guardar preferencia estable.
2. Reiniciar y ejecutar otra vez `1 lunes`: comprobar continuidad.
3. `1 martes`: comprobar ausencia del hilo anterior y presencia de preferencias.
4. `2 lunes`: pedir preferencias del cliente 1 y comprobar denegacion/aislamiento.
5. `1 lunes`: pedir «olvidad mis datos» y comprobar borrado de ambos almacenes.
