export type Row = Record<string, any>;
let token = '';
export async function loadState(): Promise<Row> {
  const response = await fetch('/api/state');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Could not load portfolio.');
  token = data.sessionToken; return data;
}
export async function post(path: string, body: Row = {}): Promise<any> {
  const response = await fetch(`/api/${path}`, {method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':token},body:JSON.stringify(body)});
  const data=await response.json(); if(!response.ok) throw new Error(data.error || 'Could not save.'); return data;
}
export const money=(value:number, compact=false)=>compact&&Math.abs(value)>=100000?`₹${(value/100000).toFixed(2)}L`:new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(value);
export const number=(value:number|null, digits=2)=>value==null?'Unavailable':new Intl.NumberFormat('en-IN',{maximumFractionDigits:digits}).format(value);
export const severityLabel: Record<string,string>={info:'Info',watch:'Watch',warning:'Warning',exit_review:'Exit review',hard_exit:'Hard exit',healthy:'Healthy'};
export const dateTime=(value:string)=>new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
