#!/usr/bin/env python3
import os
# Nuke all proxy env vars before anything else
for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

print("Proxy env after cleanup:", {k:v for k,v in os.environ.items() if 'proxy' in k.lower() or 'PROXY' in k})

import akshare as ak
df = ak.stock_zh_a_hist(symbol='600519', period='daily', start_date='20260401', end_date='20260702', adjust='qfq')
print("Shape:", df.shape)
print("Cols:", df.columns.tolist())
print(df.tail(3))
