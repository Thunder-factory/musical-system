"""
Control de carga: cuántos jobs procesa el worker a la vez.

Sin esto, el threadpool de FastAPI dejaba correr ~40 basic-pitch en
paralelo y podía llenar la RAM. Con un límite, el job que sobra se rechaza
con 503 y Django lo reintenta más tarde (decisión 6 de
docs/ARQUITECTURA.md): es el equivalente a `prefetch=1` de una cola, pero
sin agregar un broker.

Es un contador con candado y no un `threading.Semaphore` porque /salud
necesita leer cuántos cupos hay ocupados, y el semáforo no lo expone.
"""

from __future__ import annotations

import threading


class ControlCapacidad:
    def __init__(self, capacidad: int) -> None:
        if capacidad <= 0:
            raise ValueError("La capacidad tiene que ser mayor que 0")
        self.capacidad = capacidad
        self._ocupados = 0
        self._candado = threading.Lock()

    @property
    def ocupados(self) -> int:
        return self._ocupados

    def intentar_ocupar(self) -> bool:
        """Toma un cupo si hay uno libre. Nunca espera: devuelve False si está lleno."""
        with self._candado:
            if self._ocupados >= self.capacidad:
                return False
            self._ocupados += 1
            return True

    def liberar(self) -> None:
        with self._candado:
            if self._ocupados == 0:
                raise RuntimeError("Se liberó un cupo que no estaba ocupado")
            self._ocupados -= 1
