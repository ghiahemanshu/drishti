"""Pure, deterministic indicators and three-valued rule evaluation. No I/O or AI."""
from datetime import date, timedelta
from statistics import mean
import math

SEVERITIES = ['info', 'watch', 'warning', 'exit_review', 'hard_exit']
EVENTS = ['auditor_resignation', 'management_resignation', 'rating_downgrade', 'regulatory_action', 'related_party_transaction', 'acquisition', 'capital_raise', 'guidance_cut']
METRICS = {
    'close': ('Daily close', '₹', 'technical'),
    **{f'dma{n}': (f'{n} DMA', '₹', 'technical') for n in [20, 50, 100, 200]},
    'weekly_close': ('Completed weekly close', '₹', 'technical'),
    'wma40': ('40-week simple MA', '₹', 'technical'),
    'drawdown_pct': ('Drawdown from 252-session closing high', '%', 'technical'),
    'volume_ratio': ('Volume / previous 20-session average', '×', 'technical'),
    'revenue_growth': ('Revenue growth · YoY', '%', 'fundamental'),
    'revenue_cr': ('Quarterly revenue', '₹ cr', 'fundamental'),
    'ebitda_margin': ('EBITDA margin', '%', 'fundamental'),
    'margin_change_bps': ('Margin change · QoQ', 'bps', 'fundamental'),
    'pat_growth': ('PAT growth · YoY', '%', 'fundamental'),
    'roce': ('ROCE · annualised', '%', 'fundamental'),
    'roe': ('ROE · annualised', '%', 'fundamental'),
    'debt_equity': ('Debt / equity', '×', 'fundamental'),
    'net_debt_ebitda': ('Net debt / EBITDA', '×', 'fundamental'),
    'interest_coverage': ('Interest coverage', '×', 'fundamental'),
    'cfo_pat': ('Operating cash flow / PAT · TTM', '×', 'fundamental'),
    'cfo_cr': ('Operating cash flow · TTM', '₹ cr', 'fundamental'),
    'fcf_cr': ('Free cash flow · TTM', '₹ cr', 'fundamental'),
    'promoter_pledge': ('Promoter shares pledged', '%', 'fundamental'),
    'promoter_holding': ('Promoter holding', '%', 'fundamental'),
    'promoter_change_pp': ('Promoter holding change · QoQ', 'pp', 'fundamental'),
    **{f'event.{e}': (e.replace('_', ' ').capitalize() + ' · last 90 days', '0/1', 'event') for e in EVENTS},
    'max_stock_weight': ('Largest stock weight', '% of equity', 'portfolio'),
    'max_sector_weight': ('Largest sector weight', '% of equity', 'portfolio'),
    'smallcap_pct': ('Small-cap exposure', '% of equity', 'portfolio'),
    'below200_pct': ('Equity below 200 DMA', '% of equity', 'portfolio'),
    'warning_pct': ('Equity with warning or exit alerts', '% of equity', 'portfolio'),
    'cash_pct': ('Cash allocation', '% of total', 'portfolio'),
}
OPS = {'lt': '<', 'lte': '≤', 'gt': '>', 'gte': '≥', 'eq': '=', 'crosses_below': 'crosses below', 'crosses_above': 'crosses above'}

def catalog():
    return [{'key': k, 'label': v[0], 'unit': v[1], 'category': v[2]} for k, v in METRICS.items()]

def validate_rule(rule):
    if not isinstance(rule, dict): raise ValueError('Rule must be an object.')
    if not isinstance(rule.get('name'), str) or not 1 <= len(rule['name'].strip()) <= 120: raise ValueError('Give the rule a name of 1–120 characters.')
    if rule.get('severity') not in SEVERITIES: raise ValueError('Choose a valid severity.')
    if rule.get('scope') not in ('stock', 'portfolio'): raise ValueError('Invalid scope.')
    if type(rule.get('enabled')) is not bool: raise ValueError('Enabled must be true or false.')
    count = [0]
    def visit(node, depth=0):
        count[0] += 1
        if depth > 4 or count[0] > 30 or not isinstance(node, dict): raise ValueError('Rule is too complex (30 nodes / 4 levels maximum).')
        if 'all' in node or 'any' in node:
            key = 'all' if 'all' in node else 'any'
            if set(node) != {key} or not isinstance(node[key], list) or not 1 <= len(node[key]) <= 10: raise ValueError('A composite needs 1–10 conditions and one AND/OR operator.')
            for child in node[key]: visit(child, depth + 1)
            return
        metric, op = node.get('metric'), node.get('op')
        if metric not in METRICS or op not in OPS: raise ValueError('Unknown metric or comparator.')
        category = METRICS[metric][2]
        if (rule['scope'] == 'portfolio') != (category == 'portfolio'): raise ValueError('Metric does not match rule scope.')
        rhs = node.get('rhsMetric')
        if rhs:
            if rhs not in METRICS or METRICS[rhs][2] != category or METRICS[rhs][1] != METRICS[metric][1]: raise ValueError('Compare compatible metrics with matching units.')
        elif type(node.get('value')) not in (int, float) or not math.isfinite(node['value']): raise ValueError('A finite threshold is required.')
        periods = node.get('periods', 1)
        if type(periods) is not int or not 1 <= periods <= 8: raise ValueError('Consecutive periods must be between 1 and 8.')
        if category in ('event', 'portfolio') and periods != 1: raise ValueError('Events and portfolio rules use one snapshot.')
        if op.startswith('crosses') and category != 'technical': raise ValueError('Crossovers are supported for technical metrics only.')
        weekly = metric in ('weekly_close', 'wma40')
        if rhs and weekly != (rhs in ('weekly_close', 'wma40')): raise ValueError('Compare daily with daily, or weekly with weekly metrics.')
    visit(rule.get('condition'))

def valid_bars(security, asof):
    return sorted([b for b in security.get('bars', []) if b['date'] <= asof and b.get('complete', True)], key=lambda b: b['date'])

def weekly_bars(bars, asof):
    weeks = {}
    for b in bars:
        d = date.fromisoformat(b['date'])
        friday = d + timedelta(days=4 - d.weekday())
        if friday <= date.fromisoformat(asof): weeks[friday.isoformat()] = b
    return [weeks[k] for k in sorted(weeks)]

def metric_value(key, security, asof, offset=0, portfolio=None):
    """Returns (value, observation date, reason). None never means healthy."""
    category = METRICS[key][2]
    if category == 'portfolio':
        value = (portfolio or {}).get(key)
        return value, asof, '' if value is not None else 'Portfolio data is incomplete.'
    if category == 'event':
        start = date.fromisoformat(asof) - timedelta(days=90)
        if 'events' not in security: return None, asof, 'Corporate event feed is missing.'
        result = any(e['type'] == key[6:] and start.isoformat() <= e['date'] <= asof for e in security['events'])
        return int(result), asof, ''
    if category == 'fundamental':
        quarters = sorted([q for q in security.get('fundamentals', []) if q['publishedAt'] <= asof], key=lambda q: q['period'], reverse=True)
        if len(quarters) <= offset: return None, asof, 'Insufficient published quarters.'
        q = quarters[offset]
        if offset:
            latest = date.fromisoformat(quarters[0]['period'])
            observed = date.fromisoformat(q['period'])
            if latest.year * 4 + (latest.month - 1) // 3 - (observed.year * 4 + (observed.month - 1) // 3) != offset:
                return None, q['period'], 'A required consecutive quarter is missing.'
        if (date.fromisoformat(asof) - date.fromisoformat(quarters[0]['publishedAt'])).days > 180: return None, q['period'], 'Latest fundamentals are older than 180 days.'
        value = q.get(key)
        if key in ('margin_change_bps', 'promoter_change_pp'):
            field, scale = ('ebitda_margin', 100) if key == 'margin_change_bps' else ('promoter_holding', 1)
            prev = quarters[offset + 1] if len(quarters) > offset + 1 else {}
            current_quarter = date.fromisoformat(q['period'])
            previous_quarter = date.fromisoformat(prev['period']) if prev else None
            adjacent = previous_quarter is not None and current_quarter.year * 4 + (current_quarter.month - 1) // 3 - (previous_quarter.year * 4 + (previous_quarter.month - 1) // 3) == 1
            value = (q[field] - prev[field]) * scale if adjacent and q.get(field) is not None and prev.get(field) is not None else None
        return value, q['period'], '' if value is not None else 'Metric is unavailable for this company / quarter.'
    bars = valid_bars(security, asof)
    if not bars: return None, asof, 'Daily price history is missing.'
    if (date.fromisoformat(asof) - date.fromisoformat(bars[-1]['date'])).days > 7: return None, bars[-1]['date'], 'Price history is older than 7 calendar days.'
    if key in ('weekly_close', 'wma40'): bars = weekly_bars(bars, asof)
    if offset: bars = bars[:-offset] if len(bars) > offset else []
    if not bars: return None, asof, 'Insufficient completed observations.'
    at = bars[-1]['date']; values = [b['close'] for b in bars]; value = None
    if key in ('close', 'weekly_close'): value = values[-1]
    elif key.startswith('dma') or key == 'wma40':
        n = int(key[3:]) if key.startswith('dma') else 40
        if len(values) >= n: value = mean(values[-n:])
    elif key == 'drawdown_pct':
        if len(values) >= 252: value = (max(values[-252:]) - values[-1]) / max(values[-252:]) * 100
    elif key == 'volume_ratio':
        if len(bars) >= 21:
            baseline = mean([b['volume'] for b in bars[-21:-1]])
            if baseline > 0: value = bars[-1]['volume'] / baseline
    return value, at, '' if value is not None else 'Insufficient observations for this indicator.'

def compare(a, b, op):
    if a is None or b is None: return None
    return {'lt': lambda: a < b, 'lte': lambda: a <= b, 'gt': lambda: a > b, 'gte': lambda: a >= b, 'eq': lambda: a == b}[op]()

def evaluate(condition, security, asof, portfolio=None):
    if 'all' in condition or 'any' in condition:
        mode = 'all' if 'all' in condition else 'any'; children = [evaluate(c, security, asof, portfolio) for c in condition[mode]]; vals = [c['matched'] for c in children]
        if mode == 'all': result = False if False in vals else (None if None in vals else True)
        else: result = True if True in vals else (None if None in vals else False)
        return {'mode': mode, 'matched': result, 'children': children}
    key, op = condition['metric'], condition['op']; rows = []
    for offset in range(condition.get('periods', 1)):
        value, at, reason = metric_value(key, security, asof, offset, portfolio); rhs = condition.get('rhsMetric')
        threshold, _, rhs_reason = metric_value(rhs, security, asof, offset, portfolio) if rhs else (condition['value'], at, '')
        previous = None
        if op.startswith('crosses'):
            a0, _, r0 = metric_value(key, security, asof, offset + 1, portfolio)
            b0, _, r1 = metric_value(rhs, security, asof, offset + 1, portfolio) if rhs else (threshold, at, '')
            previous = {'value': a0, 'threshold': b0}
            if None in (value, threshold, a0, b0): matched = None
            elif op == 'crosses_below': matched = a0 >= b0 and value < threshold
            else: matched = a0 <= b0 and value > threshold
            reason = reason or rhs_reason or r0 or r1
        else: matched = compare(value, threshold, op)
        rows.append({'date': at, 'value': value, 'threshold': threshold, 'matched': matched, 'reason': reason or rhs_reason, 'previous': previous})
    vals = [r['matched'] for r in rows]; matched = False if False in vals else (None if None in vals else True)
    return {'metric': key, 'label': METRICS[key][0], 'unit': METRICS[key][1], 'category': METRICS[key][2], 'op': op, 'operator': OPS[op], 'rhsMetric': condition.get('rhsMetric'), 'periods': condition.get('periods', 1), 'matched': matched, 'observations': rows}
