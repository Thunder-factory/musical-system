import threading

import pytest

from app.capacidad import ControlCapacidad


def test_ocupa_hasta_la_capacidad_y_despues_rechaza():
    control = ControlCapacidad(2)

    assert control.intentar_ocupar()
    assert control.intentar_ocupar()
    assert not control.intentar_ocupar()
    assert control.ocupados == 2


def test_liberar_devuelve_el_cupo():
    control = ControlCapacidad(1)
    control.intentar_ocupar()

    control.liberar()

    assert control.ocupados == 0
    assert control.intentar_ocupar()


def test_liberar_sin_ocupar_es_un_error():
    with pytest.raises(RuntimeError):
        ControlCapacidad(1).liberar()


def test_capacidad_cero_no_se_permite():
    with pytest.raises(ValueError):
        ControlCapacidad(0)


def test_con_muchos_hilos_a_la_vez_nunca_supera_la_capacidad():
    control = ControlCapacidad(3)
    exitos: list[bool] = []
    barrera = threading.Barrier(50)

    def intentar():
        barrera.wait()
        exitos.append(control.intentar_ocupar())

    hilos = [threading.Thread(target=intentar) for _ in range(50)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert exitos.count(True) == 3
    assert control.ocupados == 3
