import json
import requests
import sys
import time
import os
from colorama import init, Fore, Style

# 📌 THE WINDOWS 10 ABSOLUTE FIX: Forces CMD/PowerShell to turn on ANSI decoding
if os.name == 'nt':
    os.system('color')

# Initialize Colorama with cross-platform wrappers and automated style resetting
init(autoreset=True)

# --- CONFIGURATION ---
RPC_URL = "http://127.0.0.1:37071"
RPC_USER = "### put your username here ###"
RPC_PASS = "### Put your password here ###"

# FILTER: Hide any alternative fork with fewer than this many peers
MIN_PEERS_TO_SHOW = 1  

# Known reliable Pocketcoin / PKOIN seed nodes to jumpstart sync
SEED_NODES = [
    "seed.pocketcoin.app",
    "seed2.pocketcoin.app",
    "seed3.pocketcoin.app",
    "node.pocketnet.app"
]
# ---------------------

# 📌 TERMINAL-SAFE ICON MAP: Uses standard text on Windows, rich icons on Mac/Linux
if os.name == 'nt':
    ICON_CHECK   = "[CHK]"
    ICON_ERROR   = "[ERR]"
    ICON_SUCCESS = "[OK]"
    ICON_ROCKET  = "[RUN]"
    ICON_TREE    = "[TREE]"
    ICON_PLUS    = "[+]"
    ICON_WARN    = "[WARN]"
    ICON_WRENCH  = "[FIX]"
    M_1, M_2, M_3, M_4 = "[1]", "[2]", "[3]", "[4]"
else:
    ICON_CHECK   = "🔍"
    ICON_ERROR   = "❌"
    ICON_SUCCESS = "✅"
    ICON_ROCKET  = "🚀"
    ICON_TREE    = "🌱"
    ICON_PLUS    = "➕"
    ICON_WARN    = "⚠️"
    ICON_WRENCH  = "🛠️"
    M_1, M_2, M_3, M_4 = "1️⃣", "2️⃣", "3️⃣", "4️⃣"

def rpc_call(method, params=[]):
    payload = {"jsonrpc": "2.0", "id": "nodefix", "method": method, "params": params}
    try:
        response = requests.post(RPC_URL, auth=(RPC_USER, RPC_PASS), json=payload, timeout=15)
        res_json = response.json()
        if "error" in res_json and res_json["error"] is not None:
            print(f"{Fore.RED}{ICON_ERROR} RPC Error: {res_json['error']['message']}{Style.RESET_ALL}")
            return None
        return res_json["result"]
    except Exception as e:
        print(f"{Fore.RED}{ICON_ERROR} Failed to reach node: {e}{Style.RESET_ALL}")
        return None

def check_status():
    print(f"\n{ICON_CHECK} --- RUNNING NODE DIAGNOSTICS ---")
    blockchain_info = rpc_call("getblockchaininfo")
    network_info = rpc_call("getnetworkinfo")
    peer_info = rpc_call("getpeerinfo") or []
    
    if not blockchain_info or not network_info:
        print(f"{Fore.RED}{ICON_ERROR} Cannot diagnose. Daemon is offline or RPC credentials are wrong.{Style.RESET_ALL}")
        return

    local_height = blockchain_info.get("blocks")
    headers_height = blockchain_info.get("headers")
    connections = network_info.get("connections")
    is_ibd = blockchain_info.get("initialblockdownload", False)

    print(f"Local Block Height:   {local_height}")
    print(f"Best Header Height:  {headers_height}")
    print(f"Connected Peers:      {connections}")
    print(f"Initial Block Download: {is_ibd}")

    if peer_info:
        peer_heights = [p.get("synced_blocks", 0) for p in peer_info]
        max_peer_height = max(peer_heights) if peer_heights else 0
        print(f"Max Peer Height:      {max_peer_height}")
        
        if local_height < max_peer_height:
            print(f"{Fore.YELLOW}{ICON_WARN} STATUS: Node is lagging behind peers by {max_peer_height - local_height} blocks.{Style.RESET_ALL}")
        elif local_height == max_peer_height and local_height < headers_height:
            print(f"{Fore.YELLOW}{ICON_WARN} STATUS: Node is stuck on a block fork. Peers cannot feed us new blocks.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}{ICON_SUCCESS} STATUS: Node height matches its active peers.{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}{ICON_ERROR} STATUS: CRITICAL! Node has 0 connected peers. It is completely isolated.{Style.RESET_ALL}")

def kickstart_peers():
    print(f"\n{ICON_ROCKET} Clearing banned node list and injecting clean seed connections...")
    rpc_call("clearbanned")
    print(f"{Fore.GREEN}{ICON_SUCCESS} Local node ban list cleared.{Style.RESET_ALL}")
    
    added_count = 0
    for seed in SEED_NODES:
        result = rpc_call("addnode", [seed, "add"])
        if result is not None:
            print(f"{ICON_PLUS} Injected seed peer: {seed}")
            added_count += 1
    print(f"Kickstart complete. Attempted to force-inject {added_count} seed peers.")

def generate_fork_tree():
    print(f"\n{ICON_TREE} --- GENERATING NETWORK FORK TREE ---")
    tips = rpc_call("getchaintips")
    peers = rpc_call("getpeerinfo") or []
    
    if not tips:
        print(f"{Fore.RED}{ICON_ERROR} Could not fetch chaintips metadata from daemon database.{Style.RESET_ALL}")
        return

    total_forks_in_wild = sum(1 for t in tips if t.get("status") != "active")
    print(f"Global Status: Found {Fore.CYAN}{total_forks_in_wild}{Style.RESET_ALL} alternative fork branches in node memory.")
    print(f"Filter Active: Hiding alternative forks with fewer than {MIN_PEERS_TO_SHOW} peers.\n")

    peer_distribution = {}
    for p in peers:
        p_height = p.get("synced_blocks", 0)
        peer_distribution[p_height] = peer_distribution.get(p_height, 0) + 1

    hidden_count = 0

    for idx, tip in enumerate(tips):
        status = tip.get("status")
        height = tip.get("height")
        branch_len = tip.get("branchlen", 0)
        fork_block = height - branch_len
        
        nodes_on_tip = peer_distribution.get(height, 0)
        
        nodes_on_branch = 0
        if branch_len > 0:
            for b_height in range(fork_block + 1, height):
                nodes_on_branch += peer_distribution.get(b_height, 0)
        
        total_nodes_on_fork = nodes_on_tip + nodes_on_branch

        if status == "active":
            peer_label = f" [Nodes on line: {Fore.GREEN}{nodes_on_tip}{Style.RESET_ALL}]" if nodes_on_tip > 0 else " (0 direct peers synced to tip)"
            print(f"{Fore.GREEN}[MAIN CHAIN TIP]{Style.RESET_ALL} (Active Network Node Baseline)")
            print(f"   └── Tip Block: Height {height} (Hash: {tip['hash'][:16]}...){peer_label}\n")
        else:
            if total_nodes_on_fork < MIN_PEERS_TO_SHOW:
                hidden_count += 1
                continue

            peer_label = f" {Fore.RED}[{total_nodes_on_fork} nodes trapped]{Style.RESET_ALL} on this fork line"
            print(f"{Fore.RED}[ALTERNATIVE FORK #{idx}]{Style.RESET_ALL}")
            print(f"   ├── Status Type:  {status}")
            print(f"   ├── Split Height: Branch broken away from Main Chain at block {fork_block}")
            print(f"   ├── Fork Depth:   Progressed {branch_len} blocks deep onto its own path")
            print(f"   └── Branch Tip:   Block {height} (Hash: {tip['hash'][:16]}...){peer_label}\n")
            
    if hidden_count > 0:
        print(f"Note: Automatically hid {hidden_count} dead fork branches with 0 active peers.")

def fix_fork_at_height(height):
    print(f"\n{ICON_WRENCH} Attempting to resolve fork line at block height {height}...")
    block_hash = rpc_call("getblockhash", [int(height)])
    if not block_hash:
        print(f"{Fore.RED}{ICON_ERROR} Could not resolve the hash for that block height.{Style.RESET_ALL}")
        return
        
    print(f"Target Block Hash found: {block_hash}")
    print("Sending 'invalidateblock' payload to node daemon memory...")
    rpc_call("invalidateblock", [block_hash])
    print(f"{Fore.GREEN}{ICON_SUCCESS} Block path marked as invalid.{Style.RESET_ALL}")
    time.sleep(2)
    print("Sending 'reconsiderblock' payload to restart peer synchronization download...")
    rpc_call("reconsiderblock", [block_hash])
    print(f"{Fore.GREEN}{ICON_SUCCESS} Reconsider command sent.{Style.RESET_ALL}")

def menu():
    while True:
        print("\n==================================================")
        print(f"{Fore.CYAN}🛡️  PKOIN NODE ON-CHAIN RECOVERY UTILITY{Style.RESET_ALL}")
        print("==================================================")
        print(f"{M_1}  Run Node Diagnostics & Check Sync Progress")
        print(f"{M_2}  Kickstart Peers (Clear Bans & Force Seed Nodes)")
        print(f"{M_3}  Fix Fork / Invalidate Stuck Block Height")
        print(f"{M_4}  Generate Visual Fork Tree & Peer Map")
        print("[Q]  Quit Utility")
        print("==================================================")
        
        choice = input("👉 Enter Selection: ").strip().lower()
        
        if choice == "1":
            check_status()
        elif choice == "2":
            kickstart_peers()
        elif choice == "3":
            height = input("👉 Enter the block height where your node is stuck: ").strip()
            if height.isdigit():
                fix_fork_at_height(int(height))
            else:
                print(f"{Fore.RED}{ICON_ERROR} Invalid block height format.{Style.RESET_ALL}")
        elif choice == "4":
            generate_fork_tree()
        elif choice in ["q", "quit", "exit"]:
            print("👋 Exiting recovery utility.")
            break
        else:
            print(f"{Fore.RED}{ICON_ERROR} Invalid entry option.{Style.RESET_ALL}")

if __name__ == "__main__":
    menu()
