import json
import requests
import time
from unicurses import *  # Imports curses functions directly into global scope

# --- CONFIGURATION ---
RPC_URL = "http://127.0.0.1:37071"
RPC_USER = "your_rpc_username"
RPC_PASS = "your_rpc_password"
MIN_COIN_AGE_BLOCKS = 288 
# ---------------------

def rpc_call(method, params=[]):
    payload = {"jsonrpc": "2.0", "id": "nodetop", "method": method, "params": params}
    try:
        response = requests.post(RPC_URL, auth=(RPC_USER, RPC_PASS), json=payload, timeout=5)
        res_json = response.json()
        if "error" in res_json and res_json["error"] is not None:
            return None
        return res_json["result"]
    except:
        return None

def draw_dashboard(stdscr):
    curs_set(0)
    nodelay(stdscr, True)
    
    current_view = 1 
    
    while True:
        clear()  
        height, width = getmaxyx(stdscr)
        
        # Global Header Statistics
        block_count = rpc_call("getblockcount") or "N/A"
        mempool_info = rpc_call("getmempoolinfo") or {"size": 0, "bytes": 0}
        unspent_list = rpc_call("listunspent") or []
        
        # Header Layout Text with clear keyboard indicators
        mvaddstr(0, 0, f"⚡ NODE-TOP | Blocks: {block_count} | Mempool: {mempool_info.get('size')} txs ({mempool_info.get('bytes')/1024:.1f} KB)")
        mvaddstr(1, 0, " Unapproved Mempool    Wallet Balances    Maturity Watch    [Q] Quit")
        mvaddstr(2, 0, "-" * (width - 1))
        
        # ----------------------------------------------------
        # VIEW 1: ADVANCED UNAPPROVED MEMPOOL METRICS WITH TX TYPE
        # ----------------------------------------------------
        if current_view == 1:
            mvaddstr(3, 0, "📋 VIEW: DETAILED PENDING MEMPOOL TRANSACTIONS")
            
            verbose_mempool = rpc_call("getrawmempool", [True]) or {}
            
            if not verbose_mempool:
                mvaddstr(5, 2, "✨ Mempool is completely empty. No transactions pending.")
            else:
                mvaddstr(5, 0, f"{'Transaction ID (TXID)':<66} | {'Type':<12} | {'Fee Rate':<12} | {'Age':<6} | {'Fees (PKOIN)':<10}")
                mvaddstr(6, 0, "=" * (width - 1))
                
                current_time = time.time()
                for idx, (txid, txdata) in enumerate(verbose_mempool.items()):
                    if 7 + idx >= height - 2:
                        break  
                    
                    tx_type = "Transfer"
                    if "type" in txdata:
                        tx_type = str(txdata["type"])
                    elif "action" in txdata:
                        tx_type = str(txdata["action"])
                    elif txdata.get("ancestorcount", 1) > 1 and txdata.get("fees", {}).get("base", 0.0) == 0.005:
                        tx_type = "Consolidation"
                        
                    vsize = txdata.get("vsize", txdata.get("size", 1))
                    
                    base_fee_pkoin = 0.0
                    if isinstance(txdata.get("fees"), dict):
                        base_fee_pkoin = txdata.get("fees", {}).get("base", 0.0)
                    if base_fee_pkoin == 0.0:  
                        base_fee_pkoin = txdata.get("fee", 0.0)
                    
                    satoshis_fee = base_fee_pkoin * 100_000_000
                    feerate = round(satoshis_fee / vsize, 1) if vsize > 0 else 0.0
                    
                    entry_time = txdata.get("time", current_time)
                    age_seconds = int(current_time - entry_time)
                    if age_seconds < 60:
                        age_str = f"{age_seconds}s"
                    elif age_seconds < 3600:
                        age_str = f"{age_seconds // 60}m"
                    else:
                        age_str = f"{age_seconds // 3600}h"
                        
                    mvaddstr(7 + idx, 0, f"{txid:<66} | {tx_type:<12} | {feerate:<7} sat/vB | {age_str:<4} | {base_fee_pkoin:<10.5f}")

        # ----------------------------------------------------
        # VIEW 2: WALLET DISTRIBUTION VIEW
        # ----------------------------------------------------
        elif current_view == 2:
            mvaddstr(3, 0, "💰 VIEW: LARGE WALLET ADDRESSES DISTRIBUTION")
            balances = {}
            for utxo in unspent_list:
                addr = utxo.get("address", "Unknown")
                balances[addr] = balances.get(addr, 0.0) + utxo.get("amount", 0.0)
            
            sorted_balances = sorted(balances.items(), key=lambda x: x, reverse=True)
            
            mvaddstr(5, 0, f"{'Address':<40} | {'Balance (PKOIN)':<25}")
            mvaddstr(6, 0, "=" * (width - 1))
            for idx, (addr, amt) in enumerate(sorted_balances):
                if 7 + idx >= height - 2:
                    break
                flag = " 🔥 (FULL CEILING)" if amt >= 1000.0 else ""
                mvaddstr(7 + idx, 0, f"{addr:<40} | {amt:<25.8f}{flag}")
                    
        # ----------------------------------------------------
        # VIEW 3: COOLDOWN MATURITY MONITORING (SORTED SOONEST TO MATURE FIRST)
        # ----------------------------------------------------
        elif current_view == 3:
            mvaddstr(3, 0, f"⏳ VIEW: UTXO MATURITY TRACKER")
            mvaddstr(5, 0, f"{'Address':<40} | {'Confirmations':<15} | {'Status':<20}")
            mvaddstr(6, 0, "=" * (width - 1))
            
            immature_utxos = [u for u in unspent_list if u.get("confirmations", 0) < MIN_COIN_AGE_BLOCKS]
            
            # 📌 FIX: Added reverse=True so the highest confirmations (closest to maturity) hit the top of the terminal
            immature_utxos.sort(key=lambda x: x.get("confirmations", 0), reverse=True)
            
            if not immature_utxos:
                mvaddstr(7, 2, "All coins are fully mature.")
            else:
                for idx, utxo in enumerate(immature_utxos):
                    if 7 + idx >= height - 2:
                        break
                    conf = utxo.get("confirmations", 0)
                    addr = utxo.get("address", "Unknown")[:40]
                    status = "🆕 Unconfirmed" if conf == 0 else f"⏳ Cooldown ({MIN_COIN_AGE_BLOCKS - conf} left)"
                    mvaddstr(7 + idx, 0, f"{addr:<40} | {conf:<15} | {status:<20}")
                        
        refresh()
        
        ch = getch()
        if ch in [ord('q'), ord('Q')]:
            break
        elif ch == ord('1'):
            current_view = 1
        elif ch == ord('2'):
            current_view = 2
        elif ch == ord('3'):
            current_view = 3
            
        time.sleep(1.0) 

if __name__ == "__main__":
    stdscr = initscr()
    try:
        draw_dashboard(stdscr)
    finally:
        endwin()
