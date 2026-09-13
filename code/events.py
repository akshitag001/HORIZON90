import pandas as pd

from dataclasses import dataclass

from datetime import datetime, timedelta

import re

import os

from data_loader import load_all_csvs

from currency import CurrencyConverter



@dataclass

class CashFlowEvent:

    date: pd.Timestamp

    amount_signed: float

    category: str

    flexibility: str

    is_recurring: bool

    event_id: str

    cadence_days: int = 0
    status: str = ''

    description: str = ""



def get_image_fallback_amounts():

    return {

        'event_253': 4365000.0,

        'event_1545': 2500.0,

        'event_1700': 2854.0,

        'event_1786': 3543.54,

        'event_3051': 1995.0,

        'event_3231': 45.0,

        'event_4535': 15339.0,

        'event_5170': 723.0,

        'event_6033': 79679.26,

        'event_6859': 3650.02,

        'event_7307': 33.50,

        'event_7941': 2298.0,

        'event_9421': 43.0,

        'event_9806': 9968.0,

        'event_10521': 393.22,

    }



def apply_image_amounts(events_df):

    fallback = get_image_fallback_amounts()

    mask = events_df['amount'].isna()

    for idx in events_df[mask].index:

        eid = events_df.at[idx, 'event_id']

        if eid in fallback and fallback[eid] is not None:

            events_df.at[idx, 'amount'] = float(fallback[eid])

    events_df = events_df.dropna(subset=['amount']).copy()

    return events_df



def parse_message_amendments(events_df, messages_df):

    if messages_df.empty or 'related_event_id' not in messages_df.columns:

        return events_df

        

    messages_df = messages_df.dropna(subset=['related_event_id'])

    events_df = events_df.copy()

    events_df.set_index('event_id', inplace=True)

    

    cancel_re = re.compile(r'\bcancell?ed\b', re.IGNORECASE)

    delay_re = re.compile(r'\bdelay(ed)? to (\d{4}-\d{2}-\d{2})\b', re.IGNORECASE)

    amount_re = re.compile(r'\b(?:increas|decreas|chang)ed(?: by \d+%?)? to (?:[\$£€\w]*)\s?([\d,]+(?:\.\d+)?)\b', re.IGNORECASE)

    perc_re = re.compile(r'\b(increas|decreas)e(?:s|d)?.*?by\s+(\d+(?:\.\d+)?)%', re.IGNORECASE)

    

    for _, msg in messages_df.iterrows():

        rel_id = msg['related_event_id']

        text = str(msg['message_text'])

        if rel_id in events_df.index:

            if cancel_re.search(text):

                events_df.at[rel_id, 'status'] = 'cancelled'

            delay_match = delay_re.search(text)

            if delay_match:

                new_date = pd.to_datetime(delay_match.group(2))

                events_df.at[rel_id, 'event_date'] = new_date

            amount_match = amount_re.search(text)

            if amount_match:

                new_amt = float(amount_match.group(1).replace(',', ''))

                events_df.at[rel_id, 'amount'] = new_amt

            perc_match = perc_re.search(text)

            if perc_match:

                factor = 1.0 + (float(perc_match.group(2)) / 100.0) if perc_match.group(1).lower().startswith('increas') else 1.0 - (float(perc_match.group(2)) / 100.0)

                events_df.at[rel_id, 'amount'] = round(events_df.at[rel_id, 'amount'] * factor, 2)

                

    events_df.reset_index(inplace=True)

    return events_df



def parse_unlinked_salary_messages(events_df, messages_df):

    if messages_df.empty or 'related_event_id' not in messages_df.columns:

        return events_df

        

    unlinked = messages_df[messages_df['related_event_id'].isna()]

    if unlinked.empty: return events_df

    

    events_df = events_df.copy()

    

    date_only_re = re.compile(r'expected on (\d{4}-\d{2}-\d{2})', re.IGNORECASE)

    date_amt_re = re.compile(r'(\d{4}-\d{2}-\d{2}).*?(?:(?:IDR|EUR|ZAR|USD|INR|GBP|JPY|BRL|RUB)\s+)?(\d+(?:\.\d+)?)')

    amt_date_re = re.compile(r'(?:(?:IDR|EUR|ZAR|USD|INR|GBP|JPY|BRL|RUB)\s+)?(\d+(?:\.\d+)?).*?(\d{4}-\d{2}-\d{2})')

    

    new_rows = []

    for _, msg in unlinked.iterrows():

        text = str(msg['message_text'])

        if 'salary' not in text.lower() and 'gaji' not in text.lower() and 'payroll' not in text.lower():

            continue

            

        m_date_only = date_only_re.search(text)

        m_amt_date = amt_date_re.search(text)

        m_date_amt = date_amt_re.search(text)

        

        new_date = None

        new_amt = None

        

        if m_date_only:

            new_date = m_date_only.group(1)

            user_salaries = events_df[(events_df['user_id'] == msg['user_id']) & (events_df['category'] == 'salary')]

            if not user_salaries.empty:

                last_salary = user_salaries.sort_values('event_date').iloc[-1]

                new_amt = last_salary['amount']

        elif m_amt_date:

            new_amt = float(m_amt_date.group(1))

            new_date = m_amt_date.group(2)

        elif m_date_amt:

            new_date = m_date_amt.group(1)

            new_amt = float(m_date_amt.group(2))

            

        if new_date and new_amt is not None:

            new_row = {

                'user_id': msg['user_id'],

                'event_id': 'msg_' + str(msg['message_id']),

                'category': 'salary',

                'amount': new_amt,

                'currency': 'USD', 

                'event_date': pd.to_datetime(new_date),

                'settlement_date': pd.to_datetime(new_date),

                'status': 'scheduled',

                'direction': 'credit',

                'event_type': 'income',

                'flexibility': 'fixed',

                'description': 'Parsed from message'

            }

            user_salaries = events_df[(events_df['user_id'] == msg['user_id']) & (events_df['category'] == 'salary')]

            if not user_salaries.empty:

                new_row['currency'] = user_salaries.iloc[0]['currency']

            new_rows.append(new_row)

            

    if new_rows:

        events_df = pd.concat([events_df, pd.DataFrame(new_rows)], ignore_index=True)

        

    return events_df





def resolve_conflict(rows):

    if len(rows) == 1:

        return rows.iloc[0]

    cancels = rows[rows['status'] == 'cancelled']

    if not cancels.empty:

        return cancels.sort_values('event_date', ascending=False).iloc[0]

    settled = rows[rows['status'] == 'settled']

    if not settled.empty:

        return settled.sort_values('event_date', ascending=False).iloc[0]

    return rows.sort_values('event_date', ascending=False).iloc[0]



def collapse_lifecycles(events_df):

    if 'linked_event_id' not in events_df.columns:

        return events_df

    parent_map = dict(zip(events_df['event_id'], events_df['linked_event_id']))

    def get_root(eid):

        visited = set()

        while pd.notna(parent_map.get(eid)):

            p = parent_map[eid]

            if p in visited or p == eid:

                break

            visited.add(p)

            eid = p

        return eid

    events_df['root_id'] = events_df['event_id'].apply(get_root)

    

    resolved_rows = []

    for _, group in events_df.groupby('root_id'):

        resolved_rows.append(resolve_conflict(group))

    res_df = pd.DataFrame(resolved_rows)

    res_df = res_df.drop_duplicates(subset=['user_id', 'amount', 'category', 'event_date', 'description'])

    return res_df



def infer_cadence(dates):

    if len(dates) < 2: return 0

    dates = sorted(dates)

    

    from collections import Counter

    

    def check_deltas(lags):

        deltas = [(dates[i] - dates[i-lags]).days for i in range(lags, len(dates))]

        if not deltas: return 0

        

        counts = Counter(deltas)

        most_common_delta, count = counts.most_common(1)[0]

        

        if count >= len(deltas) * 0.5:

            return most_common_delta

            

        monthlies = sum(1 for d in deltas if 27 <= d <= 32)

        if monthlies >= len(deltas) * 0.5:

            return 30

            

        biweeklies = sum(1 for d in deltas if 13 <= d <= 15)

        if biweeklies >= len(deltas) * 0.5:

            return 14

            

        weeklies = sum(1 for d in deltas if 6 <= d <= 8)

        if weeklies >= len(deltas) * 0.5:

            return 7

            

        return 0

        

    for lag in [1, 2, 3, 4]:

        cad = check_deltas(lag)

        if cad > 0:

            return cad

            

    return 0





def parse_unlinked_amount_messages(events_df, messages_df):

    if messages_df.empty or 'related_event_id' not in messages_df.columns:

        return events_df

    unlinked = messages_df[messages_df['related_event_id'].isna()]

    if unlinked.empty: return events_df

    import re

    events_df = events_df.copy()

    events_df.set_index('event_id', inplace=True)

    amount_re = re.compile(r'\b(?:increas|decreas|chang)ed(?: by \d+%?)? to (?:[\$\w]*)\s?([\d,]+(?:\.\d+)?)\b', re.IGNORECASE)

    perc_re = re.compile(r'\b(increas|decreas)e(?:s|d)?.*?by\s+(\d+(?:\.\d+)?)%', re.IGNORECASE)

    for _, msg in unlinked.iterrows():

        text = str(msg['message_text'])

        cat = None

        if 'rent' in text.lower():

            cat = 'rent'

        if cat:

            cat_events = events_df[events_df['category'] == cat]

            if not cat_events.empty:

                last_id = cat_events.sort_values('event_date').index[-1]

                amount_match = amount_re.search(text)

                if amount_match:

                    new_amt = float(amount_match.group(1).replace(',', ''))

                    events_df.at[last_id, 'amount'] = new_amt

                perc_match = perc_re.search(text)

                if perc_match:

                    factor = 1.0 + (float(perc_match.group(2)) / 100.0) if perc_match.group(1).lower().startswith('increas') else 1.0 - (float(perc_match.group(2)) / 100.0)

                    events_df.at[last_id, 'amount'] = round(events_df.at[last_id, 'amount'] * factor, 2)

    events_df.reset_index(inplace=True)

    return events_df



def get_cash_flow_timeline(user_id: str, as_of_date, data: dict = None) -> list:

    if data is None:

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        dataset_dir = os.path.join(base_dir, 'dataset')

        data = load_all_csvs(dataset_dir)

        

    df_events = data.get('financial_events.csv', pd.DataFrame())

    if df_events.empty: return []

    df_user = df_events[df_events['user_id'] == user_id].copy()

    if df_user.empty: return []

    

    df_user = apply_image_amounts(df_user)

    messages = data.get('messages.csv', pd.DataFrame())

    if not messages.empty:

        df_user = parse_message_amendments(df_user, messages[messages['user_id'] == user_id])

        df_user = parse_unlinked_salary_messages(df_user, messages[messages['user_id'] == user_id])
        df_user = parse_unlinked_amount_messages(df_user, messages[messages['user_id'] == user_id])

        df_user = parse_unlinked_amount_messages(df_user, messages[messages['user_id'] == user_id])

        

    df_user = collapse_lifecycles(df_user)

    

    invalid_status = ['cancelled', 'failed', 'unrealized']

    df_user = df_user[~df_user['status'].isin(invalid_status)]

    df_user = df_user[df_user['direction'] != 'non_cash']

    

    mask_pending_credit = (df_user['status'] == 'pending') & (df_user['direction'] == 'credit')

    mask_variable_income = (df_user['direction'] == 'credit') & (
        df_user['category'].isin(['windfall', 'investment']) |
        df_user['description'].str.contains('commission|bonus|refund|lottery|gain', case=False, na=False)
    )
    df_user = df_user[~(mask_pending_credit | mask_variable_income)]

    

    profiles = data.get('financial_profiles.csv', pd.DataFrame())

    home_ccy = 'USD'

    if not profiles.empty and 'user_id' in profiles.columns:

        p_row = profiles[profiles['user_id'] == user_id]

        if not p_row.empty:

            home_ccy = p_row.iloc[0]['home_currency']

            

    rates = data.get('exchange_rates.csv', pd.DataFrame())

    converter = CurrencyConverter(rates)

    

    recurring_types = {'expense', 'income', 'subscription', 'debt_payment'}



    # Group by category only

    cat_dates = {}



    for _, row in df_user.iterrows():

        if row['event_type'] in recurring_types:

            cat = row['category']

            dt = row['settlement_date'] if pd.notna(row['settlement_date']) else row['event_date']

            if pd.notna(dt):

                cat_dates.setdefault(cat, []).append(dt)



    recurring_cat = {}

    for cat, dates in cat_dates.items():

        cad = infer_cadence(dates)

        if cad > 0:

            recurring_cat[cat] = cad

            

    timeline = []

    for idx, row in df_user.iterrows():

        eid = row['event_id']

        amt = row['amount']

        ccy = row['currency']

        cat = row['category']

        desc = str(row['description'])

        direction = row['direction']

        flex = row['flexibility']

        

        rate_date = row['event_date']

        if pd.isna(rate_date):

            continue

            

        try:

            amt_home = converter.convert(amt, ccy, home_ccy, rate_date)

        except ValueError as e:

            raise ValueError(f"Failed to convert event_id {eid} from {ccy} to {home_ccy} on {rate_date}: {e}")

        if direction == 'debit':

            amt_signed = -abs(amt_home)

        elif direction == 'credit':

            amt_signed = abs(amt_home)

        else:

            amt_signed = amt_home

            

        is_recur = (row['event_type'] in recurring_types) and (cat in recurring_cat)

        cadence = recurring_cat[cat] if is_recur else 0

        exec_date = pd.to_datetime(row['settlement_date']).date() if pd.notna(row['settlement_date']) else pd.to_datetime(row['event_date']).date()



        timeline.append(CashFlowEvent(

            date=exec_date,

            amount_signed=amt_signed,

            category=cat,

            flexibility=flex,

            is_recurring=is_recur,

            event_id=eid,

            cadence_days=cadence,
            status=row['status'],

            description=desc

        ))

        

    return timeline

