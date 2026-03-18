export function showModal(id:string,html:string){const c=document.getElementById(id+"-c");const b=document.getElementById(id);if(c)c.innerHTML=html;if(b)b.classList.add("op")}
export function closeModal(id:string){const b=document.getElementById(id);if(b)b.classList.remove("op")}
export function initModals(){document.querySelectorAll<HTMLElement>(".mo-bg").forEach(b=>{b.addEventListener("click",e=>{if(e.target===b)b.classList.remove("op")})});document.addEventListener("keydown",e=>{if(e.key==="Escape")document.querySelectorAll<HTMLElement>(".mo-bg.op").forEach(b=>b.classList.remove("op"))})}
