import {Row,loadState} from './api';
type Tool={name:string;title:string;description:string;inputSchema:object;annotations:{readOnlyHint:boolean;untrustedContentHint:boolean};execute:(input:unknown)=>Promise<unknown>};
export function registerPortfolioTools(startReview:(state:Row,alert:Row)=>void){
 const context=(document as Document&{modelContext?:{registerTool:(tool:Tool,options:{signal:AbortSignal})=>void|Promise<void>}}).modelContext;
 if(!context?.registerTool)return;
 const lifecycle=new AbortController();
 const validate=(input:unknown,allowed:string[])=>{if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!allowed.includes(k)))throw Error('Input must be an object with only the documented properties.');return input as Row};
 const tools:Tool[]=[{
  name:'read_portfolio_intelligence',title:'Read portfolio intelligence',description:'Read the current local simulated portfolio, stock statuses, risk metrics and active alerts. All financial values are fictional. Does not change state or place orders.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},
  async execute(input){validate(input,[]);const d=await loadState();return {mode:d.mode,asof:d.asof,summary:d.summary,risk:d.risk,positions:d.positions.map((p:Row)=>({isin:p.isin,symbol:p.symbol,quantity:p.quantity,available:p.available,value:p.value,status:p.status})),alerts:d.alerts.filter((a:Row)=>a.status==='active').map((a:Row)=>({id:a.id,symbol:a.symbol,severity:a.severity,title:a.title,evidence:a.evidence}))}}
 },{
  name:'start_alert_review',title:'Open an alert for review',description:'Open the visible review dialog for an existing alert. This only opens the evidence and manual exit flow; it does not mark reviewed, preview, confirm or submit any order.',inputSchema:{type:'object',properties:{alertId:{type:'string'}},required:['alertId'],additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:true},
  async execute(input){const args=validate(input,['alertId']);if(typeof args.alertId!=='string')throw Error('alertId is required.');const d=await loadState();const alert=d.alerts.find((a:Row)=>a.id===args.alertId);if(!alert)throw Error('Alert not found.');startReview(d,alert);return {opened:true,alertId:alert.id,symbol:alert.symbol,orderSubmitted:false}}
 }];
 for(const tool of tools){try{Promise.resolve(context.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{/* UI remains available if the optional browser API fails. */})}catch{/* Optional API. */}}
 return ()=>lifecycle.abort();
}
