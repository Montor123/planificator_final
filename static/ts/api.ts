import type { AppState, ScheduleResult, AsignacionServicioEmpleado, ConciliacionEmpleado, ResumenEmpleado, ResumenServicio } from "./types";
export async function apiFetch<T>(path:string,opts:{method?:string;body?:unknown}={}):Promise<T>{
  const res=await fetch(path,{method:opts.method||"GET",headers:{"Content-Type":"application/json"},body:opts.body?JSON.stringify(opts.body):undefined});
  if(!res.ok){const e=await res.json().catch(()=>({}));throw new Error((e as any).error||res.statusText)}
  return res.json() as Promise<T>;
}
export const API={
  getState:()=>apiFetch<AppState>("/api/state"),
  resetState:()=>apiFetch<AppState>("/api/reset",{method:"POST"}),
  addServicio:(b:any)=>apiFetch<any>("/api/servicios",{method:"POST",body:b}),
  delServicio:(id:number)=>apiFetch<any>(`/api/servicios/${id}`,{method:"DELETE"}),
  addPosicion:(b:any)=>apiFetch<any>("/api/posiciones",{method:"POST",body:b}),
  delPosicion:(id:number)=>apiFetch<any>(`/api/posiciones/${id}`,{method:"DELETE"}),
  addTurno:(b:any)=>apiFetch<any>("/api/turnos",{method:"POST",body:b}),
  delTurno:(id:number)=>apiFetch<any>(`/api/turnos/${id}`,{method:"DELETE"}),
  addEmpleado:(b:any)=>apiFetch<any>("/api/empleados",{method:"POST",body:b}),
  delEmpleado:(id:number)=>apiFetch<any>(`/api/empleados/${id}`,{method:"DELETE"}),
  addCatalogo:(b:any)=>apiFetch<any>("/api/catalogo",{method:"POST",body:b}),
  delCatalogo:(id:number)=>apiFetch<any>(`/api/catalogo/${id}`,{method:"DELETE"}),
  assignRestriccion:(b:any)=>apiFetch<any>("/api/restricciones",{method:"POST",body:b}),
  delRestriccion:(b:any)=>apiFetch<any>("/api/restricciones/delete",{method:"POST",body:b}),
  toggleAsig:(b:any)=>apiFetch<any>("/api/asignaciones_servicio/toggle",{method:"POST",body:b}),
  addConciliacion:(b:any)=>apiFetch<any>("/api/conciliaciones",{method:"POST",body:b}),
  delConciliacion:(id:number)=>apiFetch<any>(`/api/conciliaciones/${id}`,{method:"DELETE"}),
  generar:(b:any)=>apiFetch<ScheduleResult>("/api/generar",{method:"POST",body:b}),
  getSchedule:()=>apiFetch<ScheduleResult>("/api/schedule"),
  editCell:(b:any)=>apiFetch<any>("/api/schedule/edit",{method:"POST",body:b}),
  resumenEmpleado:(id:number)=>apiFetch<ResumenEmpleado>(`/api/resumen/empleado/${id}`),
  resumenServicio:(id:number)=>apiFetch<ResumenServicio>(`/api/resumen/servicio/${id}`),
};
