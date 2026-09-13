import pandas as pd
import os
import sys
import argparse
from data_loader import load_all_csvs
from decision import evaluate_request
from explain import generate_explanation

def find_dataset_dir(explicit=None):
    """Locate the dataset/ folder without assuming a fixed submission layout.

    Tries, in order: an explicit --dataset path, a `dataset/` folder next to
    this file's parent (the original solvent/ layout), and `dataset/` under
    the current working directory (running `python main.py` from the repo
    root that contains this code/ folder).
    """
    if explicit:
        return explicit

    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.join(os.path.dirname(here), 'dataset'),
        os.path.join(os.getcwd(), 'dataset'),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]

def main():
    parser = argparse.ArgumentParser(description="Run the Solvent affordability pipeline.")
    parser.add_argument('--dataset', default=None, help="Path to the dataset/ folder (default: auto-detected)")
    args = parser.parse_args()

    dataset_dir = find_dataset_dir(args.dataset)
    if not os.path.isdir(dataset_dir):
        print(f"Dataset directory not found at {dataset_dir}. Pass --dataset <path> to point at it.")
        sys.exit(1)

    data = load_all_csvs(dataset_dir)
    
    requests = data['requests.csv']
    profiles = data['financial_profiles.csv']
    
    output_rows = []
    
    # Track stats
    stats = {}
    errors = []
    violations = []
    
    for _, req in requests.iterrows():
        req_id = req['request_id']
        user_id = req['user_id']
        req_amt = req['requested_amount']
        
        try:
            res = evaluate_request(req_id, data=data)
            
            p_row = profiles[profiles['user_id'] == user_id]
            if p_row.empty:
                profile_dict = {}
            else:
                profile_dict = p_row.iloc[0].to_dict()
                
            explanation = generate_explanation(
                req_id, 
                res['amount_safe_to_pay'], 
                res['affordability_status'],
                res['recommended_payment_method'],
                res['payment_plan'],
                res['earliest_date_for_full_payment'],
                res['spending_changes_needed'],
                profile_dict
            )
            
            res['decision_explanation'] = explanation
            
            amt_safe = res['amount_safe_to_pay']
            if not (0 <= amt_safe <= req_amt):
                # allow a small floating point tolerance
                if not (0 - 1e-4 <= amt_safe <= req_amt + 1e-4):
                    violations.append((req_id, amt_safe, req_amt))
                else:
                    # snap it to bounds
                    res['amount_safe_to_pay'] = max(0.0, min(req_amt, amt_safe))
                
            status = res['affordability_status']
            stats[status] = stats.get(status, 0) + 1
            
            output_rows.append(res)
            print(f"Processed {req_id}: {status}", flush=True)
            
        except Exception as e:
            errors.append((req_id, str(e)))
            print(f"Error processing {req_id}: {e}", flush=True)
            
    df_out = pd.DataFrame(output_rows)
    cols = [
        'request_id', 'amount_safe_to_pay', 'affordability_status', 
        'recommended_payment_method', 'payment_plan', 
        'earliest_date_for_full_payment', 'spending_changes_needed', 
        'decision_explanation'
    ]
    if not df_out.empty:
        df_out = df_out[cols]
    
    out_path = os.path.join(dataset_dir, 'output.csv')
    df_out.to_csv(out_path, index=False)
    
    print("\n" + "="*40)
    print("SUMMARY")
    print("="*40)
    for k, v in stats.items():
        print(f"{k}: {v}")
        
    print(f"\nErrors: {len(errors)}")
    for r, e in errors:
        print(f"  {r}: {e}")
        
    print(f"\nViolations (amount_safe_to_pay not in [0, req_amount]): {len(violations)}")
    for r, s, a in violations:
        print(f"  {r}: {s} outside bounds of [0, {a}]")

if __name__ == '__main__':
    main()
