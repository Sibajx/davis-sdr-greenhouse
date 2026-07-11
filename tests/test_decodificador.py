"""
Pruebas unitarias para las funciones puras de decodificación de
davis_monitor.py (DecodificadorDavis).

Nota: importar davis_monitor.py ejecuta algunas líneas a nivel de módulo
(crea ~/capturas_davis/ y configura logging a archivo). Esto es un efecto
secundario conocido del script original y no afecta el resultado de estas
pruebas, pero sería deseable refactorizarlo en el futuro para separar
configuración de lógica pura (ver README, sección "Mejoras recomendadas").
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from davis_monitor import DecodificadorDavis  # noqa: E402


class TestValidarCRC:
    def test_trama_valida_es_aceptada(self):
        # payload de 6 bytes + CRC-16/CCITT (poly 0x1021, init 0) calculado
        # correctamente para ese payload.
        trama_valida = "8000641234569962"
        assert DecodificadorDavis.validar_crc(trama_valida) is True

    def test_trama_corrupta_es_rechazada(self):
        # mismo CRC que la trama válida, pero con un byte de payload alterado
        trama_corrupta = "8000641234579962"
        assert DecodificadorDavis.validar_crc(trama_corrupta) is False

    def test_trama_demasiado_corta_es_rechazada(self):
        assert DecodificadorDavis.validar_crc("8000") is False

    def test_hex_invalido_no_lanza_excepcion(self):
        # cadena no hexadecimal: debe regresar False, no lanzar excepción
        assert DecodificadorDavis.validar_crc("no_es_hex") is False

    def test_cadena_vacia_es_rechazada(self):
        assert DecodificadorDavis.validar_crc("") is False


class TestGradosACardinal:
    def test_norte(self):
        assert DecodificadorDavis.grados_a_cardinal(0) == "N"

    def test_este(self):
        assert DecodificadorDavis.grados_a_cardinal(90) == "E"

    def test_sur(self):
        assert DecodificadorDavis.grados_a_cardinal(180) == "S"

    def test_oeste(self):
        assert DecodificadorDavis.grados_a_cardinal(270) == "W"

    def test_envuelve_a_360_grados(self):
        # 360 grados debe envolver de regreso a "N" (index % 16)
        assert DecodificadorDavis.grados_a_cardinal(360) == "N"
