def generate_explanation(req_id, amount_safe, affordability, recommended_method, payment_plan, earliest_date, spending_changes, profile):
    """
    Generates a deterministic 1-2 sentence explanation based on the decision results.
    """
    home_currency = profile.get('home_currency', 'USD')
    min_balance = float(profile.get('minimum_balance_to_keep', 0))
    
    amount_safe_str = f"{home_currency} {amount_safe:.2f}"
    
    if affordability == 'affordable_now':
        if spending_changes and spending_changes != 'none':
            return f"The request is affordable today up to {amount_safe_str} if the required spending changes are applied, protecting the minimum balance of {home_currency} {min_balance:.2f}."
        else:
            return f"The requested amount is fully affordable today, maintaining the required minimum balance of {home_currency} {min_balance:.2f}."
            
    if affordability == 'affordable_with_plan':
        if recommended_method == 'partial_payment':
            msg = f"The requested amount cannot be fully paid today without breaching the minimum balance. A partial payment of {amount_safe_str} can be made today, with the remainder on {earliest_date}."
        elif recommended_method == 'installments':
            msg = f"The requested amount cannot be fully paid today without breaching the minimum balance. The recommended installment plan is safe and completes by the desired deadline."
        else:
            msg = f"The requested amount can be safely paid through a structured payment plan."
            
        if spending_changes and spending_changes != 'none':
            msg += " This requires applying the recommended spending changes."
        return msg
        
    if affordability == 'affordable_later':
        msg = f"The requested amount cannot be paid today or via installments, but becomes fully affordable on {earliest_date} while maintaining the minimum balance of {home_currency} {min_balance:.2f}."
        if spending_changes and spending_changes != 'none':
            msg += " This requires applying the recommended spending changes."
        return msg
        
    # not_affordable
    msg = f"The request is not affordable within the forecast period without breaching the minimum balance of {home_currency} {min_balance:.2f}."
    if spending_changes and spending_changes != 'none':
        msg = f"Even with allowed spending changes, the request remains not affordable without breaching the minimum balance of {home_currency} {min_balance:.2f}."
    return msg
