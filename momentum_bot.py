import requests
import time
import os

# --- 設定（GitHub Secretsから読み込み） ---
BIRDEYE_API_KEY = os.environ.get("BIRDEYE_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_to_discord(message):
    if not DISCORD_WEBHOOK_URL: return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
    except:
        pass

def is_rugcheck_safe(ca):
    """RugCheck APIによる安全性検品"""
    url = f"https://api.rugcheck.xyz/v1/tokens/{ca}/report"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return False
        risks = response.json().get("risks", [])
        for risk in risks:
            if risk.get("level") == "danger":
                print(f"    [×] セキュリティ却下: {risk.get('name')}")
                return False
        return True
    except:
        return False

def get_birdeye_tokens():
    """Birdeye APIからトレンド取得 (最大20件)"""
    url = "https://public-api.birdeye.so/defi/token_trending"
    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    params = {"sort_by": "volume24hUSD", "sort_type": "desc", "offset": 0, "limit": 20}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10).json()
        return res.get("data", {}).get("tokens", []) if res.get("success") else []
    except:
        return []

def get_dexscreener_tokens():
    """DexScreenerから最新のブースト銘柄を取得 (無料・キー不要)"""
    url = "https://api.dexscreener.com/token-boosts/latest/v1"
    try:
        # DexScreenerはトレンドのCA（コントラクトアドレス）をリストで返す
        res = requests.get(url, timeout=10).json()
        # Solanaチェーンの銘柄のみ抽出
        return [t.get("tokenAddress") for t in res if t.get("chainId") == "solana"]
    except:
        return []

def get_token_overview(ca):
    """特定のCAの出来高・流動性データをBirdeyeから取得"""
    url = f"https://public-api.birdeye.so/defi/token_overview?address={ca}"
    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        return res.get("data", {}) if res.get("success") else None
    except:
        return None

def main():
    if not BIRDEYE_API_KEY: return
    
    # 1. 両方のAPIから候補を収集（重複排除）
    print(">>> データ収集開始...")
    birdeye_list = [t.get("address") for t in get_birdeye_tokens()]
    dex_list = get_dexscreener_tokens()
    all_ca = list(set(birdeye_list + dex_list)) # 重複を除いた全アドレス
    
    print(f">>> 監視対象: {len(all_ca)}件 (Birdeye: {len(birdeye_list)}, Dex: {len(dex_list)})")
    
    passed_count = 0
    for ca in all_ca:
        data = get_token_overview(ca)
        if not data: continue
        
        symbol = data.get("symbol", "Unknown")
        liquidity = float(data.get("v24hUSD", 0) or 0) # 簡易的に24h出来高を流動性の指標として使用
        # 実際には data.get("liquidity") があればそれを使用
        liq = float(data.get("liquidity", 0) or 0)
        v24h = float(data.get("v24hUSD", 0) or 0)
        v1h = float(data.get("v1hUSD", 0) or 0)
        
        # 加速判定 (1.2倍)
        avg_v1h = v24h / 24 if v24h > 0 else 0
        is_accelerating = v1h > (avg_v1h * 1.2)
        
        # 二段階選別：[数値フィルター] -> [セキュリティ検査]
        if (15000 <= liq <= 300000) and is_accelerating and (v1h > liq * 0.05):
            if is_rugcheck_safe(ca):
                passed_count += 1
                msg = (
                    f"🚀 **【マルチソース検知】: {symbol}**\n"
                    f"```text\n"
                    f"加速率: {v1h/avg_v1h:.1f}倍 / 1h出来高: ${v1h:,.0f}\n"
                    f"流動性: ${liq:,.0f}\n"
                    f"```\n"
                    f"🔍 **BubbleMaps**: https://app.bubblemaps.io/sol/token/{ca}\n"
                    f"📊 **GMGN**: https://gmgn.ai/sol/token/{ca}"
                )
                send_to_discord(msg)
                print(f"    [OK] 通知送信: {symbol}")
        
        time.sleep(0.6) # API制限回避

    print(f"\n>>> スキャン完了: {passed_count}件を通知しました。")

if __name__ == "__main__":
    main()
