import requests
import time
import os

# --- 設定 ---
BIRDEYE_API_KEY = os.environ.get("BIRDEYE_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_to_discord(message):
    if not DISCORD_WEBHOOK_URL: return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
    except:
        pass

def is_rugcheck_safe(ca):
    """RugCheckによるセキュリティ検品"""
    url = f"https://api.rugcheck.xyz/v1/tokens/{ca}/report"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return False
        data = response.json()
        risks = data.get("risks", [])
        
        # 危険判定が1つでもあれば即却下
        for risk in risks:
            if risk.get("level") == "danger":
                print(f"    [×] Security Danger: {risk.get('name')}")
                return False
        return True
    except:
        return False

def get_birdeye_tokens():
    """Birdeyeトレンド取得 (Free枠限界の20件)"""
    url = "https://public-api.birdeye.so/defi/token_trending"
    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    params = {"sort_by": "volume24hUSD", "sort_type": "desc", "offset": 0, "limit": 20}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10).json()
        return res.get("data", {}).get("tokens", []) if res.get("success") else []
    except:
        return []

def get_dexscreener_tokens():
    """DexScreener最新ブースト銘柄取得"""
    url = "https://api.dexscreener.com/token-boosts/latest/v1"
    try:
        res = requests.get(url, timeout=10).json()
        return [t.get("tokenAddress") for t in res if t.get("chainId") == "solana"]
    except:
        return []

def get_token_overview(ca):
    """CA詳細データ(時価総額・流動性)を取得"""
    url = f"https://public-api.birdeye.so/defi/token_overview?address={ca}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        return res.get("data", {}) if res.get("success") else None
    except:
        return None

def main():
    if not BIRDEYE_API_KEY: return
    
    print(">>> 索敵開始 (Multi-Source Enabled)...")
    all_ca = list(set([t.get("address") for t in get_birdeye_tokens()] + get_dexscreener_tokens()))
    print(f">>> 母集団: {len(all_ca)}件")

    passed_count = 0
    for ca in all_ca:
        data = get_token_overview(ca)
        if not data: continue
        
        symbol = data.get("symbol", "???")
        liq = float(data.get("liquidity", 0) or 0)
        mc = float(data.get("mc", 0) or 0)
        v24h = float(data.get("v24hUSD", 0) or 0)
        v1h = float(data.get("v1hUSD", 0) or 0)
        
        # --- 新規追加: 流動性比率の計算 ---
        # 比率 = 流動性 / 時価総額
        liq_ratio = (liq / mc) if mc > 0 else 0
        
        # 加速判定
        avg_v1h = v24h / 24 if v24h > 0 else 0
        is_accelerating = v1h > (avg_v1h * 1.2)

        # --- フィルタリング条件 ---
        # 1. 流動性が1.5万ドル〜30万ドル (小〜中規模)
        # 2. 流動性比率が 15% 以上 (出口の確保) [cite: 2026-02-13]
        # 3. 加速率が 1.2倍 以上 (トレンド初動)
        # 4. 回転率が 5% 以上 (活性度)
        if (15000 <= liq <= 300000) and (liq_ratio >= 0.15) and is_accelerating and (v1h > liq * 0.05):
            if is_rugcheck_safe(ca):
                passed_count += 1
                msg = (
                    f"🛡️ **【防衛選別クリア】: {symbol}**\n"
                    f"```text\n"
                    f"加速率: {v1h/avg_v1h:.1f}倍 / 流動性比率: {liq_ratio*100:.1f}%\n"
                    f"1h出来高: ${v1h:,.0f} / 流動性: ${liq:,.0f}\n"
                    f"時価総額: ${mc:,.0f}\n"
                    f"```\n"
                    f"🔍 **BubbleMaps**: https://app.bubblemaps.io/sol/token/{ca}\n"
                    f"📊 **GMGN**: https://gmgn.ai/sol/token/{ca}"
                )
                send_to_discord(msg)
                print(f"    [OK] 通知送信: {symbol}")
        
        time.sleep(0.6) # レート制限対策

    print(f"\n>>> スキャン完了: {passed_count}件通知")

if __name__ == "__main__":
    main()
