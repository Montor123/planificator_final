from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional
from domain.enums import Severidad, Temporalidad, TipoRestriccion

@dataclass
class Servicio:
    id_servicio: int; nombre: str; area: str; centro_coste: str; activo: bool = True

@dataclass
class Posicion:
    id_posicion: int; id_servicio: int; nombre: str; activa: bool = True

@dataclass
class Turno:
    id_turno: int; id_posicion: int; nombre_turno: str; hora_inicio: time; hora_fin: time
    duracion_horas: float; dias_recurrencia: list[int]
    temporalidad: Temporalidad = Temporalidad.CONTINUO
    fecha_inicio: Optional[date] = None; fecha_fin: Optional[date] = None
    sigla_turno: Optional[str] = None; cruza_medianoche: bool = False
    grupo_rotacion: Optional[str] = None; es_indistinto: bool = False

@dataclass
class Empleado:
    id_empleado: int; nombre: str; activo: bool; fecha_alta: date
    fecha_baja: Optional[date] = None; area: Optional[str] = None
    centro_coste: Optional[str] = None; observaciones: Optional[str] = None
    horas_minimas: Optional[float] = None; horas_maximas: Optional[float] = None
    horas_objetivo: Optional[float] = None
    preferencia_turno: str = "indiferente"
    preferencias: dict[str, bool] = field(default_factory=dict)

@dataclass
class Restriccion:
    id_restriccion: int; dias: Optional[int]; desc_restriccion: str
    hora_dia: Optional[float]; siglas: Optional[str]
    tipo_restriccion: TipoRestriccion; severidad: Severidad
    es_laboral: bool; es_convenio: bool; activa: bool = True

@dataclass
class RestriccionEmpleado:
    id_empleado: int; id_restriccion: int; fecha: date
    hora_ini: Optional[time] = None; hora_fin: Optional[time] = None
    observaciones: Optional[str] = None

@dataclass
class AsignacionServicioEmpleado:
    id_empleado: int; id_servicio: int; es_principal: bool = False

@dataclass
class ConciliacionEmpleado:
    id_conciliacion: int; id_empleado: int; dia_semana: int
    hora_ini: time; hora_fin: time; fecha_ini: date; fecha_fin: date

@dataclass
class AsignacionTurno:
    id_planificacion: int; id_empleado: int; id_servicio: int; id_posicion: int
    fecha: date; turno_asignado: str; horas: float; es_off: bool = False
