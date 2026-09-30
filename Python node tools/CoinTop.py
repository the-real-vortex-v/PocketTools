import json
import requests
import time
from unicurses import *  # Using the updated 3.13 compatible wrapper

# --- CONFIGURATION ---
RPC_URL = "http://127.0.0.1:37071"
RPC_USER = "#### Put your username here ####"
RPC_PASS = "#### Put your password here ####"

MIN_COIN_AGE_BLOCKS = 288 
# ---------------------

def rpc_call(method, params=[]):
    payload = {"jsonrpc": "2.0", "id": "nodetop", "method": method, "params": params}
    try:
        response = requests.post(RPC_URL, auth=(RPC_USER, RPC_PASS), json=payload, timeout=10)
        res_json = response.json()
        if "error" in res_json and res_json["error"] is not None:
            return None
        return res_json["result"]
    except:
        return None

def generate_text_report():
    """Calculates all metrics, sorts the unapproved mempool entries from oldest to newest,
    and outputs a complete, untruncated breakdown file."""
    print("📋 Compiling exhaustive wallet metrics and mempool logs...")
    
    block_count = rpc_call("getblockcount") or "N/A"
    mempool_info = rpc_call("getmempoolinfo") or {"size": 0, "bytes": 0}
    unspent_list = rpc_call("listunspent") or []
    verbose_mempool = rpc_call("getrawmempool", [True]) or {}
    
    current_time = time.time()
    report_lines = []
    
    # --- HEADER PANEL ---
    report_lines.append("==========================================================================================")
    report_lines.append(f"⚡ PKOIN NODE SUMMARY REPORT  |  Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"📊 Block Height: {block_count}  |  Mempool Size: {mempool_info.get('size')} txs ({mempool_info.get('bytes')/1024:.1f} KB)")
    report_lines.append("==========================================================================================\n")
    
    # --- SECTION 1: MEMPOOL (SORTED BY AGE - OLDEST FIRST) ---
    report_lines.append("📋 SECTION 1: UNAPPROVED PENDING MEMPOOL TRANSACTIONS (Oldest First)")
    report_lines.append("-" * 120)
    report_lines.append(f"{'Transaction ID (TXID)':<66} | {'Type':<14} | {'Fee Rate':<12} | {'Time in Pool':<12} | {'Fees (PKOIN)':<14}")
    report_lines.append("-" * 120)
    
    if not verbose_mempool:
        report_lines.append("✨ Mempool is completely empty. No pending transactions found.")
    else:
        # Sort key logic: lowest timestamp (oldest transaction) goes to the top
        sorted_mempool = sorted(verbose_mempool.items(), key=lambda x: x[1].get("time", current_time))
        
        for txid, txdata in sorted_mempool:
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
                age_str = f"{age_seconds // 3600}h { (age_seconds % 3600) // 60 }m"
                
            report_lines.append(f"{txid:<66} | {tx_type:<14} | {feerate:<7} sat/vB | {age_str:<12} | {base_fee_pkoin:<14.8f}")
            
    # --- SECTION 2: BALANCES ---
    report_lines.append("\n\n💰 SECTION 2: LARGE WALLET ADDRESSES BALANCE DISTRIBUTION")
    report_lines.append("-" * 80)
    report_lines.append(f"{'Address':<45} | {'Balance (PKOIN)':<25}")
    report_lines.append("-" * 80)
    
    balances = {}
    for utxo in unspent_list:
        addr = utxo.get("address", "Unknown")
        balances[addr] = balances.get(addr, 0.0) + utxo.get("amount", 0.0)
    sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)
    
    for addr, amt in sorted_balances:
        flag = " 🔥 (FULL CEILING)" if amt >= 1000.0 else ""
        report_lines.append(f"{addr:<45} | {amt:<25.8f}{flag}")
        
    # --- SECTION 3: MATURITY ---
    report_lines.append("\n\n⏳ SECTION 3: UTXO COOLDOWN MATURITY WATCH")
    report_lines.append("-" * 80)
    report_lines.append(f"{'Address':<45} | {'Confirmations':<15} | {'Status':<20}")
    report_lines.append("-" * 80)
    
    immature_utxos = [u for u in unspent_list if u.get("confirmations", 0) < MIN_COIN_AGE_BLOCKS]
    immature_utxos.sort(key=lambda x: x.get("confirmations", 0), reverse=True)
    
    if not immature_utxos:
        report_lines.append("✅ All outputs are mature and ready for Phase 1 or Phase 2 loops.")
    else:
        for utxo in immature_utxos:
            conf = utxo.get("confirmations", 0)
            addr = utxo.get("address", "Unknown")
            status = "🆕 Unconfirmed" if conf == 0 else f"⏳ Cooldown ({MIN_COIN_AGE_BLOCKS - conf} left)"
            report_lines.append(f"{addr:<45} | {conf:<15} | {status}")
            
    # Compile output data maps
    full_report_text = "\n".join(report_lines)
    
    # Save output cleanly onto Windows file structure space
    filename = "Pkoin report.txt"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(full_report_text)
        
    # Echo output cleanly directly to active terminal space
    print(full_report_text)
    print(f"\n💾 Complete untruncated breakdown log successfully recorded to: {os.path.abspath(filename)}")
def draw_dashboard(stdscr):
    curs_set(0)
    nodelay(stdscr, True)
    current_view = 1 
    
    while True:
        clear()  
        height, width = getmaxyx(stdscr)
        
        block_count = rpc_call("getblockcount") or "N/A"
        mempool_info = rpc_call("getmempoolinfo") or {"size": 0, "bytes": 0}
        unspent_list = rpc_call("listunspent") or []
        
        # 📌 FIX: Added explicit key numbers, [2], [3] directly into the interface header
        mvaddstr(0, 0, f"⚡ NODE-TOP | Blocks: {block_count} | Mempool: {mempool_info.get('size')} txs ({mempool_info.get('bytes')/1024:.1f} KB)")
        mvaddstr(1, 0, " [1] Unapproved Mempool    [2] Wallet Balances    [3] Maturity Watch    [Q] Quit")
        mvaddstr(2, 0, "-" * (width - 1))
        
        if current_view == 1:
            mvaddstr(3, 0, "📋 VIEW: DETAILED PENDING MEMPOOL TRANSACTIONS (Oldest First)")
            verbose_mempool = rpc_call("getrawmempool", [True]) or {}
            
            if not verbose_mempool:
                mvaddstr(5, 2, "✨ Mempool is completely empty. No transactions pending.")
            else:
                mvaddstr(5, 0, f"{'Transaction ID (TXID)':<66} | {'Type':<12} | {'Fee Rate':<12} | {'Age':<6} | {'Fees (PKOIN)':<14}")
                mvaddstr(6, 0, "=" * (width - 1))
                
                current_time = time.time()
                
                # 📌 FIX: Sorted by the 'time' value so the smallest timestamp (oldest transaction) sits at the top
                sorted_mempool = sorted(verbose_mempool.items(), key=lambda x: x[1].get("time", current_time))
                
                for idx, (txid, txdata) in enumerate(sorted_mempool):
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
                        
                    mvaddstr(7 + idx, 0, f"{txid:<66} | {tx_type:<12} | {feerate:<7} sat/vB | {age_str:<4} | {base_fee_pkoin:<14.8f}")

        elif current_view == 2:
            mvaddstr(3, 0, "💰 VIEW: LARGE WALLET ADDRESSES DISTRIBUTION")
            balances = {}
            for utxo in unspent_list:
                addr = utxo.get("address", "Unknown")
                balances[addr] = balances.get(addr, 0.0) + utxo.get("amount", 0.0)
            
            sorted_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)
            
            mvaddstr(5, 0, f"{'Address':<40} | {'Balance (PKOIN)':<25}")
            mvaddstr(6, 0, "=" * (width - 1))
            for idx, (addr, amt) in enumerate(sorted_balances):
                if 7 + idx >= height - 2:
                    break
                flag = " 🔥 (FULL CEILING)" if amt >= 1000.0 else ""
                mvaddstr(7 + idx, 0, f"{addr:<40} | {amt:<25.8f}{flag}")
                    
        elif current_view == 3:
            mvaddstr(3, 0, f"⏳ VIEW: UTXO MATURITY TRACKER")
            mvaddstr(5, 0, f"{'Address':<40} | {'Confirmations':<15} | {'Status':<20}")
            mvaddstr(6, 0, "=" * (width - 1))
            
            immature_utxos = [u for u in unspent_list if u.get("confirmations", 0) < MIN_COIN_AGE_BLOCKS]
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
    if len(sys.argv) > 1 and sys.argv[1].lower() == "--report":
        generate_text_report()
    else:
        stdscr = initscr()
        try:
            draw_dashboard(stdscr)
        finally:
            endwin()
