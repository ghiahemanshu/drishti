"""SQLite application service. Every write and simulated fill is transactional."""
import json, sqlite3, uuid, time, hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .engine import catalog, evaluate, metric_value, validate_rule, SEVERITIES, METRICS, valid_bars
from .adapters import MockHoldingsAdapter, MockMarketDataAdapter, MockExecutionAdapter

ROOT = Path(__file__).resolve().parents[1]
def dumps(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())

class AppError(Exception):
    def __init__(self, message, status=400): self.message, self.status = message, status; super().__init__(message)

class Store:
    def __init__(self, path=None, seed=None):
        self.path = str(path or ROOT/'data'/'portfolio.sqlite')
        self.seed = seed or json.loads((ROOT/'data'/'seed.json').read_text())
        self.holdings_adapter=MockHoldingsAdapter(); self.market_adapter=MockMarketDataAdapter(); self.execution_adapter=MockExecutionAdapter()
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS holdings(account_id TEXT NOT NULL, isin TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>=0), avg_cost REAL NOT NULL, pledged INTEGER NOT NULL CHECK(pledged>=0), blocked INTEGER NOT NULL CHECK(blocked>=0), unsettled INTEGER NOT NULL CHECK(unsettled>=0), PRIMARY KEY(account_id,isin), CHECK(quantity>=pledged+blocked+unsettled));
            CREATE TABLE IF NOT EXISTS rules(id TEXT PRIMARY KEY, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS theses(isin TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, target TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0, record TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_active ON alerts(rule_id,target,version) WHERE status='active';
            CREATE TABLE IF NOT EXISTS previews(id TEXT PRIMARY KEY, isin TEXT NOT NULL, status TEXT NOT NULL, expires REAL NOT NULL, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS executions(id TEXT PRIMARY KEY, preview_id TEXT NOT NULL UNIQUE, idempotency_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, details TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'Audit log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'Audit log is append-only'); END;
            ''')
            if not db.execute("SELECT 1 FROM meta WHERE key='dataset'").fetchone():
                self._put(db,'dataset',{k:v for k,v in self.seed.items() if k not in ('holdings','rules','theses')}); self._put(db,'cash',self.seed['cash']); self._put(db,'revision',1)
                for h in self.seed['holdings']:
                    db.execute('INSERT INTO holdings VALUES(?,?,?,?,?,?,?)',tuple(h[k] for k in ('account_id','isin','quantity','avg_cost','pledged','blocked','unsettled')))
                for r in self.seed['rules']: validate_rule(r); db.execute('INSERT INTO rules VALUES(?,?)',(r['id'],dumps(r)))
                for isin,body in self.seed['theses'].items(): db.execute('INSERT INTO theses VALUES(?,?)',(isin,body))
                self._audit(db,'DEMO_INITIALISED','portfolio',{'source':'Fictional seed data','mode':'simulation'})
            self._scan(db)

    @contextmanager
    def connection(self, write=True):
        db=sqlite3.connect(self.path,timeout=10); db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA journal_mode=WAL')
        try:
            if write: db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback(); raise
        finally: db.close()

    def _get(self,db,key): return json.loads(db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()[0])
    def _put(self,db,key,value): db.execute('INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,dumps(value)))
    def _bump(self,db): self._put(db,'revision',self._get(db,'revision')+1)
    def _audit(self,db,action,target,details): db.execute('INSERT INTO audit(at,action,target,details) VALUES(?,?,?,?)',(now(),action,target,dumps(details)))
    def _rules(self,db): return [json.loads(r[0]) for r in db.execute('SELECT record FROM rules ORDER BY id')]
    def _dataset(self,db): return self.market_adapter.snapshot(self._get(db,'dataset'))

    def _positions(self,db,dataset):
        positions=[]; lots=[h for a in dataset['accounts'] for h in self.holdings_adapter.fetch_holdings(db,a['id'])]
        for s in dataset['securities']:
            accounts=[dict(h,available=h['quantity']-h['pledged']-h['blocked']-h['unsettled']) for h in lots if h['isin']==s['isin'] and h['quantity']>0]
            qty=sum(a['quantity'] for a in accounts)
            if not qty: continue
            price=metric_value('close',s,dataset['asof'])[0]
            valuation_stale = price is None
            if price is None:
                history = valid_bars(s, dataset['asof'])
                price = history[-1]['close'] if history else 0
            cost=sum(a['quantity']*a['avg_cost'] for a in accounts); value=qty*price
            positions.append({**{k:v for k,v in s.items() if k not in ('bars','fundamentals','events')},'quantity':qty,'valuationStale':valuation_stale,'available':sum(a['available'] for a in accounts),'accounts':accounts,'price':price,'value':round(value,2),'cost':round(cost,2),'avgCost':cost/qty,'pnl':round(value-cost,2),'pnlPct':(value-cost)/cost*100 if cost else 0,'sparkline':[b['close'] for b in s['bars'][-60:]],'metrics':{k:metric_value(k,s,dataset['asof'])[0] for k in METRICS if METRICS[k][2] not in ('portfolio','event')}})
        total=sum(p['value'] for p in positions)
        for p in positions: p['weight']=p['value']/total*100 if total else 0
        return positions

    def _compute(self,db):
        dataset=self._dataset(db); positions=self._positions(db,dataset); rules=self._rules(db); evaluations=[]; total=sum(p['value'] for p in positions); sectors={}; cash=self._get(db,'cash')
        byisin={s['isin']:s for s in dataset['securities']}
        for p in positions:
            sectors[p['sector']]=sectors.get(p['sector'],0)+p['value']
            for r in rules:
                if r['enabled'] and r['scope']=='stock' and r['isin'] in ('*',p['isin']):
                    evidence=evaluate(r['condition'],byisin[p['isin']],dataset['asof'])
                    evaluations.append({'ruleId':r['id'],'version':r['version'],'target':p['isin'],'symbol':p['symbol'],'title':r['name'],'severity':r['severity'],'evidence':evidence,'matched':evidence['matched'],'asof':dataset['asof']})
            current=[e for e in evaluations if e['target']==p['isin']]; breaches=[e for e in current if e['matched'] is True]; p['breaches']=len(breaches); p['unknowns']=sum(e['matched'] is None for e in current)
            severity=max([SEVERITIES.index(e['severity']) for e in breaches],default=-1)
            p['status']='Unmonitored' if not current else 'Action required' if severity>=3 else 'Warning' if severity==2 else 'Watch' if severity>=0 else 'Data gap' if p['unknowns'] else 'Healthy'
            p['severity']=SEVERITIES[severity] if severity>=0 else 'watch' if p['unknowns'] else 'resolved' if not current else 'healthy'
        portfolio={'max_stock_weight':max([p['weight'] for p in positions],default=0),'max_sector_weight':max(sectors.values(),default=0)/total*100 if total else 0,'smallcap_pct':sum(p['value'] for p in positions if p['marketCap']=='Small cap')/total*100 if total else 0,'below200_pct':None if any(p['metrics']['dma200'] is None for p in positions) else sum(p['value'] for p in positions if p['price']<p['metrics']['dma200'])/total*100 if total else 0,'warning_pct':sum(p['value'] for p in positions if p['status'] in ('Warning','Action required'))/total*100 if total else 0,'cash_pct':cash/(total+cash)*100 if total+cash else 0}
        for r in rules:
            if r['enabled'] and r['scope']=='portfolio':
                evidence=evaluate(r['condition'],{},dataset['asof'],portfolio)
                evaluations.append({'ruleId':r['id'],'version':r['version'],'target':'portfolio','symbol':'Portfolio','title':r['name'],'severity':r['severity'],'evidence':evidence,'matched':evidence['matched'],'asof':dataset['asof']})
        return dataset,positions,rules,evaluations,portfolio,sectors

    def _scan(self,db):
        _,_,_,evaluations,_,_=self._compute(db)
        active={(r['rule_id'],r['target'],r['version']):dict(r) for r in db.execute("SELECT * FROM alerts WHERE status='active'")}; seen=set()
        for e in evaluations:
            key=(e['ruleId'],e['target'],e['version']); seen.add(key); old=active.get(key)
            if e['matched'] is True and not old:
                aid=uid(); stamp=now()
                db.execute('INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?)',(aid,*key,'active',stamp,stamp,0,dumps(e)))
                self._audit(db,'ALERT_TRIGGERED',e['target'],{'alertId':aid,**e})
            elif old and e['matched'] is not False:
                db.execute('UPDATE alerts SET record=?,updated_at=? WHERE id=?',(dumps(e),now(),old['id']))
            elif old:
                db.execute("UPDATE alerts SET status='resolved',updated_at=? WHERE id=?",(now(),old['id']))
                self._audit(db,'ALERT_RESOLVED',e['target'],{'alertId':old['id'],'reason':'Condition cleared'})
        for key,old in active.items():
            if key not in seen:
                db.execute("UPDATE alerts SET status='resolved',updated_at=? WHERE id=?",(now(),old['id']))
                self._audit(db,'ALERT_RESOLVED',old['target'],{'alertId':old['id'],'reason':'Rule changed, disabled, or position closed'})
        self._put(db,'lastScan',now())
        return evaluations

    def scan(self,manual=True):
        with self.connection() as db:
            result=self._scan(db)
            if manual: self._audit(db,'SCAN_COMPLETED','portfolio',{'evaluations':len(result),'breaches':sum(e['matched'] is True for e in result)})
        return {'ok':True}

    def snapshot(self):
        with self.connection(False) as db:
            dataset,positions,rules,evaluations,portfolio,sectors=self._compute(db)
            alerts=[{**json.loads(r['record']),**{k:r[k] for k in ('id','status','created_at','updated_at','acknowledged')}} for r in db.execute('SELECT * FROM alerts ORDER BY created_at DESC')]
            alerts.sort(key=lambda a:(a['status']=='active',SEVERITIES.index(a['severity'])),reverse=True)
            total=sum(p['value'] for p in positions); cost=sum(p['cost'] for p in positions)
            return {'mode':'simulation','asof':dataset['asof'],'lastScan':self._get(db,'lastScan'),'revision':self._get(db,'revision'),'accounts':dataset['accounts'],'positions':positions,'rules':rules,'alerts':alerts,'evaluations':evaluations,'metricsCatalog':catalog(),'risk':portfolio,'sectors':[{'name':k,'value':v,'weight':v/total*100 if total else 0} for k,v in sorted(sectors.items(),key=lambda x:-x[1])],'summary':{'equity':total,'cash':self._get(db,'cash'),'cost':cost,'pnl':total-cost,'pnlPct':(total-cost)/cost*100 if cost else 0,'actionPositions':sum(p['status']=='Action required' for p in positions),'unknowns':sum(e['matched'] is None for e in evaluations)},'theses':dict(db.execute('SELECT isin,body FROM theses')),'executions':[json.loads(r[0]) for r in db.execute('SELECT record FROM executions ORDER BY created_at DESC')],'audit':[{**dict(r),'details':json.loads(r['details'])} for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 250')]}

    def security(self,isin):
        with self.connection(False) as db:
            s=next((s for s in self._dataset(db)['securities'] if s['isin']==isin),None)
            if not s: raise AppError('Security not found.',404)
            return s

    def save_thesis(self,isin,body):
        if not isinstance(body,str) or len(body)>5000: raise AppError('Thesis must be text of at most 5,000 characters.')
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM theses WHERE isin=?',(isin,)).fetchone(): raise AppError('Security not found.',404)
            old=db.execute('SELECT body FROM theses WHERE isin=?',(isin,)).fetchone()[0]
            db.execute('UPDATE theses SET body=? WHERE isin=?',(body,isin)); self._audit(db,'THESIS_UPDATED',isin,{'before':old,'after':body})
        return {'ok':True}

    def save_rule(self,rule):
        try: validate_rule(rule)
        except (ValueError,TypeError) as e: raise AppError(str(e))
        with self.connection() as db:
            dataset=self._dataset(db)
            if rule.get('isin') not in ['*']+[s['isin'] for s in dataset['securities']]: raise AppError('Unknown security.')
            rid=rule.get('id') or uid(); row=db.execute('SELECT record FROM rules WHERE id=?',(rid,)).fetchone(); old=json.loads(row[0]) if row else None
            if old and rule.get('version')!=old['version']: raise AppError('This rule changed. Refresh and try again.',409)
            saved={k:rule[k] for k in ('name','scope','isin','condition','severity','enabled')}; saved.update(id=rid,version=old['version']+1 if old else 1)
            db.execute('INSERT INTO rules VALUES(?,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record',(rid,dumps(saved)))
            self._bump(db); self._audit(db,'RULE_UPDATED' if old else 'RULE_CREATED',rid,{'before':old,'after':saved}); self._scan(db)
            return saved

    def acknowledge(self,aid):
        with self.connection() as db:
            a=db.execute('SELECT * FROM alerts WHERE id=?',(aid,)).fetchone()
            if not a: raise AppError('Alert not found.',404)
            if not a['acknowledged']:
                db.execute('UPDATE alerts SET acknowledged=1 WHERE id=?',(aid,)); self._audit(db,'ALERT_REVIEWED',aid,{})
        return {'ok':True}

    def preview(self,body):
        if type(body.get('percent')) is not int or body['percent'] not in (25,50,100): raise AppError('Choose an exit of 25%, 50%, or 100%.')
        with self.connection() as db:
            self._scan(db)
            alert=db.execute("SELECT * FROM alerts WHERE id=? AND status='active'",(body.get('alertId'),)).fetchone()
            if not alert: raise AppError('Select an active stock alert to review an exit.',409)
            record=json.loads(alert['record'])
            if alert['target']=='portfolio' or record['matched'] is not True: raise AppError('Only an active, evaluable stock alert can start an exit.',409)
            dataset=self._dataset(db); positions=self._positions(db,dataset); p=next((p for p in positions if p['isin']==alert['target']),None)
            if not p: raise AppError('No holding remains.',409)
            if p['valuationStale']: raise AppError('Current price is unavailable. An exit cannot be previewed.',409)
            account_ids=body.get('accountIds',[a['account_id'] for a in p['accounts']])
            if not isinstance(account_ids,list) or not account_ids or len(account_ids)!=len(set(account_ids)) or any(a not in [h['account_id'] for h in p['accounts']] for a in account_ids): raise AppError('Choose valid accounts without duplicates.')
            lots=[a for a in p['accounts'] if a['account_id'] in account_ids]; total=sum(a['quantity'] for a in lots); available=sum(a['available'] for a in lots); requested=total*body['percent']//100; qty=min(requested,available)
            if not qty: raise AppError('There are no whole, sellable shares for this selection.',409)
            allocation=[dict(a,sellQuantity=qty*a['available']//available) for a in lots]
            remainder=qty-sum(a['sellQuantity'] for a in allocation)
            ranked=sorted(allocation,key=lambda a:(-(qty*a['available']%available),a['account_id']))
            for a in ranked[:remainder]: a['sellQuantity']+=1
            revision=self._get(db,'revision'); fingerprint=hashlib.sha256(dumps({'alert':alert['id'],'percent':body['percent'],'accounts':sorted(account_ids),'revision':revision}).encode()).hexdigest()
            for row in db.execute("SELECT record FROM previews WHERE status='pending' AND expires>?",(time.time(),)):
                existing=json.loads(row[0])
                if existing['fingerprint']==fingerprint: return existing
            preview={'id':uid(),'fingerprint':fingerprint,'revision':revision,'alertId':alert['id'],'ruleVersion':alert['version'],'isin':p['isin'],'symbol':p['symbol'],'percent':body['percent'],'quantity':qty,'requestedQuantity':requested,'heldQuantity':total,'availableQuantity':available,'excludedQuantity':total-available,'remainingQuantity':total-qty,'price':p['price'],'estimatedProceeds':round(qty*p['price'],2),'orderType':'MARKET','mode':'simulation','accounts':allocation,'expiresAt':time.time()+300,'asof':dataset['asof'],'createdAt':now(),'evidence':record}
            db.execute('INSERT INTO previews VALUES(?,?,?,?,?)',(preview['id'],p['isin'],'pending',preview['expiresAt'],dumps(preview)))
            self._audit(db,'ORDER_PREVIEWED',p['isin'],preview)
            return preview

    def confirm(self,body):
        if body.get('confirmed') is not True: raise AppError('Explicit user confirmation is required.')
        pid,key=body.get('previewId'),body.get('idempotencyKey')
        if not isinstance(key,str) or not 8<=len(key)<=100: raise AppError('A valid idempotency key is required.')
        with self.connection() as db:
            previous=db.execute('SELECT * FROM executions WHERE idempotency_key=? OR preview_id=?',(key,pid)).fetchall()
            if previous:
                if any(r['preview_id']!=pid for r in previous): raise AppError('Idempotency key belongs to another order.',409)
                return json.loads(previous[0]['record'])
            row=db.execute('SELECT * FROM previews WHERE id=?',(pid,)).fetchone()
            if not row: raise AppError('Preview not found.',404)
            p=json.loads(row['record'])
            if row['status']!='pending' or row['expires']<time.time(): raise AppError('Preview expired. Create a fresh order preview.',409)
            if p['revision']!=self._get(db,'revision'): raise AppError('Holdings or rules changed. Review a fresh preview.',409)
            self._scan(db)
            alert=db.execute("SELECT * FROM alerts WHERE id=? AND status='active'",(p['alertId'],)).fetchone()
            if not alert or json.loads(alert['record'])['matched'] is not True: raise AppError('The alert is no longer actionable. Refresh first.',409)
            dataset=self._dataset(db)
            if dataset['mode']!='simulation': raise AppError('Live execution is not implemented.',403)
            security = next(s for s in dataset['securities'] if s['isin'] == p['isin'])
            current_price = metric_value('close', security, dataset['asof'])[0]
            if dataset['asof'] != p['asof'] or current_price is None or current_price != p['price']:
                raise AppError('Market snapshot changed. Review a fresh preview.',409)
            # Recheck the stored plan against authoritative lots; client quantities are never trusted.
            for a in p['accounts']:
                h=db.execute('SELECT * FROM holdings WHERE account_id=? AND isin=?',(a['account_id'],p['isin'])).fetchone()
                if not h or h['quantity']-h['pledged']-h['blocked']-h['unsettled']<a['sellQuantity']: raise AppError('Sellable quantity changed. Create a fresh preview.',409)
            eid=uid(); orders=[]
            for a in p['accounts']:
                qty=a['sellQuantity']
                if not qty: continue
                order=self.execution_adapter.submit(client_order_id=eid+'-'+a['account_id'],account_id=a['account_id'],isin=p['isin'],quantity=qty,price=p['price'],order_type=p['orderType'])
                orders.append({**order,'accountId':a['account_id'],'quantity':qty})
                db.execute('UPDATE holdings SET quantity=quantity-? WHERE account_id=? AND isin=?',(qty,a['account_id'],p['isin']))
            result={'id':eid,'previewId':pid,'symbol':p['symbol'],'isin':p['isin'],'quantity':p['quantity'],'proceeds':p['estimatedProceeds'],'price':p['price'],'createdAt':now(),'status':'SIMULATED_FILLED','orders':orders,'mode':'simulation'}
            db.execute('INSERT INTO executions VALUES(?,?,?,?,?)',(eid,pid,key,result['createdAt'],dumps(result)))
            db.execute("UPDATE previews SET status='executed' WHERE id=?",(pid,)); self._put(db,'cash',round(self._get(db,'cash')+result['proceeds'],2)); self._bump(db)
            self._audit(db,'EXIT_CONFIRMED',p['isin'],{'previewId':pid,'execution':result}); self._scan(db)
            return result
