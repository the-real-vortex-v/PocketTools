import json
import requests
import time
import sys
# --- CONFIGURATION ---
RPC_URL = "http://127.0.0.1:37071"
RPC_USER = "#### Put your username here ####"
RPC_PASS = "#### Put your password here ####"

WALLET_PASSPHRASE = ""       # Leave empty "" if unencrypted
UTXO_COUNT_THRESHOLD = 5     # Fragmented address threshold
MIN_COIN_AGE_BLOCKS = 288    # Confirmation age for "mature" coins
TARGET_CAP = 1000.0          # Target balance ceiling per address
FEE_ESTIMATE = 0.005         # Flat transaction fee
DUST_LIMIT = 0.00010000
MAX_INPUTS_PER_TX = 100      # Keep transaction sizes well under the 100KB limit
ASSUME_YES = False           # Overridden to True if --yes is passed via CLI
# ---------------------

def rpc_call(method, params=[]):
    payload = {"jsonrpc": "2.0", "id": "pkoin-smart-filler", "method": method, "params": params}
    try:
        response = requests.post(RPC_URL, auth=(RPC_USER, RPC_PASS), json=payload, timeout=30)
        res_json = response.json()
        if "error" in res_json and res_json["error"] is not None:
            raise Exception(f"RPC Error: {res_json['error']}")
        return res_json["result"]
    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        exit(1)

def run_dry_run_simulation(address_data, fillable_addresses, TARGET_CAP):
    """
    Scans the local wallet dictionary mapping and prints out a clear 
    blueprint of the actions Phase 1 and Phase 2 will execute.
    """
    print("\n🧐 ================= DRY-RUN SIMULATION PREVIEW ================= 🧐")
    if not fillable_addresses:
        print("✅ No fillable addresses found under the target cap. Nothing to do!")
        return False

    # Pull target details safely from index 0 of the sorted list array
    target_addr = fillable_addresses[0]["address"]
    current_bal = fillable_addresses[0]["balance"]
    needed = round(TARGET_CAP - current_bal, 8)
    
    print(f"🎯 Target Address to Fill: {target_addr}")
    print(f"   └── Current Balance: {current_bal:.8f} | Space Remaining: {needed:.8f} PKOIN")
    
    print("\n📋 Simulated Phase 1: Moving mature funds to target bucket...")
    sim_received = 0.0
    for addr, data in address_data.items():
        if addr == target_addr or sim_received >= needed:
            continue
            
        mature_count = sum(1 for tx in data["utxos"] if tx.get("confirmations", 0) >= MIN_COIN_AGE_BLOCKS)
        mature_funds = sum(tx["amount"] for tx in data["utxos"] if tx.get("confirmations", 0) >= MIN_COIN_AGE_BLOCKS)
        
        if mature_count > UTXO_COUNT_THRESHOLD:
            movable = round(mature_funds - FEE_ESTIMATE, 8)
            if movable > 0:
                print(f"   ├── Will pull {mature_count} inputs from source: {addr[:12]}...")
                if movable > (needed - sim_received):
                    chunk = round(needed - sim_received, 8)
                    print(f"   │   └── Sending {chunk:.8f} to target (Sending remaining change back to source)")
                    sim_received = needed
                else:
                    print(f"   │   └── Sending {movable:.8f} to target bucket")
                    sim_received = round(sim_received + movable, 8)

    print("\n📋 Simulated Phase 2: Internal fragmentation sweep...")
    for addr, data in address_data.items():
        mature_count = sum(1 for tx in data["utxos"] if tx.get("confirmations", 0) >= MIN_COIN_AGE_BLOCKS)
        if mature_count > UTXO_COUNT_THRESHOLD:
            print(f"   └── Address {addr[:12]}... has {mature_count} fragmented inputs. Will smash internally.")
            
    print("====================================================================")
    return True

def display_and_wait_for_targets(waiting_list):
    if not waiting_list:
        return
    print("\n📋 ================= ACTIVE MATURITY WATCHLIST ================= 📋")
    print(f"{'Phase':<10} | {'Address':<12} | {'TxID Snippet':<18} | {'Target Block':<12}")
    print("-" * 62)
    for item in waiting_list:
        print(f"{item['phase']:<10} | {item['address'][:12]} | {item['txid'][:16]}... | {item['target_block']:<12}")
    print("=" * 62)

    target_block = min(item['target_block'] for item in waiting_list)
    while True:
        current_block = int(rpc_call("getblockcount"))
        blocks_remaining = target_block - current_block
        if blocks_remaining <= 0:
            print("\n\n✅ Target block milestone reached! Resuming wallet sweep...")
            break
        for seconds_left in range(60, 0, -1):
            sys.stdout.write(
                f"\r⏱️  Current Block: {current_block} | Next Target: {target_block} ({blocks_remaining} blocks left) | Next Node Poll: {seconds_left}s  "
            )
            sys.stdout.flush()
            time.sleep(1)

def main():
    blockchain_waiting_list = []

    while True:
        current_block = int(rpc_call("getblockcount"))
        blockchain_waiting_list = [item for item in blockchain_waiting_list if current_block < item['target_block']]

        if blockchain_waiting_list:
            display_and_wait_for_targets(blockchain_waiting_list)
            continue

        print("\n======================= NEW CONSOLIDATION LOOP =======================")
        print("🔄 Mapping wallet structure for exhaustive multi-stage consolidation...")
        unspent = rpc_call("listunspent")
        
        address_data = {}
        has_unconfirmed = False
        global_used_utxos = set()
        
        for utxo in unspent:
            if not utxo.get("spendable", False):
                continue
            if utxo.get("confirmations", 0) == 0:
                has_unconfirmed = True
                
            addr = utxo.get("address")
            if not addr:
                continue
                
            if addr not in address_data:
                address_data[addr] = {"total_balance": 0.0, "utxos": []}
                
            address_data[addr]["total_balance"] += utxo["amount"]
            address_data[addr]["utxos"].append(utxo)

        fillable_addresses = [
            {"address": addr, "balance": data["total_balance"]}
            for addr, data in address_data.items()
            if data["total_balance"] < TARGET_CAP
        ]
        fillable_addresses.sort(key=lambda x: x["balance"], reverse=False)
        # --- UNATTENDED CLI SWITCH & SIMULATION INTERLOCK ---
        global ASSUME_YES
        if len(sys.argv) > 1 and sys.argv[1].lower() == "--yes":
            ASSUME_YES = True
            print("🚀 Unattended Mode Enabled via command-line flag.")

        run_dry_run_simulation(address_data, fillable_addresses, TARGET_CAP)
        
        if not ASSUME_YES:
            confirm = input("\n❓ Proceed with these live blockchain movements? (y/n): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("👋 Consolidation cancelled by user. Exiting script.")
                sys.exit(0)
            print("✅ Confirmation received. Initiating execution cycles...")
            ASSUME_YES = True  # Mutes the prompt for subsequent blocks in this run

        # Safely index the first element of our sorted array to locate our targets
        destination_address = fillable_addresses[0]["address"] if fillable_addresses else None
        max_receivable = round(TARGET_CAP - fillable_addresses[0]["balance"], 8) if fillable_addresses else TARGET_CAP

        transactions_broadcasted = 0

        if WALLET_PASSPHRASE:
            rpc_call("walletpassphrase", [WALLET_PASSPHRASE, 60])

        try:
            # 1. PHASE 1: Fill target buckets to the target threshold
            print("\n📋 Running Phase 1: Filling target buckets...")
            for addr, data in address_data.items():
                if not destination_address or addr == destination_address:
                    continue

                mature_utxos = [
                    tx for tx in data["utxos"] 
                    if tx.get("confirmations", 0) >= MIN_COIN_AGE_BLOCKS
                    and f"{tx['txid']}:{tx['vout']}" not in global_used_utxos
                ]
                
                while len(mature_utxos) > UTXO_COUNT_THRESHOLD and max_receivable > 0:
                    batch = mature_utxos[:MAX_INPUTS_PER_TX]
                    mature_utxos = mature_utxos[MAX_INPUTS_PER_TX:] 
                    
                    tx_inputs = [{"txid": tx["txid"], "vout": tx["vout"]} for tx in batch]
                    total_movable = sum(tx["amount"] for tx in batch)
                    send_amount = round(total_movable - FEE_ESTIMATE, 8)
                    
                    if send_amount <= 0:
                        continue

                    print(f"📥 Batching inputs from {addr[:8]}... to fill target {destination_address[:8]}...")
                    
                    change_amount = 0.0
                    if send_amount > max_receivable:
                        fill_amount = max_receivable
                        change_amount = round(send_amount - fill_amount, 8)
                        tx_outputs = {destination_address: fill_amount}
                        if change_amount >= DUST_LIMIT:
                            tx_outputs[addr] = change_amount
                        max_receivable = 0 
                    else:
                        tx_outputs = {destination_address: send_amount}
                        max_receivable = round(max_receivable - send_amount, 8)

                    txid = execute_transaction(tx_inputs, tx_outputs)
                    if txid:
                        transactions_broadcasted += 1
                        for tx in batch:
                            global_used_utxos.add(f"{tx['txid']}:{tx['vout']}")
                        
                        blockchain_waiting_list.append({
                            "phase": "Phase 1",
                            "address": addr if change_amount >= DUST_LIMIT else destination_address,
                            "txid": txid,
                            "target_block": current_block + 2
                        })

            # 2. PHASE 2: Consolidate remaining small fragmented internal sets
            print("\n📋 Running Phase 2: Internal fragmentation sweep...")
            for addr, data in address_data.items():
                mature_utxos = [
                    tx for tx in data["utxos"] 
                    if tx.get("confirmations", 0) >= MIN_COIN_AGE_BLOCKS
                    and f"{tx['txid']}:{tx['vout']}" not in global_used_utxos
                ]
                
                while len(mature_utxos) > UTXO_COUNT_THRESHOLD:
                    batch = mature_utxos[:MAX_INPUTS_PER_TX]
                    mature_utxos = mature_utxos[MAX_INPUTS_PER_TX:] 
                    
                    print(f"💎 Smashing {len(batch)} small UTXOs inside {addr[:8]}... into one clean UTXO.")
                    
                    tx_inputs = [{"txid": tx["txid"], "vout": tx["vout"]} for tx in batch]
                    total_movable = sum(tx["amount"] for tx in batch)
                    send_amount = round(total_movable - FEE_ESTIMATE, 8)
                    
                    tx_outputs = {addr: send_amount}
                    
                    txid = execute_transaction(tx_inputs, tx_outputs)
                    if txid:
                        transactions_broadcasted += 1
                        for tx in batch:
                            global_used_utxos.add(f"{tx['txid']}:{tx['vout']}")
                        
                        blockchain_waiting_list.append({
                            "phase": "Phase 2",
                            "address": addr,
                            "txid": txid,
                            "target_block": current_block + MIN_COIN_AGE_BLOCKS
                        })

        finally:
            if WALLET_PASSPHRASE:
                rpc_call("walletlock")

        print("\n🏁 ================= RUN SUMMARY ================= 🏁")
        print(f"🚀 Sent out {transactions_broadcasted} transaction batches during this sweep.")
        
        if not blockchain_waiting_list and not has_unconfirmed:
            print("\n✅ Wallet consolidation structure is immaculate and fully optimized!")
            print("👋 Execution complete. Turning off script.")
            break
        elif has_unconfirmed and not blockchain_waiting_list:
            print("\n⏳ Unconfirmed external activity detected. Waiting 2 blocks for structural safety...")
            blockchain_waiting_list.append({
                "phase": "External",
                "address": "Mempool",
                "txid": "Unknown_Activity",
                "target_block": current_block + 2
            })

def execute_transaction(tx_inputs, tx_outputs):
    try:
        raw_tx = rpc_call("createrawtransaction", [tx_inputs, tx_outputs])
        if not raw_tx:
            print("❌ Node refused to build the raw transaction framework.")
            return None
            
        signed_tx = rpc_call("signrawtransactionwithwallet", [raw_tx])
        if not signed_tx:
            print("❌ Node refused to call the wallet signature framework.")
            return None
            
        if signed_tx.get("complete", False):
            txid = rpc_call("sendrawtransaction", [signed_tx["hex"]])
            print(f"✅ Broadcast Success! TxID: {txid[:16]}...")
            return txid
        else:
            print("❌ Failed to complete the signature framework for this batch.")
            if "errors" in signed_tx:
                print(f"⚠️  Node Signature Error Log: {signed_tx['errors']}")
            return None
            
    except Exception as e:
        print(f"❌ Execution failure on this batch: {e}")
        return None

if __name__ == "__main__":
    main()
