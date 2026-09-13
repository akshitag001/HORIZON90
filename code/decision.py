import pandas as pd
from datetime import timedelta, date
import itertools
from forecast import simulate_balance, get_cash_flow_timeline, precompute_events
from currency import CurrencyConverter

def evaluate_request(request_id, data):
    df_req = data['requests.csv']
    req_row = df_req[df_req['request_id'] == request_id]
    if req_row.empty:
        df_req = data.get('requests.csv', pd.DataFrame())
    req_row = df_req[df_req['request_id'] == request_id]
    if req_row.empty:
        df_req = data.get('sample_requests.csv', pd.DataFrame())
        req_row = df_req[df_req['request_id'] == request_id]
        if req_row.empty:
            raise ValueError(f"Request {request_id} not found in requests.csv or sample_requests.csv")
            
    req = req_row.iloc[0]
    user_id = req['user_id']
    req_date = pd.to_datetime(req['request_date']).date()
    amt = float(req['requested_amount'])
    deadline = pd.to_datetime(req['desired_completion_date']).date() if pd.notna(req['desired_completion_date']) else None
    
    profiles = data['financial_profiles.csv']
    profile = profiles[profiles['user_id'] == user_id].iloc[0]
    init_balance = float(profile['current_available_balance'])
    min_balance = float(profile['minimum_balance_to_keep'])
    user_prefs_raw = str(profile['payment_methods_user_will_consider']).lower()
    user_prefs = [p.strip() for p in user_prefs_raw.split('|')] if user_prefs_raw != 'nan' else []
    
    timeline = get_cash_flow_timeline(user_id, req_date, data=data)
    
    reduce_cats = str(profile['expense_categories_user_is_willing_to_reduce']).split('|') if pd.notna(profile['expense_categories_user_is_willing_to_reduce']) else []
    stop_cats = str(profile['expense_categories_user_is_willing_to_stop']).split('|') if pd.notna(profile['expense_categories_user_is_willing_to_stop']) else []
    
    df_events = data['financial_events.csv']
    converter = CurrencyConverter(data['exchange_rates.csv'])
    
    possible_changes = []
    
    for ev in timeline:
        if pd.notna(ev.flexibility) and ev.amount_signed < 0:
            flex = str(ev.flexibility).lower()
            if ev.category in stop_cats and flex in ['stoppable', 'reducible_or_stoppable']:
                possible_changes.append({'stop': ev.event_id})
            if ev.category in reduce_cats and flex in ['reducible', 'reducible_or_stoppable']:
                ev_row = df_events[df_events['event_id'] == ev.event_id].iloc[0]
                min_amt = ev_row['minimum_allowed_amount']
                if pd.notna(min_amt):
                    try:
                        home_ccy = profile['home_currency']
                        min_home = converter.convert(min_amt, ev_row['currency'], home_ccy, ev_row['event_date'])
                        possible_changes.append({'reduce_to': (ev.event_id, min_home)})
                    except:
                        pass
                        
    change_combos = [[]] # Start with no changes
    
    for r in range(1, 4):
        for combo in itertools.combinations(possible_changes, r):
            event_ids = set()
            conflict = False
            for c in combo:
                eid = c.get('stop') or c.get('reduce_to')[0]
                if eid in event_ids:
                    conflict = True
                    break
                event_ids.add(eid)
            if not conflict:
                change_combos.append(list(combo))
                
    # Sort combos by length (fewer changes first)
    change_combos.sort(key=len)
    
    all_valid_options = []
    
    pay_opts = data['request_payment_options.csv']
    req_opts = pay_opts[pay_opts['request_id'] == request_id]
    
    precomp = precompute_events(user_id, req_date, 455, data, timeline)
    
    def evaluate_changes(changes):
        options = []
        
        trace, is_safe = simulate_balance(
            user_id, req_date, days=455, hypothetical_payments=[], 
            spending_changes=changes, data=data, timeline=timeline,
            init_balance=init_balance, min_balance=min_balance,
            precomputed_events=precomp
        )
        
        def simulate_plan_fast(plan):
            if not plan: return False
            last_date = max(d for d, _ in plan)
            end_date = last_date + timedelta(days=90)
            
            # For each day in trace up to end_date, check if trace balance - payments >= min_balance
            for d, b in trace:
                if d > end_date:
                    break
                
                # sum payments up to d
                paid = sum(amt for pd_date, amt in plan if pd_date <= d)
                if b - paid < min_balance - 1e-4:
                    return False
            return True
        
        trace_balances = [b for _, b in trace]
        
        # trace is a list of (date, balance) up to req_date + 455
        # For safe_today, we only care about the first 90 days (indices 0 to 90)
        trace_90 = trace_balances[:91]
        
        if not trace_90:
            safe_today = 0.0
        else:
            lowest_90 = min(trace_90)
            safe_today = max(0.0, lowest_90 - min_balance)
            safe_today = min(amt, safe_today)
            
        earliest_full = None
        # We need to find the earliest test_date in 0..365 where 
        # min(balance for 90 days from test_date) >= min_balance + amt
        # Using a sliding window over trace since trace is day-by-day
        
        for i in range(365):
            test_date = req_date + timedelta(days=i)
            # Find index in trace where date >= test_date
            # Since trace starts at req_date and goes day by day for 455 days,
            # trace_balances[i] corresponds to test_date
            if i + 90 < len(trace_balances):
                window_min = min(trace_balances[i:i+91])
                if window_min >= min_balance + amt:
                    earliest_full = test_date
                    break
                
        # 1. full_payment
        if 'full_payment' in user_prefs:
            if safe_today >= amt - 0.01:
                status = 'affordable_now' if not changes else 'affordable_with_plan'
                options.append({
                    'status': status,
                    'method': 'full_payment',
                    'plan': f"{req_date}:{amt}",
                    'cost': amt,
                    'completion': req_date,
                    'start': req_date,
                    'payments': 1,
                    'option_id': '0',
                    'changes': changes
                })
                
        # 2. partial_payment
        if str(req.get('allows_partial_payment', 'false')).lower() == 'true' and 'partial_payment' in user_prefs:
            if 0 < safe_today < amt - 0.01 and earliest_full is not None:
                if deadline is None or earliest_full <= deadline:
                    rem = amt - safe_today
                    plan = [(req_date, safe_today), (earliest_full, rem)]
                    if simulate_plan_fast(plan):
                        plan_str = f"{req_date}:{safe_today}|{earliest_full}:{rem}"
                        options.append({
                            'status': 'affordable_with_plan',
                            'method': 'partial_payment',
                            'plan': plan_str,
                            'cost': amt,
                            'completion': earliest_full,
                            'start': req_date,
                            'payments': 2,
                            'option_id': '0',
                            'changes': changes
                        })
                        
        # 3. installments
        if 'installments' in user_prefs:
            max_months = float(profile['max_installment_months']) if pd.notna(profile['max_installment_months']) else 0
            for _, opt in req_opts.iterrows():
                if opt['payment_method'] != 'installments': continue
                num_payments = int(opt['number_of_payments'])
                if num_payments > max_months: continue
                
                freq_days = int(opt['payment_frequency_days'])
                first_date = pd.to_datetime(opt['first_payment_date']).date()
                opt_amt = float(opt['payment_amount'])
                total = float(opt['total_payable_amount'])
                opt_id = str(opt['payment_option_id'])
                
                plan = []
                curr = first_date
                for _ in range(num_payments):
                    plan.append((curr, opt_amt))
                    curr += timedelta(days=freq_days)
                    
                last_payment_date = plan[-1][0]
                
                if deadline is None or last_payment_date <= deadline:
                    if simulate_plan_fast(plan):
                        plan_str = "|".join([f"{d}:{a}" for d, a in plan])
                        options.append({
                            'status': 'affordable_with_plan',
                            'method': 'installments',
                            'plan': plan_str,
                            'cost': total,
                            'completion': last_payment_date,
                            'start': first_date,
                            'payments': num_payments,
                            'option_id': opt_id,
                            'changes': changes
                        })
                        
        # 4. wait
        if 'full_payment' in user_prefs and earliest_full is not None:
            status = 'affordable_later' if not changes else 'affordable_with_plan'
            options.append({
                'status': status,
                'method': 'wait',
                'plan': f"{earliest_full}:{amt}",
                'cost': amt,
                'completion': earliest_full,
                'start': earliest_full,
                'payments': 1,
                'option_id': '0',
                'changes': changes
            })
            
        return options

    pure_cash_options = evaluate_changes([])
    meets_deadline_no_change = [o for o in pure_cash_options if deadline is None or o['completion'] <= deadline]
    
    if meets_deadline_no_change:
        all_valid_options = meets_deadline_no_change
    elif not pure_cash_options:
        # Spec says: "spending changes are a last resort".
        if change_combos:
            max_combo_opts = evaluate_changes(possible_changes)
            max_meets = [o for o in max_combo_opts if deadline is None or o['completion'] <= deadline]
            
            if not max_meets:
                all_valid_options = pure_cash_options
            else:
                for r in range(1, 4):
                    r_combos = [c for c in change_combos[1:] if len(c) == r]
                    found_any = False
                    for combo in r_combos:
                        combo_opts = evaluate_changes(combo)
                        meets_deadline = [o for o in combo_opts if deadline is None or o['completion'] <= deadline]
                        if meets_deadline:
                            all_valid_options.extend(meets_deadline)
                            found_any = True
                    if found_any:
                        break
                        
        if not all_valid_options:
            all_valid_options = pure_cash_options
    else:
        for r in range(1, 4):
            r_combos = [c for c in change_combos[1:] if len(c) == r]
            found_any = False
            for combo in r_combos:
                combo_opts = evaluate_changes(combo)
                meets_deadline = [o for o in combo_opts if deadline is None or o['completion'] <= deadline]
                if meets_deadline:
                    all_valid_options.extend(meets_deadline)
                    found_any = True
            if found_any:
                break
                
        if not all_valid_options:
            all_valid_options = pure_cash_options

    def compute_safe_today_and_earliest_full():
        # amount_safe_to_pay / earliest_date_for_full_payment are defined by
        # the spec independently of whether a full payment plan exists --
        # they measure raw cash-flow capacity before any payment method is
        # chosen. This must be computed even when no option is safe (i.e.
        # affordability_status ends up not_affordable): the user may still be
        # able to safely pay part of the amount today, or the full amount may
        # become safe on some date past the deadline.
        trace, _ = simulate_balance(
            user_id, req_date, days=455, hypothetical_payments=[],
            spending_changes=[], data=data, timeline=timeline,
            init_balance=init_balance, min_balance=min_balance
        )

        trace_90 = [b for d, b in trace if (d - req_date).days <= 90]
        lowest_balance = min(trace_90) if trace_90 else 0.0
        safe_today = max(0.0, lowest_balance - min_balance)
        safe_today = min(amt, safe_today)

        earliest_full = None
        trace_balances = [b for d, b in trace]
        for i in range(365):
            test_date = req_date + timedelta(days=i)
            if i + 90 < len(trace_balances):
                window_min = min(trace_balances[i:i+91])
                if window_min >= min_balance + amt:
                    earliest_full = test_date
                    break

        return round(safe_today, 2), earliest_full

    if not all_valid_options:
        safe_today, earliest_full = compute_safe_today_and_earliest_full()
        return {
            'request_id': request_id,
            'amount_safe_to_pay': safe_today,
            'affordability_status': 'not_affordable',
            'recommended_payment_method': 'not_recommended',
            'payment_plan': 'none',
            'earliest_date_for_full_payment': None,
            'spending_changes_needed': 'none',
            'decision_explanation': ''
        }

    def sort_key(opt):
        fails_deadline = False
        if deadline is not None and opt['completion'] > deadline:
            fails_deadline = True
            
        return (
            fails_deadline,
            len(opt['changes']),
            opt['cost'],
            opt['start'],
            opt['payments'],
            opt['option_id']
        )
        
    all_valid_options.sort(key=sort_key)
    best = all_valid_options[0]
    
    def format_changes(changes):
        if not changes: return 'none'
        parts = []
        for c in changes:
            if 'stop' in c:
                parts.append(f"stop:{c['stop']}")
            elif 'reduce_to' in c:
                eid, amount = c['reduce_to']
                parts.append(f"reduce_to:{eid}:{amount:.2f}")
        return "|".join(parts)
        
    safe_today, earliest_full = compute_safe_today_and_earliest_full()

    res = {
        'request_id': request_id,
        'amount_safe_to_pay': safe_today,
        'affordability_status': best['status'],
        'recommended_payment_method': best['method'],
        'payment_plan': best['plan'],
        'earliest_date_for_full_payment': earliest_full,
        'spending_changes_needed': format_changes(best['changes']),
        'decision_explanation': ''
    }
    
    return res
