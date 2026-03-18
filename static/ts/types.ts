export interface Servicio { id_servicio:number; nombre:string; area:string; centro_coste:string; activo:boolean }
export interface Posicion { id_posicion:number; id_servicio:number; nombre:string; activa:boolean }
export interface Turno { id_turno:number; id_posicion:number; nombre_turno:string; hora_inicio:string; hora_fin:string; duracion_horas:number; dias_recurrencia:number[]; temporalidad:"continuo"|"temporal"; fecha_inicio:string|null; fecha_fin:string|null; sigla_turno:string|null; cruza_medianoche:boolean }
export interface Empleado { id_empleado:number; nombre:string; activo:boolean; fecha_alta:string; fecha_baja:string|null; horas_minimas:number|null; horas_maximas:number|null; horas_objetivo:number|null; preferencia_turno:"diurno"|"nocturno"|"indiferente"; preferencias:Record<string,boolean> }
export interface Restriccion { id_restriccion:number; dias:number|null; desc_restriccion:string; hora_dia:number|null; siglas:string|null; tipo_restriccion:string; severidad:"HARD"|"SOFT_HIGH"|"SOFT_MEDIUM"|"SOFT_LOW"; es_laboral:boolean; es_convenio:boolean; activa:boolean }
export interface RestriccionEmpleado { id_empleado:number; id_restriccion:number; fecha:string; hora_ini:string|null; hora_fin:string|null; observaciones:string|null }
export interface AsignacionServicioEmpleado { id_empleado:number; id_servicio:number; es_principal:boolean }
export interface ConciliacionEmpleado { id_conciliacion:number; id_empleado:number; dia_semana:number; hora_ini:string; hora_fin:string; fecha_ini:string; fecha_fin:string }
export interface AppState { servicios:Servicio[]; posiciones:Posicion[]; turnos:Turno[]; empleados:Empleado[]; catalogo:Record<string,Restriccion>; restricciones_empleado:RestriccionEmpleado[]; asignaciones_servicio:AsignacionServicioEmpleado[]; conciliaciones:ConciliacionEmpleado[] }
export interface CellData { turno:string; horas:number; es_off:boolean }
export interface EmployeeGrid { nombre:string; posicion:string; days:Record<string,CellData> }
export interface ServiceGrid { nombre:string; employees:Record<string,EmployeeGrid> }
export interface HourSummary { id:number; nombre:string; horas_trabajo:number; horas_restriccion:number; horas_total:number; objetivo:number; diff:number }
export interface ScheduleResult { grids:Record<string,ServiceGrid>; dates:string[]; hours:HourSummary[]; summary:{faltantes:number;total:number} }
export interface ResumenEmpleado { horas_trabajo:number; horas_restriccion:number; horas_total:number; dias_off:number; dias_restriccion:number; turnos_count:Record<string,number> }
export interface ResumenServicio { servicio:string; empleados:Record<string,number>; turnos_count:Record<string,number>; total_horas:number }
