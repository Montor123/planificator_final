# Planificator v3.0

Planificador de cuadrantes. Backend Flask + Frontend HTML/TypeScript.

## Ejecutar

```bash
pip install flask pandas
python app.py
# http://localhost:5000
```

## Estructura

```
planificator/
├── app.py                  # Flask API REST
├── requirements.txt        # flask, pandas
├── domain/
│   ├── enums.py            # Temporalidad, TipoRestriccion, Severidad, FranjaTurno
│   └── models.py           # Servicio, Posicion, Turno, Empleado, Restriccion,
│                           # RestriccionEmpleado, AsignacionServicioEmpleado,
│                           # ConciliacionEmpleado, AsignacionTurno
├── services/
│   ├── shift_service.py    # Enriquecimiento turnos (sigla, duración, franja)
│   ├── employee_service.py # Disponibilidad
│   ├── demand_service.py   # Requisitos de demanda
│   ├── restriction_service.py  # Expansión diaria + severidad
│   ├── service_planning_service.py  # Validación servicios/turnos
│   ├── assignment_service.py  # Servicio por defecto
│   └── legal_rules_service.py # Normativa laboral
├── solver/
│   └── scheduler.py        # Greedy + conciliaciones + preferencias turno
├── repositories/
│   └── sqlite_repository.py
├── utils/
│   ├── validation.py       # parse_date, parse_time (HH:MM y HH:MM:SS)
│   ├── date_utils.py
│   └── export.py
├── static/
│   ├── index.html          # Frontend con sidebar lateral
│   ├── js/app.js           # JavaScript compilado
│   └── ts/                 # Fuentes TypeScript (types, api, windows, app)
├── tests/                  # test_api, test_scheduler, test_restrictions, test_sqlite
└── data/                   # SQLite auto-creada
```

## Funcionalidades

- **Menú lateral** con navegación por secciones
- **Cuadrante separado por servicios** con nombre + posición por fila
- **CRUDs completos**: Servicios, Posiciones, Turnos, Empleados, Catálogo, Restricciones
- **Asignación servicio-empleado**: matriz click para asignar/desasignar
- **Conciliaciones**: horarios por día de semana con vigencia
- **Edición manual**: clic en celda del cuadrante para cambiar turno
- **Restricciones con horas**: hora_dia suma al cómputo mensual
- **Validación límite**: error al exceder días máximos de restricción
- **Preferencia diurno/nocturno**: ~80% alineado, nunca 100%
- **Resúmenes**: por empleado y por servicio
