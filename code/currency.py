import pandas as pd

class CurrencyConverter:
    def __init__(self, df_rates: pd.DataFrame):
        self.df_rates = df_rates.copy()
        if not self.df_rates.empty:
            self.df_rates['rate_date'] = pd.to_datetime(self.df_rates['rate_date'])
            self.df_rates = self.df_rates.sort_values('rate_date')
            
    def _get_rate(self, from_ccy, to_ccy, on_date):
        if self.df_rates.empty:
            return None
        mask = (self.df_rates['from_currency'] == from_ccy) & \
               (self.df_rates['to_currency'] == to_ccy) & \
               (self.df_rates['rate_date'] <= on_date)
        valid_rates = self.df_rates[mask]
        
        if valid_rates.empty:
            return None
            
        return valid_rates.iloc[-1]['rate']

    def convert(self, amount: float, from_ccy: str, to_ccy: str, on_date) -> float:
        if from_ccy == to_ccy:
            return float(amount)
            
        on_date = pd.to_datetime(on_date)
        
        # 1. Direct pair
        rate = self._get_rate(from_ccy, to_ccy, on_date)
        if rate is not None:
            return float(amount * rate)
            
        # 2. Inverse pair
        rate_inv = self._get_rate(to_ccy, from_ccy, on_date)
        if rate_inv is not None:
            return float(amount * (1.0 / rate_inv))
            
        # 3. USD bridge
        if from_ccy != 'USD' and to_ccy != 'USD':
            # Find from_ccy -> USD
            rate_from_usd = self._get_rate(from_ccy, 'USD', on_date)
            if rate_from_usd is None:
                rate_usd_from = self._get_rate('USD', from_ccy, on_date)
                if rate_usd_from is not None:
                    rate_from_usd = 1.0 / rate_usd_from
                    
            # Find USD -> to_ccy
            rate_usd_to = self._get_rate('USD', to_ccy, on_date)
            if rate_usd_to is None:
                rate_to_usd = self._get_rate(to_ccy, 'USD', on_date)
                if rate_to_usd is not None:
                    rate_usd_to = 1.0 / rate_to_usd
                    
            if rate_from_usd is not None and rate_usd_to is not None:
                return float(amount * rate_from_usd * rate_usd_to)
                
        # 4. Error if no path found
        raise ValueError(f"No valid exchange rate found for {from_ccy} -> {to_ccy} on or before {on_date.date()}")
