import sys
import os
import pandas as pd
from tabulate import tabulate

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from data_loader import load_all_csvs
from events import get_cash_flow_timeline
from decision import evaluate_request
from explain import generate_explanation
from main import find_dataset_dir

def main():
    dataset_dir = find_dataset_dir()

    print("Loading datasets...")
    data = load_all_csvs(dataset_dir)
    sample_reqs = data['sample_requests.csv']
    
    fields_to_check = [
        'amount_safe_to_pay',
        'affordability_status',
        'recommended_payment_method',
        'payment_plan',
        'earliest_date_for_full_payment',
        'spending_changes_needed',
        'decision_explanation'
    ]
    
    table_data = []
    mismatches = []
    
    fully_matching_rows = 0
    
    for _, req in sample_reqs.iterrows():
        req_id = req['request_id']
        data_mock = dict(data)
        data_mock['requests.csv'] = sample_reqs
        
        try:
            opt = evaluate_request(req_id, data_mock)
            profile_df = data['financial_profiles.csv']
            profile = profile_df[profile_df['user_id'] == req['user_id']].iloc[0]
            
            explanation = generate_explanation(
                req_id=req_id,
                amount_safe=opt['amount_safe_to_pay'],
                affordability=opt['affordability_status'],
                recommended_method=opt['recommended_payment_method'],
                payment_plan=opt['payment_plan'],
                earliest_date=opt['earliest_date_for_full_payment'],
                spending_changes=opt['spending_changes_needed'],
                profile=profile
            )
            
            row_matches = True
            
            for field in fields_to_check:
                expected = req[field]
                if field == 'decision_explanation':
                    got = explanation
                else:
                    got = opt[field]
                
                # Normalization
                if pd.isna(expected):
                    expected = 'none' if field in ['payment_plan', 'spending_changes_needed'] else ''
                else:
                    expected = str(expected).strip()
                    
                if field == 'amount_safe_to_pay':
                    expected = str(round(float(expected), 2))
                    got = str(round(float(got), 2))
                else:
                    got = str(got).strip() if got is not None else ''
                    
                is_match = (expected == got)
                
                if not is_match:
                    row_matches = False
                    mismatches.append((req_id, field, expected, got))
                
                table_data.append([
                    req_id, field, expected[:50] + ('...' if len(expected)>50 else ''), 
                    got[:50] + ('...' if len(got)>50 else ''), 'Y' if is_match else 'N'
                ])
                
            if row_matches:
                fully_matching_rows += 1
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERROR] processing {req_id}: {e}")
            for field in fields_to_check:
                table_data.append([req_id, field, req[field], 'ERROR', 'N'])
                mismatches.append((req_id, field, req[field], 'ERROR'))
    
    print("\n--- DETAILED RESULTS ---")
    print(tabulate(table_data, headers=['Request ID', 'Field', 'Expected', 'Got', 'Match']))
    
    print("\n" + "="*50)
    print("FINAL SUMMARY")
    print("="*50)
    print(f"{fully_matching_rows}/{len(sample_reqs)} rows fully matching.")
    
    if mismatches:
        print("\nMismatches:")
        for r_id, f, exp, got in mismatches:
            print(f"  - {r_id} [{f}]: expected '{exp}', got '{got}'")
    else:
        print("\nALL ROWS MATCH EXACTLY!")

if __name__ == "__main__":
    main()
