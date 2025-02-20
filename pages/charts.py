import yfinance as yf

ticker = yf.Ticker("SPY")
print(ticker.options)