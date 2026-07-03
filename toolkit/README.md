# 小白股票工具箱 — 使用指南

## 两套工具配合使用

```
日常看结论 → daily_stock_analysis（AI日报，推送到微信）
动手学习   → stock_toolkit.py（本地跑数据、回测）
```

---

## 一、AI日报（已 Fork 好，只需填密钥）

你的专属仓库已就绪：
**https://github.com/fuhongtao1010-oss/daily_stock_analysis**

### 配置步骤（5分钟）

```
1. 打开上面链接 → Settings → Secrets and variables → Actions
2. 添加以下 Secrets：
```

| Secret | 值 | 说明 |
|--------|-----|------|
| `STOCK_LIST` | `600519,000858,300750,00700` | 你的自选股 |
| `ANSPIRE_API_KEYS` | 去 anspire.cn 注册免费拿 | 大模型+搜索，一键搞定 |
| `GEMINI_API_KEY` | ai.google.dev 免费拿 | 备用 AI 模型 |
| `WECHAT_WEBHOOK_URL` | 企业微信机器人 URL | 推送到微信（或飞书/Telegram） |

```
3. Actions 标签页 → 启用 workflows
4. Actions → 每日股票分析 → Run workflow → 手动测试一次
```

之后每天早上6点（北京时间）自动出报告。

---

## 二、本地工具箱

### 安装运行

```bash
cd ~/tmp/stock-toolkit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python stock_toolkit.py
```

### 三种模式

| 模式 | 操作 |
|------|------|
| 1. 单股票分析 | 输一个代码，看指标+K线+回测 |
| 2. 多股票对比 | 输多个代码，对比评分排序 |
| 3. 快速扫描 | 默认扫5只白马股 |

### 输出内容

- 📊 基础指标（均线、MACD、RSI、布林带）
- 📈 K线图（保存为 PNG）
- 🔬 双均线回测结果（收益率、胜率、夏普比率）
- 💾 CSV 数据导出
- 📋 多股票评分对比表

---

## 三、学习路线

| 阶段 | 干什么 |
|------|--------|
| 第1周 | 每天早上看 AI日报推送，熟悉分析维度 |
| 第2周 | 本地工具箱跑持仓股票，看各项指标什么意思 |
| 第3周 | 跟着 Rockyzsu/stock 教程学策略 |
| 第4周 | 改 toolkit 里的回测参数，验证自己的想法 |
