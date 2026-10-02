"""Rebuild fictional, reproducible demo data. Never downloads market data."""
import json, math
from datetime import date, timedelta
from pathlib import Path

def leaf(metric, op, value=None, rhs=None, periods=1):
    return {'metric': metric, 'op': op, **({'rhsMetric': rhs} if rhs else {'value': value}), 'periods': periods}

def build_seed():
    specs = [
        ('INE002A01018','RELIANCE','Reliance Industries','Energy','Large cap',1468,0.07,0,17.6,18.4,17.2),
        ('INE040A01034','HDFCBANK','HDFC Bank','Financials','Large cap',982,0.10,0.025,14.8,None,None),
        ('INE467B01029','TCS','Tata Consultancy Services','Information Technology','Large cap',3284,0.12,0.21,4.2,21.3,47.8),
        ('INE009A01021','INFY','Infosys','Information Technology','Large cap',1692,0.09,0.06,11.2,22.1,32.6),
        ('INE062A01020','SBIN','State Bank of India','Financials','Large cap',814,0.11,0,16.1,None,None),
        ('INE585B01010','MARUTI','Maruti Suzuki','Automobiles','Large cap',12840,0.10,0,18.4,13.8,22.1),
        ('INE040H01021','SUZLON','Suzlon Energy','Industrials','Small cap',62.4,0.22,0.24,7.8,12.4,14.2),
        ('INE021A01026','ASIANPAINT','Asian Paints','Consumer','Large cap',2892,0.07,0.02,12.8,20.4,29.6),
    ]
    asof = '2026-10-01'; days=[]; d=date.fromisoformat(asof)
    while len(days)<330:
        if d.weekday()<5: days.append(d.isoformat())
        d-=timedelta(days=1)
    days.reverse(); securities=[]
    for idx,(isin,symbol,name,sector,cap,price,trend,drop,growth,margin,roce) in enumerate(specs):
        raw=[]
        for i,day in enumerate(days):
            shape=1+trend*i/329+0.019*math.sin(i/14+idx)+0.008*math.sin(i/4)
            if i>305: shape*=1-drop*(i-305)/24
            raw.append(shape)
        bars=[{'date':day,'close':round(raw[i]/raw[-1]*price,2),'volume':int(1100000*(1+0.2*math.sin(i/6+idx))*(2.8 if i>=328 and symbol in ('TCS','SUZLON') else 1)),'complete':True} for i,day in enumerate(days)]
        fundamentals=[]
        for q,(period,published) in enumerate([('2026-06-30','2026-08-05'),('2026-03-31','2026-05-10'),('2025-12-31','2026-02-07'),('2025-09-30','2025-11-05')]):
            g=growth+(1.8*q if symbol in ('TCS','SUZLON') else q*0.4); isbank=sector=='Financials'
            fundamentals.append({'period':period,'publishedAt':published,'revenue_growth':round(g,2),'revenue_cr':round(price*17,1),'ebitda_margin':round(margin+q*0.8,2) if margin else None,'pat_growth':round(g-3,2),'roce':roce,'roe':16.8+idx,'debt_equity':None if isbank else (1.7 if symbol=='SUZLON' else 0.24),'net_debt_ebitda':None if isbank else 0.8,'interest_coverage':None if isbank else 8.2,'cfo_pat':None if isbank else (0.55 if symbol=='SUZLON' else 1.15),'cfo_cr':None if isbank else price*2.7,'fcf_cr':None if isbank else (-120 if symbol=='SUZLON' else price*1.2),'promoter_pledge':7.2 if symbol=='SUZLON' else 0,'promoter_holding':(15.1+q*0.5) if symbol=='SUZLON' else (0 if isbank else 51.2)})
        securities.append({'isin':isin,'symbol':symbol,'name':name,'sector':sector,'marketCap':cap,'bars':bars,'fundamentals':fundamentals,'events':[{'type':'guidance_cut','date':'2026-09-28','title':'Fictional guidance reduction for demo','source':'Synthetic exchange-event fixture'}] if symbol=='TCS' else [],'source':'Synthetic fixture · NOT live market data'})
    accounts=[{'id':'zerodha','name':'Zerodha','account':'•• 4821','demat':'DEMO-CDSL-4821','status':'Mock connected'},{'id':'icici','name':'ICICI Direct','account':'•• 9074','demat':'DEMO-NSDL-9074','status':'Mock connected'},{'id':'groww','name':'Groww','account':'•• 2638','demat':'DEMO-CDSL-2638','status':'Mock connected'}]
    lots=[(0,'zerodha',500,1280,50,0,0),(0,'icici',250,1330,0,0,0),(1,'zerodha',650,840,0,0,0),(1,'icici',450,892,0,20,0),(2,'zerodha',120,3640,0,0,0),(2,'icici',80,3510,0,0,0),(2,'groww',40,3420,0,0,5),(3,'groww',270,1550,0,0,0),(4,'icici',650,720,0,0,0),(5,'zerodha',35,11120,0,0,0),(6,'groww',4000,54,500,100,0),(6,'zerodha',1200,58,0,0,0),(7,'icici',150,2630,0,0,0)]
    holdings=[{'isin':specs[i][0],'account_id':a,'quantity':q,'avg_cost':cost,'pledged':pl,'blocked':bl,'unsettled':u} for i,a,q,cost,pl,bl,u in lots]
    rules=[]
    def add(id,name,condition,severity='warning',scope='stock',isin='*'):
        rules.append({'id':id,'name':name,'condition':condition,'severity':severity,'scope':scope,'isin':isin,'enabled':True,'version':1})
    add('trend-200','Two closes below 200 DMA',leaf('close','lt',rhs='dma200',periods=2),'exit_review')
    add('growth','Revenue growth below 10% for 2 quarters',leaf('revenue_growth','lt',10,periods=2))
    add('volume-break','Breakdown with elevated volume',{'all':[leaf('close','lt',rhs='dma50'),leaf('volume_ratio','gt',1.5)]},'exit_review')
    add('drawdown','Drawdown exceeds 18%',leaf('drawdown_pct','gt',18),'exit_review')
    add('pledge','Promoter pledge exceeds 5%',leaf('promoter_pledge','gt',5))
    add('guidance','Guidance cut reported',leaf('event.guidance_cut','eq',1),'watch')
    add('weekly','Weekly close below 40-week MA',leaf('weekly_close','lt',rhs='wma40'),'warning')
    add('concentration','Single stock exceeds 20% of equity',leaf('max_stock_weight','gt',20),'warning','portfolio')
    add('sector','Sector exceeds 35% of equity',leaf('max_sector_weight','gt',35),'watch','portfolio')
    add('exposure','More than 30% of equity below 200 DMA',leaf('below200_pct','gt',30),'warning','portfolio')
    theses={s['isin']:f"Hold {s['name']} while the long-term growth case remains intact. Review quarterly results and material events; use price trends as a prompt to revisit the thesis." for s in securities}
    theses[specs[2][0]]='Expect double-digit revenue growth with EBITDA margins above 22%. Retain while cash generation and the long-term trend hold. Reassess on two weak quarters or a sustained 200 DMA breakdown.'
    return {'asof':asof,'mode':'simulation','cash':180000,'accounts':accounts,'securities':securities,'holdings':holdings,'rules':rules,'theses':theses}

if __name__ == '__main__':
    path=Path(__file__).resolve().parents[1]/'data'/'seed.json'
    path.write_text(json.dumps(build_seed(),indent=2)+'\n'); print(f'Wrote {path}')
