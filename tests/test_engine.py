import unittest, copy
from statistics import mean
from backend.engine import metric_value, evaluate, validate_rule, weekly_bars
from backend.make_seed import build_seed, leaf

class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.seed=build_seed()
    def setUp(self): self.s=copy.deepcopy(self.seed['securities'][2]); self.asof=self.seed['asof']
    def test_all_daily_averages(self):
        for n in [20,50,100,200]: self.assertAlmostEqual(metric_value(f'dma{n}',self.s,self.asof)[0],mean(b['close'] for b in self.s['bars'][-n:]))
    def test_weekly_excludes_current_incomplete_week(self):
        bars=weekly_bars(self.s['bars'],self.asof); self.assertEqual(bars[-1]['date'],'2026-09-25'); self.assertEqual(len(bars[-40:]),40)
        self.assertAlmostEqual(metric_value('wma40',self.s,self.asof)[0],mean(b['close'] for b in bars[-40:]))
    def test_volume_excludes_signal_session(self):
        self.assertAlmostEqual(metric_value('volume_ratio',self.s,self.asof)[0],self.s['bars'][-1]['volume']/mean(b['volume'] for b in self.s['bars'][-21:-1]))
    def test_drawdown_from_trailing_closing_high(self):
        prices=[b['close'] for b in self.s['bars'][-252:]]; self.assertAlmostEqual(metric_value('drawdown_pct',self.s,self.asof)[0],100*(max(prices)-prices[-1])/max(prices))
    def test_consecutive_sessions_each_gets_its_own_ma(self):
        e=evaluate(leaf('close','lt',rhs='dma200',periods=2),self.s,self.asof)
        self.assertTrue(e['matched']); self.assertAlmostEqual(e['observations'][1]['threshold'],mean(b['close'] for b in self.s['bars'][-201:-1])); self.assertEqual(e['observations'][1]['date'],'2026-09-30')
    def test_missing_is_unknown_and_kleene_composites(self):
        self.s['fundamentals'][0]['roce']=None; unknown=leaf('roce','lt',10); yes=leaf('close','gt',0); no=leaf('close','lt',0)
        self.assertIsNone(evaluate(unknown,self.s,self.asof)['matched'])
        self.assertIsNone(evaluate({'all':[unknown,yes]},self.s,self.asof)['matched'])
        self.assertFalse(evaluate({'all':[unknown,no]},self.s,self.asof)['matched'])
        self.assertTrue(evaluate({'any':[unknown,yes]},self.s,self.asof)['matched'])
        self.assertIsNone(evaluate({'any':[unknown,no]},self.s,self.asof)['matched'])
    def test_insufficient_history_and_zero_volume_unknown(self):
        self.s['bars']=self.s['bars'][-15:]; self.assertIsNone(metric_value('dma20',self.s,self.asof)[0])
        self.s=copy.deepcopy(self.seed['securities'][2])
        for b in self.s['bars'][-21:-1]: b['volume']=0
        self.assertIsNone(metric_value('volume_ratio',self.s,self.asof)[0])
    def test_no_lookahead(self):
        original=metric_value('close',self.s,self.asof)[0]; self.s['bars'].append({'date':'2026-10-02','close':1,'volume':1})
        self.assertEqual(metric_value('close',self.s,self.asof)[0],original)
        self.s['fundamentals'][0]['publishedAt']='2026-10-03'
        self.assertEqual(metric_value('revenue_growth',self.s,self.asof)[0],self.s['fundamentals'][1]['revenue_growth'])
    def test_stale_data_unknown(self):
        self.assertIsNone(metric_value('close',self.s,'2026-10-20')[0]); self.assertIsNone(metric_value('revenue_growth',self.s,'2027-08-01')[0])
    def test_quarter_gap_is_unknown(self):
        del self.s['fundamentals'][1]
        e=evaluate(leaf('revenue_growth','lt',100,periods=2),self.s,self.asof)
        self.assertIsNone(e['matched']); self.assertIsNone(metric_value('margin_change_bps',self.s,self.asof)[0])
    def test_crossovers_are_events_not_levels(self):
        self.s['bars'][-2]['close']=101;self.s['bars'][-1]['close']=99
        self.assertTrue(evaluate(leaf('close','crosses_below',100),self.s,self.asof)['matched'])
        self.s['bars'][-2]['close']=98; self.assertFalse(evaluate(leaf('close','crosses_below',100),self.s,self.asof)['matched'])
    def test_event_window_and_unknown_feed(self):
        self.assertEqual(metric_value('event.guidance_cut',self.s,self.asof)[0],1)
        self.s['events'][0]['date']='2026-10-02'; self.assertEqual(metric_value('event.guidance_cut',self.s,self.asof)[0],0)
        del self.s['events']; self.assertIsNone(metric_value('event.guidance_cut',self.s,self.asof)[0])
    def test_invalid_rule_rejected(self):
        r=copy.deepcopy(self.seed['rules'][0])
        for condition in ({'all':[]},leaf('close','lt',float('nan')),leaf('close','lt',rhs='revenue_growth'),leaf('close','lt',rhs='wma40'),leaf('close','lt',3,periods=0),leaf('unknown','lt',3)):
            r['condition']=condition
            with self.assertRaises(ValueError): validate_rule(r)
