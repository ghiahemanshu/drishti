import unittest,tempfile,copy,sqlite3,time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from backend.store import Store, AppError
from backend.make_seed import build_seed,leaf

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=self.tmp.name+'/portfolio.sqlite'; self.store=Store(self.path); self.initial=self.store.snapshot(); self.isin='INE467B01029'; self.alert=next(a for a in self.initial['alerts'] if a['target']==self.isin and a['ruleId']=='trend-200')
    def tearDown(self): self.tmp.cleanup()
    def preview(self,percent=25,**kw): return self.store.preview({'alertId':self.alert['id'],'percent':percent,**kw})
    def confirm(self,p,**kw): return self.store.confirm({'previewId':p['id'],'idempotencyKey':'confirm-'+p['id'],'confirmed':True,**kw})
    def test_isin_consolidation_and_availability(self):
        p=next(p for p in self.initial['positions'] if p['isin']==self.isin); self.assertEqual(p['quantity'],240); self.assertEqual(p['available'],235); self.assertEqual(len(p['accounts']),3); self.assertAlmostEqual(p['avgCost'],3560)
        self.assertAlmostEqual(sum(p['weight'] for p in self.initial['positions']),100)
    def test_scans_do_not_duplicate_active_alerts(self):
        ids={a['id'] for a in self.initial['alerts']}
        self.store.scan();self.store.scan();self.assertEqual(ids,{a['id'] for a in self.store.snapshot()['alerts']})
    def test_preview_alone_never_sells_and_reuses_token(self):
        p=self.preview();q=self.preview(); self.assertEqual(p['id'],q['id']); self.assertEqual(p['quantity'],60)
        self.assertEqual(self.initial['positions'],self.store.snapshot()['positions']); self.assertEqual(sum(a['sellQuantity'] for a in p['accounts']),60)
    def test_explicit_confirmation_required(self):
        p=self.preview()
        with self.assertRaises(AppError): self.confirm(p,confirmed=False)
        self.assertEqual(len(self.store.snapshot()['executions']),0)
    def test_full_exit_excludes_restricted_quantities(self):
        p=self.preview(100);self.assertEqual(p['quantity'],235);self.assertEqual(p['excludedQuantity'],5)
        e=self.confirm(p);s=self.store.snapshot();position=next(p for p in s['positions'] if p['isin']==self.isin)
        self.assertEqual(position['quantity'],5);self.assertEqual(position['available'],0);self.assertEqual(e['quantity'],235)
        self.assertEqual(s['summary']['cash'],self.initial['summary']['cash']+e['proceeds'])
    def test_replay_survives_restart(self):
        p=self.preview();a=self.confirm(p);self.store=Store(self.path);b=self.confirm(p);self.assertEqual(a,b);self.assertEqual(len(self.store.snapshot()['executions']),1)
        self.assertEqual(sum(x['action']=='EXIT_CONFIRMED' for x in self.store.snapshot()['audit']),1)
    def test_concurrent_duplicate_confirms_fill_once(self):
        p=self.preview()
        with ThreadPoolExecutor(max_workers=5) as pool: results=list(pool.map(lambda _: self.confirm(p),range(5)))
        self.assertEqual(len({r['id'] for r in results}),1);self.assertEqual(len(self.store.snapshot()['executions']),1)
    def test_competing_previews_only_one_can_fill(self):
        p=self.preview(25);q=self.preview(50);self.confirm(p)
        with self.assertRaisesRegex(AppError,'changed'): self.confirm(q)
    def test_expiry_invalidates_preview(self):
        p=self.preview()
        with patch('backend.store.time.time',return_value=p['expiresAt']+1):
            with self.assertRaisesRegex(AppError,'expired'): self.confirm(p)
    def test_server_ignores_client_quantity_price_and_allocations(self):
        p=self.preview();e=self.confirm(p,quantity=999999,price=1,accounts=[])
        self.assertEqual(e['quantity'],60);self.assertEqual(e['price'],3284)
    def test_quantity_revalidated_at_confirm(self):
        p=self.preview()
        with self.store.connection() as db: db.execute("UPDATE holdings SET blocked=quantity-pledged-unsettled WHERE isin=?",(self.isin,))
        with self.assertRaisesRegex(AppError,'quantity changed'): self.confirm(p)
    def test_rule_changes_resolve_old_alert_and_invalidate_preview(self):
        p=self.preview();r=copy.deepcopy(next(r for r in self.initial['rules'] if r['id']=='trend-200'));r['enabled']=False;self.store.save_rule(r)
        s=self.store.snapshot();self.assertEqual(next(a['status'] for a in s['alerts'] if a['id']==self.alert['id']),'resolved')
        with self.assertRaisesRegex(AppError,'changed'): self.confirm(p)
        with self.assertRaisesRegex(AppError,'changed'): self.store.save_rule(r)
    def test_review_does_not_clear_breach(self):
        self.store.acknowledge(self.alert['id']);s=self.store.snapshot();a=next(a for a in s['alerts'] if a['id']==self.alert['id']);self.assertTrue(a['acknowledged']);self.assertEqual(a['status'],'active')
    def test_selected_accounts_and_rounding(self):
        p=self.preview(25,accountIds=['groww']);self.assertEqual(p['quantity'],10);self.assertEqual(len(p['accounts']),1)
        for pct in [25,50,100]:
            p=self.preview(pct)
            self.assertEqual(p['quantity'],sum(a['sellQuantity'] for a in p['accounts']))
            self.assertTrue(all(0<=a['sellQuantity']<=a['available'] for a in p['accounts']))
    def test_key_cannot_be_reused_for_another_preview(self):
        p=self.preview();self.confirm(p);q=self.preview()
        with self.assertRaisesRegex(AppError,'another order'): self.confirm(q,idempotencyKey='confirm-'+p['id'])
    def test_failed_adapter_rolls_back_all_mock_fills(self):
        p=self.preview();original=self.store.execution_adapter.submit;calls=[0]
        def failure(**args):
            calls[0]+=1
            if calls[0]==2: raise RuntimeError('Simulated failure')
            return original(**args)
        with patch.object(self.store.execution_adapter,'submit',failure):
            with self.assertRaises(RuntimeError): self.confirm(p)
        s=self.store.snapshot();self.assertEqual(s['positions'],self.initial['positions']);self.assertEqual(s['executions'],[]);self.assertEqual(s['summary']['cash'],self.initial['summary']['cash'])
    def test_thesis_rule_and_audit_persist(self):
        self.store.save_thesis(self.isin,'Durable thesis');r={'name':'ROCE floor','condition':leaf('roce','lt',60),'severity':'hard_exit','scope':'stock','isin':self.isin,'enabled':True};self.store.save_rule(r)
        s=Store(self.path).snapshot();self.assertEqual(s['theses'][self.isin],'Durable thesis');self.assertTrue(any(r['name']=='ROCE floor' for r in s['rules']))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.connection() as db: db.execute('DELETE FROM audit')
    def test_missing_fundamentals_produce_data_gap(self):
        r={'name':'Bank ROCE','condition':leaf('roce','lt',15),'severity':'warning','scope':'stock','isin':'INE040A01034','enabled':True};r=self.store.save_rule(r)
        s=self.store.snapshot();self.assertIsNone(next(e['matched'] for e in s['evaluations'] if e['ruleId']==r['id']));self.assertGreater(s['summary']['unknowns'],0)
    def test_invalid_orders_and_scope_rejected(self):
        for body in ({'percent':30},{'percent':True},{'percent':25,'accountIds':[]},{'percent':25,'accountIds':['groww','groww']},{'percent':25,'accountIds':['nope']}):
            with self.assertRaises(AppError): self.store.preview({'alertId':self.alert['id'],**body})
        r=copy.deepcopy(next(r for r in self.initial['rules'] if r['id']=='trend-200'));r['scope']='portfolio'
        with self.assertRaises(AppError):self.store.save_rule(r)

    def test_changed_price_invalidates_preview_even_without_revision_bump(self):
        p=self.preview()
        with self.store.connection() as db:
            dataset=self.store._get(db,'dataset')
            security=next(s for s in dataset['securities'] if s['isin']==self.isin)
            security['bars'][-1]['close']-=10
            self.store._put(db,'dataset',dataset)
        with self.assertRaisesRegex(AppError,'snapshot changed'): self.confirm(p)
    def test_unknown_existing_alert_blocks_exit(self):
        with self.store.connection() as db:
            dataset=self.store._get(db,'dataset')
            security=next(s for s in dataset['securities'] if s['isin']==self.isin)
            security['bars']=security['bars'][-2:]
            self.store._put(db,'dataset',dataset)
        self.store.scan()
        a=next(a for a in self.store.snapshot()['alerts'] if a['id']==self.alert['id'])
        self.assertEqual(a['status'],'active'); self.assertIsNone(a['matched'])
        with self.assertRaisesRegex(AppError,'evaluable'): self.preview()
    def test_unmonitored_is_not_healthy(self):
        with self.store.connection() as db:
            db.execute('DELETE FROM rules')
        s=self.store.snapshot(); self.assertTrue(all(p['status']=='Unmonitored' for p in s['positions']))
    def test_stale_price_blocks_fundamental_exit(self):
        with self.store.connection() as db:
            dataset=self.store._get(db,'dataset'); dataset['asof']='2026-10-20'; self.store._put(db,'dataset',dataset)
        self.store.scan(); s=self.store.snapshot()
        self.assertTrue(all(p['valuationStale'] for p in s['positions']))
        a=next(a for a in s['alerts'] if a['target']==self.isin and a['ruleId']=='growth' and a['status']=='active')
        with self.assertRaisesRegex(AppError,'price is unavailable'): self.store.preview({'alertId':a['id'],'percent':25})
