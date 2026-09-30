import json
import requests
import time
import sys
import os
from unicurses import *  # Using the updated 3.13 compatible wrapper

# --- CONFIGURATION ---
RPC_URL = "http://127.0.0.1:37071"
RPC_USER = "#### put your username here ####"
RPC_PASS = "#### put your password here ####"

MIN_COIN_AGE_BLOCKS = 288 # ---------------------
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
    print("📋 Compiling exhaustive wallet metrics and mempool logs...")
    
    block_count = rpc_call("getblockcount") or "N/A"
    mempool_info = rpc_call("getmempoolinfo") or {"size": 0, "bytes": 0}
    unspent_list = rpc_call("listunspent") or []
    verbose_mempool = rpc_call("getrawmempool", [True]) or {}
    wallet_info = rpc_call("getwalletinfo") or {}
    
    # Extract total wallet balance states
    total_wallet_balance = wallet_info.get("balance", 0.0)
    total_immature = wallet_info.get("immature_balance", 0.0)
    total_mature = round(total_wallet_balance - total_immature, 8)
    
    current_time = time.time()
    report_lines = []
    
    report_lines.append("==========================================================================================")
    report_lines.append(f"⚡ PKOIN NODE SUMMARY REPORT  |  Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"💰 Total Wallet Balance: {total_wallet_balance:.8f} PKOIN")
    report_lines.append(f"   ├── Mature Funds:    {total_mature:.8f} PKOIN")
    report_lines.append(f"   └── Immature Funds:  {total_immature:.8f} PKOIN")
    mempool_size = mempool_info.get('size', {}).get('memory', 0) if isinstance(mempool_info.get('size'), dict) else mempool_info.get('size', 0)
    report_lines.append(f"📊 Block Height: {block_count}  |  Mempool Size: {mempool_size} txs ({mempool_info.get('bytes', 0)/1024:.1f} KB)")
    report_lines.append("==========================================================================================\n")
    
    # --- SECTION 1: MEMPOOL (OLDEST FIRST) ---
    report_lines.append("📋 SECTION 1: UNAPPROVED PENDING MEMPOOL TRANSACTIONS (Oldest First)")
    report_lines.append("-" * 135)
    report_lines.append(f"{'Transaction ID (TXID)':<66} | {'Type':<14} | {'Fee Rate':<12} | {'Time in Pool':<12} | {'Fees (PKOIN)':<14}")
    report_lines.append("-" * 135)
    
    if not verbose_mempool:
        report_lines.append("✨ Mempool is completely empty. No pending transactions found.")
    else:
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
                age_str = f"{age_seconds // 3600}h {(age_seconds % 3600) // 60}m"
                
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
        
    # --- SECTION 3: MATURITY WATCH ---
    report_lines.append("\n\n⏳ SECTION 3: UTXO COOLDOWN MATURITY WATCH (Soonest to Mature First)")
    report_lines.append("-" * 135)
    report_lines.append(f"{'Address':<35} | {'Confs':<6} | {'Remaining':<10} | {'Type':<12} | {'Amount (PKOIN)':<16} | {'Fees (PKOIN)':<12}")
    report_lines.append("-" * 135)
    
    immature_utxos = [u for u in unspent_list if u.get("confirmations", 0) < MIN_COIN_AGE_BLOCKS]
    immature_utxos.sort(key=lambda x: x.get("confirmations", 0), reverse=True)
    
    if not immature_utxos:
        report_lines.append("✅ All outputs are mature and ready for Phase 1 or Phase 2 loops.")
    else:
        for utxo in immature_utxos:
            conf = utxo.get("confirmations", 0)
            remaining_blocks = max(0, MIN_COIN_AGE_BLOCKS - conf)
            remaining_str = "🆕 Unconf" if conf == 0 else f"{remaining_blocks} blks"
            
            addr = utxo.get("address", "Unknown")[:35]
            amount = utxo.get("amount", 0.0)
            txid = utxo.get("txid")
            
            tx_type = "Transfer"
            fee_pkoin = 0.00000000
            
            if txid:
                tx_details = rpc_call("gettransaction", [txid])
                if tx_details:
                    if "type" in tx_details:
                        tx_type = str(tx_details["type"])
                    elif "action" in tx_details:
                        tx_type = str(tx_details["action"])
                    
                    fee_pkoin = abs(tx_details.get("fee", 0.0))
                    if fee_pkoin == 0.0 and len(tx_details.get("details", [])) > 0:
                        tx_type = "Consolidation"
                        fee_pkoin = 0.00500000
                        
            report_lines.append(f"{addr:<35} | {conf:<6} | {remaining_str:<10} | {tx_type:<12} | {amount:<16.8f} | {fee_pkoin:<12.8f}")
            
    full_report_text = "\n".join(report_lines)
    filename = "Pkoin report.txt"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(full_report_text)
        
    print(full_report_text)
    print(f"\n💾 Complete untruncated log successfully written to: {os.path.abspath(filename)}")
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
        wallet_info = rpc_call("getwalletinfo") or {}
        
        # Calculate full wallet states securely from the node core balance database
        total_wallet_balance = wallet_info.get("balance", 0.0)
        total_immature = wallet_info.get("immature_balance", 0.0)
        total_mature = round(total_wallet_balance - total_immature, 8)
        
        mempool_size = (
            mempool_info.get('size', {}).get('memory', 0) 
            if isinstance(mempool_info.get('size'), dict) 
            else mempool_info.get('size', 0)
        )
        
        # Header displaying all three explicit balance fields across the top row
        mvaddstr(
            0, 0, 
            f"⚡ Total: {total_wallet_balance:.4f} | Mature: {total_mature:.4f} | "
            f"Immature: {total_immature:.4f} PKOIN | Blocks: {block_count} | "
            f"Mempool: {mempool_size} txs"
        )
        # 📌 FIX: Restored shortcut visibility directly inside key bar
        mvaddstr(
            1, 0, 
            " [1] Unapproved Mempool    [2] Wallet Balances    "
            "[3] Maturity Watch    [Q] Quit"
        )
        mvaddstr(2, 0, "-" * (width - 1))
        
        # ----------------------------------------------------
        # VIEW 1: ADVANCED UNAPPROVED MEMPOOL METRICS (OLDEST FIRST)
        # ----------------------------------------------------
        if current_view == 1:
            mvaddstr(
                3, 0, 
                "📋 VIEW: DETAILED PENDING MEMPOOL TRANSACTIONS (Oldest First)"
            )
            verbose_mempool = rpc_call("getrawmempool", [True]) or {}
            
            if not verbose_mempool:
                mvaddstr(
                    5, 2, "✨ Mempool is completely empty. No transactions pending."
                )
            else:
                mvaddstr(
                    5, 0, 
                    f"{'Transaction ID (TXID)':<66} | {'Type':<12} | "
                    f"{'Fee Rate':<12} | {'Age':<6} | {'Fees (PKOIN)':<14}"
                )
                mvaddstr(6, 0, "=" * (width - 1))
                
                current_time = time.time()
                # 📌 FIX: Adjusted sort tracker loop parameter to target item indexes safely
                sorted_mempool = sorted(
                    verbose_mempool.items(), 
                    key=lambda x: x[1].get("time", current_time)
                )
                
                # --- VIEW 1 LOOP FRAMES: RENDER MEMPOOL ROWS ---
                for idx, (txid, txdata) in enumerate(sorted_mempool):
                    if 7 + idx >= height - 2:
                        break
                    
                    tx_type = "Transfer"
                    if "type" in txdata:
                        tx_type = str(txdata["type"])
                    elif "action" in txdata:
                        tx_type = str(txdata["action"])
                    elif (
                        txdata.get("ancestorcount", 1) > 1 and
                        txdata.get("fees", {}).get("base", 0.0) == 0.005
                    ):
                        tx_type = "Consolidation"
                        
                    vsize = txdata.get("vsize", txdata.get("size", 1))
                    base_fee_pkoin = 0.0
                    if isinstance(txdata.get("fees"), dict):
                        base_fee_pkoin = txdata.get("fees", {}).get("base", 0.0)
                    if base_fee_pkoin == 0.0:
                        base_fee_pkoin = txdata.get("fee", 0.0)
                        
                    satoshis_fee = base_fee_pkoin * 100_000_000
                    feerate = (
                        round(satoshis_fee / vsize, 1) if vsize > 0 else 0.0
                    )
                    
                    entry_time = txdata.get("time", current_time)
                    age_seconds = int(current_time - entry_time)
                    if age_seconds < 60:
                        age_str = f"{age_seconds}s"
                    elif age_seconds < 3600:
                        age_str = f"{age_seconds // 60}m"
                    else:
                        age_str = f"{age_seconds // 3600}h"
                        
                    mvaddstr(
                        7 + idx, 0,
                        f"{txid:<66} | {tx_type:<12} | {feerate:<7} sat/vB | "
                        f"{age_str:<4} | {base_fee_pkoin:<14.8f}"
                    )
                    
        # ----------------------------------------------------
        # VIEW 2: WALLET DISTRIBUTION VIEW
        # ----------------------------------------------------
        elif current_view == 2:
            mvaddstr(3, 0, "💰 VIEW: LARGE WALLET ADDRESSES DISTRIBUTION")
            balances = {}
            for utxo in unspent_list:
                addr = utxo.get("address", "Unknown")
                balances[addr] = (
                    balances.get(addr, 0.0) + utxo.get("amount", 0.0)
                )
            sorted_balances = sorted(
                balances.items(), key=lambda x: x[1], reverse=True
            )
            
            mvaddstr(5, 0, f"{'Address':<40} | {'Balance (PKOIN)':<25}")
            mvaddstr(6, 0, "=" * (width - 1))
            for idx, (addr, amt) in enumerate(sorted_balances):
                if 7 + idx >= height - 2:
                    break
                flag = " 🔥 (FULL CEILING)" if amt >= 1000.0 else ""
                mvaddstr(
                    7 + idx, 0, f"{addr:<40} | {amt:<25.8f}{flag}"
                )
                
        # ----------------------------------------------------
        # VIEW 3: COOLDOWN MATURITY MONITORING WITH REMAINING BLOCKS
        # ----------------------------------------------------
        elif current_view == 3:
            mvaddstr(
                3, 0,
                "⏳ VIEW: UTXO MATURITY TRACKER (Soonest to Remove First)"
            )
            mvaddstr(
                5, 0,
                f"{'Address':<35} | {'Confs':<6} | {'Remaining':<10} | "
                f"{'Type':<12} | {'Amount':<14} | {'Fees (PKOIN)':<12}"
            )
            mvaddstr(6, 0, "=" * (width - 1))
            
            immature_utxos = [
                u for u in unspent_list
                if u.get("confirmations", 0) < MIN_COIN_AGE_BLOCKS
            ]
            immature_utxos.sort(
                key=lambda x: x.get("confirmations", 0), reverse=True
            )
            
            if not immature_utxos:
                mvaddstr(7, 2, "All coins are fully mature.")
            else:
                for idx, utxo in enumerate(immature_utxos):
                    if 7 + idx >= height - 2:
                        break
                        
                    conf = utxo.get("confirmations", 0)
                    remaining_blocks = max(0, MIN_COIN_AGE_BLOCKS - conf)
                    remaining_str = (
                        "🆕 Unconf" if conf == 0 else f"{remaining_blocks} blks"
                    )
                    
                    addr = utxo.get("address", "Unknown")[:35]
                    amount = utxo.get("amount", 0.0)
                    txid = utxo.get("txid")
                    
                    tx_type = "Transfer"
                    fee_pkoin = 0.00000000
                    
                    if txid:
                        tx_details = rpc_call("gettransaction", [txid])
                        if tx_details:
                            if "type" in tx_details:
                                tx_type = str(tx_details["type"])
                            elif "action" in tx_details:
                                tx_type = str(tx_details["action"])
                                
                            fee_pkoin = abs(tx_details.get("fee", 0.0))
                            if (
                                fee_pkoin == 0.0 and
                                len(tx_details.get("details", [])) > 0
                            ):
                                tx_type = "Consolidation"
                                fee_pkoin = 0.00500000
                                
                    mvaddstr(
                        7 + idx, 0,
                        f"{addr:<35} | {conf:<6} | {remaining_str:<10} | "
                        f"{tx_type:<12} | {amount:<14.8f} | {fee_pkoin:<12.8f}"
                    )
                    
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

# --- SCRIPT ENTRY POINT & RUN MODE INTERCEPTOR ---
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "--report":
        generate_text_report()
    else:
        stdscr = initscr()
        try:
            draw_dashboard(stdscr)
        finally:
            endwin()
