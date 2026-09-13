import pandas as pd
import os

def load_all_csvs(dataset_dir: str) -> dict:
    data = {}
    csv_files = [
        "requests.csv", "sample_requests.csv", "financial_profiles.csv",
        "financial_events.csv", "exchange_rates.csv", "request_payment_options.csv",
        "messages.csv", "images.csv", "output.csv"
    ]
    
    for file in csv_files:
        path = os.path.join(dataset_dir, file)
        if os.path.exists(path):
            df = pd.read_csv(path)
            
            # Convert date columns to datetime
            for col in df.columns:
                if 'date' in col.lower():
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                # Convert amount/rate columns to float
                elif any(kw in col.lower() for kw in ['amount', 'balance', 'rate']):
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
            data[file] = df
        else:
            data[file] = pd.DataFrame()
            
    return data

def build_indices(data: dict) -> dict:
    indices = {
        'events_by_user': {},
        'profile_by_user': {},
        'payment_options_by_request': {},
        'messages_by_user': {},
        'messages_by_request': {},
        'images_by_request': {}
    }
    
    # Events by user
    df_events = data.get('financial_events.csv', pd.DataFrame())
    if not df_events.empty and 'user_id' in df_events.columns:
        indices['events_by_user'] = {user_id: group for user_id, group in df_events.groupby('user_id')}
        
    # Profile by user
    df_profiles = data.get('financial_profiles.csv', pd.DataFrame())
    if not df_profiles.empty and 'user_id' in df_profiles.columns:
        indices['profile_by_user'] = df_profiles.set_index('user_id').to_dict('index')
        
    # Payment options by request
    df_options = data.get('request_payment_options.csv', pd.DataFrame())
    if not df_options.empty and 'request_id' in df_options.columns:
        indices['payment_options_by_request'] = {req_id: group for req_id, group in df_options.groupby('request_id')}
        
    # Messages by user and request
    df_messages = data.get('messages.csv', pd.DataFrame())
    if not df_messages.empty:
        if 'user_id' in df_messages.columns:
            indices['messages_by_user'] = {user_id: group for user_id, group in df_messages.groupby('user_id')}
        if 'request_id' in df_messages.columns:
            indices['messages_by_request'] = {req_id: group for req_id, group in df_messages.groupby('request_id')}
            
    # Images by request
    df_images = data.get('images.csv', pd.DataFrame())
    if not df_images.empty and 'request_id' in df_images.columns:
        indices['images_by_request'] = {req_id: group for req_id, group in df_images.groupby('request_id')}
        
    return indices

def summarize_schema(data: dict):
    print("=== Schema Summary ===")
    categorical_cols = ['event_type', 'category', 'status', 'flexibility', 'direction']
    
    for file, df in data.items():
        print(f"\n--- {file} ---")
        if df.empty:
            print("File missing or empty.")
            continue
            
        print(f"Rows: {len(df)}")
        print("Columns and types:")
        for col, dtype in df.dtypes.items():
            print(f"  {col}: {dtype}")
            
        # Unique values for categoricals
        for col in categorical_cols:
            if col in df.columns:
                unique_vals = df[col].dropna().unique().tolist()
                print(f"  -> Unique '{col}': {unique_vals}")

if __name__ == "__main__":
    # Test data loading and indexing
    import sys
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(base_dir, 'dataset')
    
    if not os.path.exists(dataset_dir):
        print(f"Dataset directory not found at {dataset_dir}")
        sys.exit(1)
        
    print(f"Loading data from {dataset_dir}...")
    data = load_all_csvs(dataset_dir)
    indices = build_indices(data)
    
    print("\nIndices built successfully:")
    for key, val in indices.items():
        print(f"  {key}: {len(val)} groups/entries")
        
    print("")
    summarize_schema(data)
