from services import get_stock_metrics, get_timeseries, compare_stocks, compute_metrics

# Current (or at a given time) price, volume, growth, loss
get_stock_metrics("NTLC")                    # current from palmarès
get_stock_metrics("NTLC", at_time="2025-06-01")  # historical price from series

# Time series for a range (e.g. for a chart)
get_timeseries("NTLC", "2025-03-01", "2025-06-30")

# Compare two stocks
print(compare_stocks("NTLC", "SLBC", period="veille"))
print(compare_stocks("NTLC", "SLBC", period_price_date="2025-05-15"))  # + price at that date

# Stats over a period
print(compute_metrics("NTLC", "2025-01-01", "2025-12-31"))  # or no dates = full series