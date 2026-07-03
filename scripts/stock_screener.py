#!/usr/bin/env python3
"""
A股智能选股推荐器 — 全市场扫描 + 多因子筛选 + AI 分析
配合 GitHub Actions 每天自动推荐
"""
import os
for k in list(os.environ):
    if 'proxy' in k.lower(): del os.environ[k]
os.environ['NO_PROXY'] = '*'

import sys, json, time
from datetime import datetime, timedelta
try:
    import akshare as ak
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"缺少依赖: {e}")
    sys.exit(1)

pd.set_option('display.max_rows', 30)
pd.set_option('display.width', 120)


def screen_a_shares(min_price=5, max_price=200, min_volume_ratio=1.2, top_n=30):
    """
    全市场扫描选股 — 多因子筛选
    返回评分最高的 top_n 只股票
    """
    print("  📥 获取全A股实时行情...")
    df = ak.stock_zh_a_spot_em()
    print(f"    共 {len(df)} 只股票")

    # 重命名列
    col_map = {
        '代码': 'code', '名称': 'name', '最新价': 'price',
        '涨跌幅': 'pct', '涨跌额': 'change', '成交量': 'volume',
        '成交额': 'amount', '振幅': 'amplitude', '换手率': 'turnover',
        '市盈率-动态': 'pe', '市净率': 'pb',
        '总市值': 'mcap', '流通市值': 'fcap',
        '60日涨跌幅': 'pct_60d', '5日涨跌幅': 'pct_5d',
        '量比': 'vol_ratio',
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

    # 基础过滤
    cond = (
        (df['price'] >= min_price) & (df['price'] <= max_price)
        & (df['turnover'] > 0.3)  # 有换手
    )
    if 'vol_ratio' in df.columns:
        cond &= (df['vol_ratio'] >= min_volume_ratio)
    if 'pct' in df.columns:
        cond &= (df['pct'] > -5) & (df['pct'] < 10)  # 排除暴涨暴跌
    if 'mcap' in df.columns:
        cond &= (df['mcap'] > 1e9)  # 总市值 > 10亿，排除垃圾股

    df = df[cond].copy()
    print(f"    基础过滤后: {len(df)} 只")

    if len(df) == 0:
        print("  ❌ 没有符合条件的股票")
        return pd.DataFrame()

    # ── 多因子评分 ──
    scores = []

    # 1. 涨幅因子 (最近表现好)
    if 'pct' in df.columns:
        pct_score = (df['pct'] - df['pct'].min()) / (df['pct'].max() - df['pct'].min() + 1e-10)
        scores.append(pct_score * 20)  # 权重 20%

    # 2. 量比因子 (放量)
    if 'vol_ratio' in df.columns:
        vr_max = df['vol_ratio'].clip(upper=10)  # 封顶10倍
        vr_score = (vr_max - vr_max.min()) / (vr_max.max() - vr_max.min() + 1e-10)
        scores.append(vr_score * 20)  # 权重 20%

    # 3. 换手率因子 (活跃度适中)
    if 'turnover' in df.columns:
        t = df['turnover'].clip(upper=20)  # 封顶20%
        t_score = 1 - abs(t - t.median()) / (t.max() - t.min() + 1e-10)  # 接近中位数最好
        scores.append(t_score * 15)  # 权重 15%

    # 4. 振幅因子 (有波动才有机会)
    if 'amplitude' in df.columns:
        amp = df['amplitude'].clip(upper=10)
        amp_score = (amp - amp.min()) / (amp.max() - amp.min() + 1e-10)
        scores.append(amp_score * 10)  # 权重 10%

    # 5. 市值因子 (中等市值弹性大)
    if 'mcap' in df.columns:
        mcap_log = np.log10(df['mcap'])
        ideal = mcap_log.median()
        mcap_score = 1 - abs(mcap_log - ideal) / (mcap_log.max() - mcap_log.min() + 1e-10)
        scores.append(mcap_score * 15)  # 权重 15%

    # 6. PE 因子 (估值合理)
    if 'pe' in df.columns:
        pe = df['pe'].clip(0, 100)
        pe_score = 1 - (pe - pe.min()) / (pe.max() - pe.min() + 1e-10)
        scores.append(pe_score * 10)  # 权重 10%

    # 7. 5日涨幅(动量)
    if 'pct_5d' in df.columns:
        mom = df['pct_5d'].clip(-20, 30)
        mom_score = (mom - mom.min()) / (mom.max() - mom.min() + 1e-10)
        scores.append(mom_score * 10)  # 权重 10%

    # 综合评分
    df['score'] = sum(scores)
    df['score'] = df['score'].round(1)

    # 排序取 top
    df = df.sort_values('score', ascending=False).head(top_n)
    df['rank'] = range(1, len(df) + 1)

    return df[['rank', 'code', 'name', 'price', 'pct', 'vol_ratio', 'turnover',
               'pe', 'mcap', 'score']].copy()


def get_board_hot():
    """获取热门板块"""
    try:
        df = ak.stock_board_industry_name_em()
        df = df.sort_values('涨跌幅', ascending=False).head(10)
        return df[['板块名称', '涨跌幅', '上涨家数', '下跌家数', '领涨股']]
    except:
        return None


def get_board_stocks(board_name, top=5):
    """获取板块内领涨股"""
    try:
        df = ak.stock_board_industry_cons_em(symbol=board_name)
        df = df.sort_values('涨跌幅', ascending=False).head(top)
        return df[['代码', '名称', '最新价', '涨跌幅']]
    except:
        return None


def gen_telegram_report(screened, top_n=10):
    """生成 Telegram 推送格式的报告"""
    lines = []
    lines.append("🔥 *A股智能选股推荐*\n")

    # 热门板块
    boards = get_board_hot()
    if boards is not None:
        lines.append("*📊 今日热门板块*")
        for _, row in boards.iterrows():
            lines.append(
                f"  {row['板块名称']}  {row['涨跌幅']:+.2f}%  "
                f"↑{row['上涨家数']}↓{row['下跌家数']}"
            )
        lines.append("")

    # 推荐列表
    lines.append(f"*🏆 综合评分 Top {top_n}*")
    lines.append("`排名 代码    名称       评分 价格   涨幅 `")
    for _, row in screened.head(top_n).iterrows():
        name = row['name'][:6].ljust(6)
        lines.append(
            f"`{int(row['rank']):<4} {row['code']} {name} "
            f"{row['score']:<4} {row['price']:<6.2f} "
            f"{row['pct']:+.2f}%`"
        )

    lines.append("")
    lines.append("⚡ *筛选条件*")
    lines.append("• 价格: 5-200元 | 换手>0.3% | 市值>10亿")
    lines.append("• 多因子评分: 涨幅+量比+换手+振幅+市值+PE+动量")
    lines.append("")
    lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("⚠️ 仅供参考，投资需谨慎")

    return "\n".join(lines)


def main():
    print("=" * 55)
    print("  A股智能选股推荐器")
    print("=" * 55)

    # 选股
    screened = screen_a_shares(top_n=30)
    if screened.empty:
        print("  没有找到符合条件的股票")
        return

    # 打印
    print(f"\n  {'='*55}")
    print(f"  🏆 综合评分 Top 20")
    print(f"  {'='*55}")
    for _, row in screened.head(20).iterrows():
        print(f"  #{int(row['rank']):<3} {row['code']} {row['name']:<8} "
              f"评分:{row['score']:<5} 价格:{row['price']:<8.2f} "
              f"涨幅:{row['pct']:+.2f}%")

    # 热门板块
    print(f"\n  {'='*55}")
    print(f"  📊 今日热门板块")
    print(f"  {'='*55}")
    boards = get_board_hot()
    if boards is not None:
        for _, row in boards.iterrows():
            print(f"  {row['板块名称']:<12} {row['涨跌幅']:>+6.2f}%  "
                  f"↑{row['上涨家数']}↓{row['下跌家数']}  "
                  f"领涨: {row.get('领涨股', '')}")

    # 导出报告
    report = gen_telegram_report(screened)
    with open("stock_recommend_report.md", "w") as f:
        f.write(report)
    print(f"\n  💾 报告已保存: stock_recommend_report.md")

    # 输出JSON（给GitHub Actions用）
    screened.head(10).to_json("stock_recommend_top10.json", orient="records", force_ascii=False)
    print(f"  💾 Top10 JSON: stock_recommend_top10.json")


if __name__ == "__main__":
    main()
