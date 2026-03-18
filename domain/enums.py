from __future__ import annotations
from enum import Enum

class Temporalidad(str, Enum):
    CONTINUO = "continuo"
    TEMPORAL = "temporal"

class TipoRestriccion(str, Enum):
    VACACIONES = "vacaciones"
    PERMISO = "permiso"
    BAJA_MEDICA = "baja_medica"
    DIA_LIBRE = "dia_libre"
    CONCILIACION = "conciliacion"
    LACTANCIA = "lactancia"
    JORNADA_REDUCIDA = "jornada_reducida"
    INDISPONIBILIDAD = "indisponibilidad"
    ASUNTO_PROPIO = "asunto_propio"
    MATRIMONIO = "matrimonio"
    HOSPITALIZACION = "hospitalizacion"
    FALLECIMIENTO = "fallecimiento"
    CAMBIO_DOMICILIO = "cambio_domicilio"
    FUERZA_MAYOR = "fuerza_mayor"
    SINDICAL = "sindical"
    SUFRAGIO = "sufragio"
    OTRO = "otro"

class Severidad(str, Enum):
    HARD = "HARD"
    SOFT_HIGH = "SOFT_HIGH"
    SOFT_MEDIUM = "SOFT_MEDIUM"
    SOFT_LOW = "SOFT_LOW"

class FranjaTurno(str, Enum):
    M = "M"
    T = "T"
    N = "N"

OFF_SHIFT = "OFF"
