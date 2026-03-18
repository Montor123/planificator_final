// TypeScript source reference. Browser loads compiled /static/js/app.js
// To recompile: npx tsc
import type { AppState, ScheduleResult } from "./types";
import { API } from "./api";
import { initModals } from "./windows";
let STATE:AppState|null=null;
let SCHEDULE:ScheduleResult|null=null;
async function init(){STATE=await API.getState();initModals();try{SCHEDULE=await API.getSchedule()}catch{}}
init();
