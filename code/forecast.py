import pandas as pd
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
import os
from data_loader import load_all_csvs
from events import get_cash_flow_timeline

def precompute_events(user_id, start_date, days, data, timeline):
    end_date = start_date + timedelta(days=days)
    if timeline is None:
        timeline = get_cash_flow_timeline(user_id, start_date, data=data)
    
    def get_d(x):
        if hasattr(x.date, 'date') and callable(x.date.date): return x.date.date()
        if isinstance(x.date, date): return x.date
        return date.fromisoformat(str(x.date).split()[0])

    def typical_amount(events):
        # Median magnitude of the series, used to spot one-off outliers
        # (bonuses, arrears, quarterly payments) that share a category with
        # a regular recurring payment but shouldn't be projected forward
        # as if they were the recurring amount.
        mags = sorted(abs(ev.amount_signed) for ev in events)
        n = len(mags)
        if n == 0:
            return 0.0
        mid = n // 2
        return mags[mid] if n % 2 else (mags[mid - 1] + mags[mid]) / 2.0

    def is_amount_outlier(ev, typical, tolerance=0.35):
        if typical <= 0:
            return False
        return abs(abs(ev.amount_signed) - typical) > tolerance * typical

    def find_anchor_event(events, cadence):
        if 27 <= cadence <= 32: min_d, max_d = 20, 45
        elif 13 <= cadence <= 15: min_d, max_d = 10, 20
        elif 6 <= cadence <= 8: min_d, max_d = 5, 10
        else: min_d, max_d = cadence - 3, cadence + 3

        typical = typical_amount(events)

        def scan(skip_outliers):
            for i in range(len(events) - 1, -1, -1):
                ev = events[i]
                if skip_outliers and is_amount_outlier(ev, typical):
                    continue
                ev_d = get_d(ev)
                has_preceding = False
                for j in range(i - 1, -1, -1):
                    prev_ev = events[j]
                    if skip_outliers and is_amount_outlier(prev_ev, typical):
                        continue
                    prev_d = get_d(prev_ev)
                    delta = (ev_d - prev_d).days
                    if min_d <= delta <= max_d:
                        has_preceding = True
                        break
                if has_preceding:
                    return ev
            return None

        # Prefer the most recent typical-amount event that has a typical-amount
        # predecessor roughly one cadence earlier. An outlier amount (a bonus
        # landing a few days from the regular payroll) must not be chosen as
        # the anchor, since its amount would then be projected forward as if
        # it were the recurring payment.
        anchor = scan(skip_outliers=True)
        if anchor is not None:
            return anchor

        # Fall back to the original (amount-agnostic) behavior if every event
        # looks like an outlier relative to the median (e.g. a genuinely
        # variable-amount recurring series, like commission or gig payouts).
        anchor = scan(skip_outliers=False)
        if anchor is not None:
            return anchor
        return events[-1]

    cat_events = {}
    for ev in timeline:
        if ev.is_recurring:
            cat_events.setdefault(ev.category, []).append(ev)

    # cat_latest maps category -> (true_latest_event, amount_anchor_event).
    # The true latest event decides whether the series is still active (its
    # date drives the staleness cutoff and the next projected date) even
    # when its own amount looks like an outlier (e.g. a payroll cut, a
    # discount month) -- only the *amount* to project comes from the
    # outlier-aware anchor. Using the amount-anchor's (possibly older) date
    # for staleness would wrongly drop a category that is still recurring
    # just because its most recent instance had an unusual amount.
    cat_latest = {}
    for cat, evs in cat_events.items():
        evs.sort(key=get_d)
        if str(evs[-1].description).strip().lower().startswith('final'):
            continue
        true_latest = evs[-1]
        cad = true_latest.cadence_days if true_latest.cadence_days > 0 else 30
        anchor = find_anchor_event(evs, cad)
        cat_latest[cat] = (true_latest, anchor)

    projected_events = {}
    for ev in timeline:
        if hasattr(ev.date, 'date') and callable(ev.date.date):
            ev_d = ev.date.date()
        elif isinstance(ev.date, date):
            ev_d = ev.date
        else:
            ev_d = date.fromisoformat(str(ev.date).split()[0])
            
        if getattr(ev, 'status', '') == 'settled': continue
        if start_date <= ev_d <= end_date:
            projected_events.setdefault(ev_d, []).append((ev.amount_signed, ev.event_id, ev.category, ev.flexibility))
            
    def as_date(x):
        if hasattr(x, 'date') and callable(x.date):
            return x.date()
        if isinstance(x, date):
            return x
        return date.fromisoformat(str(x).split()[0])

    for cat, (true_latest, anchor_ev) in cat_latest.items():
        cadence = true_latest.cadence_days if true_latest.cadence_days > 0 else 30
        true_latest_d = as_date(true_latest.date)
        anchor_d = as_date(anchor_ev.date)

        # Staleness is judged from the true latest event (regardless of its
        # amount) so an unusual amount on the most recent occurrence (a pay
        # cut, a one-off discount) doesn't make an active category look
        # discontinued. But dates are walked forward from the amount-anchor
        # event, to keep phase aligned with the established pay day (e.g.
        # the 15th) even when the single most recent instance landed on an
        # atypical date (a one-off payment a few days off-cycle).
        amt = anchor_ev.amount_signed
        if cadence == 30:
            cutoff = start_date - relativedelta(days=45)
        else:
            cutoff = start_date - timedelta(days=int(cadence * 1.5))

        if true_latest_d < cutoff:
            continue

        if cadence == 30:
            curr = anchor_d + relativedelta(months=1)
        else:
            curr = anchor_d + timedelta(days=cadence)

        while curr < start_date:
            if cadence == 30:
                curr += relativedelta(months=1)
            else:
                curr += timedelta(days=cadence)

        while curr <= end_date:
            projected_events.setdefault(curr, []).append((amt, None, cat, true_latest.flexibility))
            if cadence == 30:
                curr += relativedelta(months=1)
            else:
                curr += timedelta(days=cadence)

    return projected_events

def simulate_balance(user_id, start_date, days=90, hypothetical_payments=None, spending_changes=None, data=None, timeline=None, init_balance=None, min_balance=None, precomputed_events=None):
    if data is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = load_all_csvs(os.path.join(base_dir, 'dataset'))
        
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date).date()
    elif isinstance(start_date, pd.Timestamp) or hasattr(start_date, 'date'):
        if hasattr(start_date, 'date') and not isinstance(start_date, date):
            start_date = start_date.date()
    
    if init_balance is None or min_balance is None:
        profiles = data.get('financial_profiles.csv', pd.DataFrame())
        if profiles.empty or user_id not in profiles['user_id'].values:
            raise ValueError(f"User {user_id} not found in profiles.")
            
        p_row = profiles[profiles['user_id'] == user_id].iloc[0]
        balance = float(p_row['current_available_balance'])
        min_balance = float(p_row['minimum_balance_to_keep'])
    else:
        balance = init_balance
    
    stops = set()
    reductions = {}
    if spending_changes:
        for sc in spending_changes:
            if 'stop' in sc:
                stops.add(sc['stop'])
            elif 'reduce_to' in sc:
                reductions[sc['reduce_to'][0]] = sc['reduce_to'][1]
                
    hp_dict = {}
    if hypothetical_payments:
        for d, amt in hypothetical_payments:
            if hasattr(d, 'date') and callable(d.date):
                d_date = d.date()
            elif isinstance(d, date):
                d_date = d
            else:
                d_date = date.fromisoformat(str(d).split()[0])
            hp_dict[d_date] = hp_dict.get(d_date, 0.0) - abs(amt)
            
    end_date = start_date + timedelta(days=days)
    
    if precomputed_events is not None:
        projected_events = precomputed_events
        event_dict = {ev.event_id: ev for ev in timeline} if timeline else {}
    else:
        projected_events = precompute_events(user_id, start_date, days, data, timeline)
        event_dict = {ev.event_id: ev for ev in timeline} if timeline else {}
    stopped_cats = set()
    for stop_id in stops:
        if stop_id in event_dict:
            ev = event_dict[stop_id]
            if ev.flexibility not in ['stoppable', 'reducible_or_stoppable']:
                raise ValueError(f"Cannot stop event {stop_id} with flexibility {ev.flexibility}")
            stopped_cats.add(ev.category)
            
    reduced_cats = {}
    for reduce_id in reductions:
        if reduce_id in event_dict:
            ev = event_dict[reduce_id]
            if ev.flexibility not in ['reducible', 'reducible_or_stoppable']:
                raise ValueError(f"Cannot reduce event {reduce_id} with flexibility {ev.flexibility}")
            reduced_cats[ev.category] = abs(reductions[reduce_id])
                
    series = []
    is_safe = True
    curr_date = start_date
    
    for i in range(days + 1):
        d = curr_date
        
        if d in projected_events:
            for amt, ev_id, cat, flex in projected_events[d]:
                if cat in stopped_cats:
                    continue
                if cat in reduced_cats:
                    new_mag = reduced_cats[cat]
                    if amt < 0:
                        amt = -new_mag
                    else:
                        amt = new_mag
                balance += amt
                
        if d in hp_dict:
            balance += hp_dict[d]
            
        if balance < min_balance:
            is_safe = False
            
        series.append((d, balance))
        curr_date += timedelta(days=1)
        
    return series, is_safe

def earliest_safe_full_payment_date(user_id, request_date, amount, days=90, data=None, spending_changes=None, timeline=None, precomputed_events=None):
    if data is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = load_all_csvs(os.path.join(base_dir, 'dataset'))
        
    request_date = pd.to_datetime(request_date)
    start_date = pd.to_datetime(request_date).date()
    start_date = pd.to_datetime(start_date).date()
    curr_date = start_date
    end_date = start_date + timedelta(days=days)
    
    while curr_date <= end_date:
        _, is_safe = simulate_balance(user_id, start_date, days=days, hypothetical_payments=[(curr_date, amount)], data=data, spending_changes=spending_changes, timeline=timeline, precomputed_events=precomputed_events)
        if is_safe:
            return curr_date
        curr_date += timedelta(days=1)
        
    return None
    
def max_safe_amount_today(user_id, request_date, data=None):
    if data is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data = load_all_csvs(os.path.join(base_dir, 'dataset'))
        
    series, is_safe = simulate_balance(user_id, request_date, days=90, data=data)
    
    profiles = data.get('financial_profiles.csv')
    p_row = profiles[profiles['user_id'] == user_id].iloc[0]
    min_balance = float(p_row['minimum_balance_to_keep'])
    
    if not is_safe:
        return 0.0
        
    lowest_balance = min(bal for d, bal in series)
    safe_amt = lowest_balance - min_balance
    return max(0.0, float(safe_amt))

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data = load_all_csvs(os.path.join(base_dir, 'dataset'))
    
    print("Testing request_01 (user_01, 2024-03-03, amt=25256)...")
    amt_safe_01 = max_safe_amount_today('user_01', '2024-03-03', data=data)
    print(f"Max safe amount today: {amt_safe_01:.2f} (Expected >= 25256)")
    if amt_safe_01 >= 25256:
        print("request_01 max_safe_amount_today: PASS")
    else:
        print("request_01 max_safe_amount_today: FAIL")
        
    print("\nTesting request_03...")
    df_req = data['sample_requests.csv']
    row_03 = df_req[df_req['request_id'] == 'request_03'].iloc[0]
    amt_03 = row_03['requested_amount']
    req_date_03 = row_03['request_date']
    
    date_03 = earliest_safe_full_payment_date('user_03', req_date_03, amt_03, data=data)
    print(f"Earliest safe full payment date: {date_03} (Expected 2019-11-15)")
    if str(date_03) == '2019-11-15':
        print("request_03 earliest_safe_full_payment_date: PASS")
    else:
        print("request_03 earliest_safe_full_payment_date: FAIL")
