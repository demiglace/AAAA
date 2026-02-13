import requests
import time
import os

# GitHub Secretsから安全に読み込む（直書き厳禁）
BIRDEYE_API_KEY = os.environ.get("BIRDEYE_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_to_discord(message):
    if not DISCORD_WEBHOOK_URL: return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=5)
    except Exception as e:
        print(f"Discord送信エラー: {e}")

def is_rugcheck_safe(ca):
    url = f"https://api.rugcheck.xyz/v1/tokens/{ca}/report"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200: return False
        risks = response.json().get("risks", [])
        for risk in risks:
            if risk.get("level") == "danger":
                print(f"    [×] 却下: 危険判定 ({risk.get('name')})")
                return False
        return True
    except:
        return False

#def get_trending_tokens():
    #url = "https://public-api.birdeye.so/defi/token_trending"
    #headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    #params = {"sort_by": "volume24hUSD", "sort_type": "desc", "offset": 0, "limit": 50}
    #try:
        #response = requests.get(url, headers=headers, params=params, timeout=15)
        #return response.json().get("data", {}).get("tokens", [])
    #except:
        #return []
def get_trending_tokens():
    url = "https://public-api.birdeye.so/defi/token_trending"
    headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}
    
    # --- デバッグ用追加コード ---
    if not BIRDEYE_API_KEY:
        print("DEBUG: APIキーが環境変数から読み込めていません！")
    else:
        print(f"DEBUG: APIキーを検知しました (先頭4文字: {BIRDEYE_API_KEY[:4]}...)")
    # --------------------------

    try:
        response = requests.get(url, headers=headers, timeout=15)
        # 応答コードを表示（200以外なら失敗）
        print(f"DEBUG: API応答ステータスコード: {response.status_code}")
        
        if response.status_code != 200:
            print(f"DEBUG: エラー内容: {response.text}")
            
        return response.json().get("data", {}).get("tokens", [])
    except Exception as e:
        print(f"DEBUG: 通信エラー発生: {e}")
        return []

def main():
    if not BIRDEYE_API_KEY:
        print("[!] 警告: APIキーが環境変数に設定されていません。")
        return

    tokens = get_trending_tokens()
    print(f"\n>>> モメンタム・スキャン開始 (全{len(tokens)}件) <<<")
    
    passed_count = 0
    for token in tokens:
        ca = token.get("address")
        symbol = token.get("symbol")
        liquidity = float(token.get("liquidity", 0) or 0)
        v24h = float(token.get("volume24hUSD", 0) or 0)
        v1h = float(token.get("volume1hUSD", 0) or 0)
        
        avg_v1h = v24h / 24 if v24h > 0 else 0
        is_accelerating = v1h > (avg_v1h * 1.2)
        
        if (15000 <= liquidity <= 300000) and is_accelerating and (v1h > liquidity * 0.1):
            if is_rugcheck_safe(ca):
                passed_count += 1
                msg = (
                    f"🔥 **【加速検知】: {symbol}**\n"
                    f"```text\n"
                    f"加速率: {v1h/avg_v1h:.1f}倍 / 1h出来高: ${v1h:,.0f}\n"
                    f"流動性: ${liquidity:,.0f}\n"
                    f"```\n"
                    f"🔍 **最終毒味(BubbleMaps)**: https://app.bubblemaps.io/sol/token/{ca}\n"
                    f"📊 **チャート(GMGN)**: https://gmgn.ai/sol/token/{ca}"
                )
                send_to_discord(msg)
        time.sleep(0.5)

    print(f"\n>>> スキャン完了: {passed_count}件を通知しました。")

if __name__ == "__main__":
    main()
