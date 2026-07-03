#!/usr/bin/env python3
"""
小白股票工具箱 v2 — 组合: akshare + backtesting.py + mplfinance + tabulate
一键安装：pip install -r requirements.txt
一键运行：python stock_toolkit.py
"""
import os
for k in list(os.environ):
    if 'proxy' in k.lower():
        del os.environ[k]
os.environ['NO_PROXY'] = '*'

import sys, json, textwrap
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

try:
    import akshare as ak
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')  # 不弹窗口，直接保存图片
    import matplotlib.pyplot as plt
    import mplfinance as mpf
    from backtesting import Backtest, Strategy
    from backtesting.lib import crossover
    import tabulate
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)

plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
pd.set_option('display.max_rows', 20)
pd.set_option('display.width', 100)

# ── 配置 ────────────────────────────────────────────────
@dataclass
class Config:
    stocks: list = field(default_factory=lambda: ["600519", "000858", "300750"])  # 茅台 五粮液 宁德时代
    days: int = 365
    cash: float = 100000
    commission: float = 0.0003

CONFIG = Config()

# ── 数据获取 ────────────────────────────────────────────
def fetch_data(symbol, days=365):
    """获取股票数据，akshare -> yfinance 双保险"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    is_a = symbol.isdigit() or symbol.upper().endswith(('.SH','.SZ','.BJ'))

    if is_a or symbol.isdigit():
        try:
            code = symbol.replace('.SH','').replace('.SZ','').replace('.BJ','').upper()
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date=start, end_date=end, adjust="qfq")
            if df is not None and not df.empty:
                df.rename(columns={"日期":"Date","开盘":"Open","收盘":"Close",
                    "最高":"High","最低":"Low","成交量":"Volume","成交额":"Turnover",
                    "振幅":"Amplitude","涨跌幅":"PctChange","涨跌额":"Change","换手率":"TurnoverRate"}, inplace=True)
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)
                df.sort_index(inplace=True)
                return df
        except:
            pass

    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        df = t.history(period=f"{days}d")
        if df is not None and not df.empty:
            df.columns = [c.capitalize() for c in df.columns]
            return df
    except:
        pass
    return None

def get_stock_name(symbol):
    """获取股票中文名"""
    try:
        df = ak.stock_zh_a_spot_em()
        match = df[df['代码'] == symbol]
        if not match.empty:
            return match.iloc[0]['名称']
    except:
        pass
    return symbol

# ── 技术指标 ────────────────────────────────────────────
def calc_indicators(df):
    """计算常用技术指标"""
    close = df["Close"]
    high, low = df["High"], df["Low"]
    volume = df["Volume"]

    # 均线
    for n in [5, 10, 20, 60]:
        df[f"MA{n}"] = close.rolling(n).mean()

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df["MACD_DIF"] = ema12 - ema26
    df["MACD_DEA"] = df["MACD_DIF"].ewm(span=9).mean()
    df["MACD_HIST"] = 2 * (df["MACD_DIF"] - df["MACD_DEA"])

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, float('nan'))
    df["RSI"] = 100 - (100 / (1 + rs))

    # 布林带
    df["BOLL_MID"] = close.rolling(20).mean()
    std = close.rolling(20).std()
    df["BOLL_UP"] = df["BOLL_MID"] + 2 * std
    df["BOLL_DN"] = df["BOLL_MID"] - 2 * std

    # 成交量均线
    df["VOL_MA5"] = volume.rolling(5).mean()
    df["VOL_MA20"] = volume.rolling(20).mean()
    return df

# ── 分析报告 ────────────────────────────────────────────
def analyze_stock(df, symbol, name=""):
    """对单只股票生成分析报告"""
    calc_indicators(df)
    last = df.iloc[-1]
    close = last["Close"]

    lines = []
    lines.append(f"{'='*55}")
    lines.append(f"  {name or symbol}  —  {last.name.date()}")
    lines.append(f"{'='*55}")

    # 行情
    lines.append(f"  收盘: {close:.2f}  |  开盘: {last['Open']:.2f}  |  最高: {last['High']:.2f}  |  最低: {last['Low']:.2f}")
    if 'Volume' in last and pd.notna(last['Volume']):
        lines.append(f"  成交量: {last['Volume']/10000:.0f}万  |  换手率: {last.get('TurnoverRate', 'N/A')}")

    # 均线
    ma5, ma20, ma60 = df["MA5"].iloc[-1], df["MA20"].iloc[-1], df["MA60"].iloc[-1]
    lines.append(f"  MA5: {ma5:.2f}  MA20: {ma20:.2f}  MA60: {ma60:.2f}")

    # 趋势判断
    if close > ma5 > ma20 > ma60:
        trend = "多头排列 ↑"
    elif close < ma5 < ma20 < ma60:
        trend = "空头排列 ↓"
    elif ma5 > ma20 and close > ma5:
        trend = "短期偏多 ↗"
    elif ma5 < ma20 and close < ma5:
        trend = "短期偏空 ↘"
    else:
        trend = "震荡整理 →"
    lines.append(f"  趋势: {trend}")

    # MACD
    macd_hist = df["MACD_HIST"].iloc[-1]
    macd_hist_prev = df["MACD_HIST"].iloc[-2] if len(df) > 1 else 0
    if macd_hist > 0 and macd_hist > macd_hist_prev:
        macd_signal = "多头增强"
    elif macd_hist > 0 and macd_hist < macd_hist_prev:
        macd_signal = "多头减弱"
    elif macd_hist < 0 and macd_hist < macd_hist_prev:
        macd_signal = "空头增强"
    else:
        macd_signal = "空头减弱"
    lines.append(f"  MACD: {macd_signal}  ({'红柱' if macd_hist > 0 else '绿柱'})")

    # RSI
    rsi = df["RSI"].iloc[-1]
    if pd.notna(rsi):
        if rsi > 70:
            rsi_signal = "超买 ⚠️"
        elif rsi < 30:
            rsi_signal = "超卖 💡"
        elif rsi > 50:
            rsi_signal = "偏多"
        else:
            rsi_signal = "偏空"
        lines.append(f"  RSI(14): {rsi:.1f} — {rsi_signal}")

    # 布林带位置
    if close > df["BOLL_UP"].iloc[-1]:
        boll_signal = "突破上轨，超买"
    elif close < df["BOLL_DN"].iloc[-1]:
        boll_signal = "跌破下轨，超卖"
    elif close > df["BOLL_MID"].iloc[-1]:
        boll_signal = "中轨上方，偏多"
    else:
        boll_signal = "中轨下方，偏空"
    lines.append(f"  布林带: {boll_signal}")

    # 涨跌统计
    pct = df["Close"].pct_change()
    up = (pct > 0).sum()
    dn = (pct < 0).sum()
    win_rate = up / (up + dn) * 100 if (up + dn) > 0 else 0
    lines.append(f"  区间胜率: {win_rate:.0f}%  ({up}涨/{dn}跌)")

    # 综合评分 (简单加权)
    score = 50
    if close > ma5: score += 5
    if ma5 > ma20: score += 5
    if ma20 > ma60: score += 5
    if macd_hist > 0: score += 5
    if pd.notna(rsi):
        if 40 < rsi < 60: score += 5
        elif rsi < 30: score += 8  # 超卖反弹机会
    if close > df["BOLL_MID"].iloc[-1]: score += 3
    score = max(0, min(100, score))

    if score >= 70:
        rating = "🟢 偏多"
    elif score >= 45:
        rating = "🟡 观望"
    else:
        rating = "🔴 偏空"
    lines.append(f"  综合评分: {score}/100  →  {rating}")
    lines.append("")

    return "\n".join(lines), score, rating, trend

# ── 回测策略 ────────────────────────────────────────────
class MaCrossStrategy(Strategy):
    n1, n2 = 5, 20
    def init(self):
        self.ma1 = self.I(lambda x: pd.Series(x).rolling(self.n1).mean(), self.data.Close, name="MA5")
        self.ma2 = self.I(lambda x: pd.Series(x).rolling(self.n2).mean(), self.data.Close, name="MA20")
    def next(self):
        if crossover(self.ma1, self.ma2): self.buy()
        elif crossover(self.ma2, self.ma1): self.sell()

class BollingerStrategy(Strategy):
    """布林带反转策略"""
    def init(self):
        self.mid = self.I(lambda x: pd.Series(x).rolling(20).mean(), self.data.Close, name="MID")
        close_arr = self.data.Close
        std_arr = pd.Series(close_arr).rolling(20).std()
        self.upper = self.I(lambda x: pd.Series(x).rolling(20).mean() + 2*pd.Series(x).rolling(20).std(), self.data.Close, name="UP")
        self.lower = self.I(lambda x: pd.Series(x).rolling(20).mean() - 2*pd.Series(x).rolling(20).std(), self.data.Close, name="DN")
    def next(self):
        if self.data.Close[-1] < self.lower[-1] and self.data.Close[-1] > self.data.Close[-2]:
            self.buy()
        elif self.data.Close[-1] > self.data.Close[-2] and (self.data.Close[-1] - self.lower[-1]) / self.lower[-1] > 0.02:
            pass

def run_backtest(df, symbol, strategy_cls=MaCrossStrategy, cash=100000, commission=0.0003):
    """回测指定策略"""
    bt = Backtest(df[["Open","High","Low","Close","Volume"]],
                  strategy_cls, cash=cash, commission=commission)
    result = bt.run()
    return {
        "收益率": f"{result['Return [%]']:.2f}%",
        "年化": f"{result['Return (Ann.) [%]']:.2f}%",
        "最大回撤": f"{result['Max. Drawdown [%]']:.2f}%",
        "交易次数": result['# Trades'],
        "胜率": f"{result['Win Rate [%]']:.2f}%",
        "夏普比率": f"{result['Sharpe Ratio']:.2f}",
    }

# ── K线图 ──────────────────────────────────────────────
def plot_chart(df, symbol, filename=None):
    """画K线图 + 均线 + MACD + 成交量"""
    if filename is None:
        filename = f"{symbol}_chart.png"
    try:
        ap = [
            mpf.make_addplot(df["MA5"], color="blue", width=0.8),
            mpf.make_addplot(df["MA20"], color="orange", width=0.8),
            mpf.make_addplot(df["MA60"], color="red", width=0.8),
            mpf.make_addplot(df["MACD_HIST"], type="bar", color="green", panel=2),
            mpf.make_addplot(df["MACD_DIF"], color="blue", panel=2),
            mpf.make_addplot(df["MACD_DEA"], color="orange", panel=2),
            mpf.make_addplot(df["RSI"], color="purple", panel=3, ylabel="RSI"),
        ]
        mpf.plot(df.tail(120), type="candle", volume=True,
                 title=f"{symbol} K线 + 均线 + MACD + RSI",
                 style="charles", addplot=ap,
                 figsize=(14, 10), tight_layout=True,
                 savefig=filename)
        return filename
    except Exception as e:
        return None

# ── 多股票对比 ──────────────────────────────────────────
def compare_stocks(stocks, days=365):
    """多股票对比分析"""
    results = []
    for s in stocks:
        print(f"  📥 正在获取 {s} ...")
        df = fetch_data(s, days)
        if df is None:
            print(f"    跳过 {s}")
            continue
        report, score, rating, trend = analyze_stock(df, s)
        results.append({"代码": s, "评分": score, "评级": rating, "趋势": trend})
        print(report)
    # 对比表格
    if results:
        print(f"\n{'='*55}")
        print(f"  多股票对比总览")
        print(f"{'='*55}")
        tbl = pd.DataFrame(results).sort_values("评分", ascending=False)
        print(tabulate.tabulate(tbl, headers="keys", tablefmt="simple", showindex=False))
    return results

# ── 主程序 ──────────────────────────────────────────────
def main():
    print(f"""
{'='*55}
  📈 小白股票工具箱 v2
  数据: akshare + yfinance  |  回测: backtesting.py
  教程: github.com/Rockyzsu/stock  |  日报: daily_stock_analysis
{'='*55}
""")

    # 选择模式
    print("  模式选择:")
    print("    1. 单股票分析 + 回测")
    print("    2. 多股票对比")
    print("    3. 快速扫描持仓 (默认)")
    mode = input("  请输入 (1/2/3): ").strip() or "3"

    # 默认持仓 (茅台+五粮液+宁德+招商银行+比亚迪)
    default_stocks = ["600519", "000858", "300750", "600036", "002594"]

    if mode == "1":
        symbol = input("  股票代码: ").strip() or "600519"
        days_in = input("  分析天数 (默认365): ").strip()
        days = int(days_in) if days_in.isdigit() else 365
        stocks = [symbol]
    elif mode == "2":
        inp = input(f"  股票代码 (逗号分隔, 默认{'/'.join(default_stocks)}): ").strip()
        stocks = [s.strip() for s in (inp.split(",") if inp else default_stocks)]
        days_in = input("  分析天数 (默认365): ").strip()
        days = int(days_in) if days_in.isdigit() else 365
    else:
        stocks = default_stocks
        days = 365
        print(f"  默认扫描: {' '.join(stocks)}")

    # ── 获取数据 + 分析 ──
    all_results = []
    for s in stocks:
        print(f"\n  {'─'*50}")
        print(f"  📥 {s} ...")
        df = fetch_data(s, days)
        if df is None:
            print(f"  ❌ 跳过 {s} (数据获取失败)")
            continue

        df = calc_indicators(df)
        report, score, rating, trend = analyze_stock(df, s)
        print(report)

        # K线图
        chart_file = plot_chart(df, s)
        if chart_file:
            print(f"  📊 K线图已保存: {chart_file}")

        # 策略回测
        print(f"  🔬 双均线回测 (MA5×MA20):")
        bt_result = run_backtest(df, s)
        for k, v in bt_result.items():
            print(f"    {k}: {v}")

        # 导出数据
        csv_file = f"{s}_data.csv"
        df.to_csv(csv_file)
        print(f"  💾 数据已导出: {csv_file}")

        all_results.append({"代码": s, "评分": score, "评级": rating, "趋势": trend, "名称": get_stock_name(s)})

    # ── 对比总览 ──
    if len(all_results) > 1:
        print(f"\n{'='*55}")
        print(f"  📋 多股票对比总览")
        print(f"{'='*55}")
        tbl = pd.DataFrame(all_results).sort_values("评分", ascending=False)
        print(tabulate.tabulate(tbl, headers="keys", tablefmt="simple", showindex=False))

    # ── 下一步 ──
    print(f"\n{'='*55}")
    print(f"  ✅ 分析完成")
    print(f"{'='*55}")
    print(f"  📖 学习量化:   github.com/Rockyzsu/stock")
    print(f"  🤖 AI 日报:    github.com/fuhongtao1010-oss/daily_stock_analysis")
    print(f"  📚 资源大全:   github.com/wilsonfreitas/awesome-quant")
    print(f"  🔧 修改策略:   编辑 stock_toolkit.py 中的 Strategy 类")
    print()

if __name__ == "__main__":
    main()
