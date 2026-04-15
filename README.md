# VPN Tunnel Provisioning — Hub-and-Spoke (Cisco ASA)

Automates end-to-end IPsec IKEv2 tunnel provisioning between a hub ASA and spoke ASAs. Handles IP allocation, certificate-based auth, BGP neighbor config, verification, rollback, and SNOW/NetBox closeout — all from a single workflow execution.

**Platform project:** `69dfaa0d8bd76ce3c64563f9`
**Platform:** https://platform-6-aidev.se.itential.io/automation-studio/#/project/69dfaa0d8bd76ce3c64563f9

---

## What It Does

```
Operator submits inputs
        │
        ▼
Pre-Flight Check ── validates SNOW ticket, device reachability, trustpoints
        │
        ▼
Tunnel Design ────── allocates /30 from NetBox, derives crypto map seq number
        │
        ▼
Config Backup ────── snapshots hub + spoke configs before any change
        │
        ▼
Configure Hub ────── pushes crypto map entry + BGP neighbor to hub ASA
        │
        ▼
Configure Spoke ─── pushes full IKEv2 + BGP config to spoke ASA
        │
        ▼
Verify Tunnel ────── checks IKEv2 SA, BGP adjacency, ping both directions
        │ failure → Rollback → Close Out (Failed)
        ▼
Close Out ────────── updates SNOW to Implemented, creates NetBox IP records
```

---

## Prerequisites

Before running, complete these one-time setup steps:

### 1. Register ASA Devices

Register your hub and spoke ASAs in both `selab-iag-4.4` (for CLI execution) and `ConfigurationManager` (for config backup). Each ASA needs SSH access credentials.

### 2. Install Certificates on ASAs

IKEv2 cert-based auth requires certificate trustpoints pre-installed on each device. The workflow references the trustpoint by name — it does **not** generate or enroll certificates.

```
! On each ASA, verify:
show crypto ca trustpoints
```

### 3. Set Up NetBox Prefix Pool

Create a parent prefix in NetBox designated for tunnel /30 allocations. The workflow finds it by searching with the pool name you provide (default: `netbox`). Mark it as a pool in NetBox.

### 4. ServiceNow Change Ticket

Every provisioning run requires a **Normal Change Request** in Approved or In-Progress state. The workflow validates the ticket before starting and updates it to Implemented or Failed at close-out.

---

## Crypto Policy (Fixed — "High" Tier)

All tunnels use these parameters — no per-tunnel negotiation:

| Parameter | Value |
|-----------|-------|
| IKEv2 Encryption | AES-256 |
| IKEv2 Integrity | SHA-256 |
| IKEv2 DH Group | Group 14 |
| IKEv2 SA Lifetime | 86400s (24h) |
| IPsec Encryption | AES-256-GCM |
| IPsec Integrity | SHA-256 |
| IPsec PFS | Group 14 |
| IPsec SA Lifetime | 3600s (1h) |
| Authentication | Certificate (IKEv2) |
| Hub BGP AS | 65000 (hardcoded) |

---

## Running a Single Tunnel

Open the **VPN - Single-Spoke Orchestrator** workflow in the project and submit with:

```json
{
  "snow_ticket_id": "CHG0012345",
  "hub_hostname": "ASA-HUB-01",
  "spoke_hostname": "ASA-SPOKE-SITE-A",
  "spoke_site_name": "SITE-A",
  "hub_wan_interface": "GigabitEthernet0/0",
  "spoke_wan_interface": "GigabitEthernet0/0",
  "hub_trustpoint": "HUB-CERT-TP",
  "spoke_trustpoint": "SPOKE-CERT-TP",
  "spoke_as": 65001,
  "netbox_prefix_pool_name": "netbox",
  "crypto_map_name": "VPN-MAP",
  "verify_timeout_minutes": 5
}
```

| Input | Description |
|-------|-------------|
| `snow_ticket_id` | CHG number — must be Approved or In Progress |
| `hub_hostname` | Hostname as registered in ConfigurationManager |
| `spoke_hostname` | Hostname as registered in ConfigurationManager |
| `spoke_site_name` | Used for NetBox record descriptions and evidence |
| `hub_wan_interface` | WAN-facing interface for dynamic IP resolution |
| `spoke_wan_interface` | WAN-facing interface for dynamic IP resolution |
| `hub_trustpoint` | Trustpoint name on hub ASA (`show crypto ca trustpoints`) |
| `spoke_trustpoint` | Trustpoint name on spoke ASA |
| `spoke_as` | Spoke BGP AS number (hub is always 65000) |
| `netbox_prefix_pool_name` | Name/role of the parent prefix pool in NetBox |
| `crypto_map_name` | Crypto map name on hub ASA (e.g. `VPN-MAP`) |
| `verify_timeout_minutes` | How long to wait for IKEv2 SA + BGP (default: 5) |

---

## Running a Batch (Multiple Spokes)

Open the **VPN - Batch Orchestrator** and submit an array of spoke definitions:

```json
{
  "spokes": [
    {
      "snow_ticket_id": "CHG0012345",
      "hub_hostname": "ASA-HUB-01",
      "spoke_hostname": "ASA-SPOKE-SITE-A",
      "spoke_site_name": "SITE-A",
      "hub_wan_interface": "GigabitEthernet0/0",
      "spoke_wan_interface": "GigabitEthernet0/0",
      "hub_trustpoint": "HUB-CERT-TP",
      "spoke_trustpoint": "SPOKE-A-CERT-TP",
      "spoke_as": 65001,
      "netbox_prefix_pool_name": "netbox",
      "crypto_map_name": "VPN-MAP",
      "verify_timeout_minutes": 5
    },
    {
      "snow_ticket_id": "CHG0012345",
      "hub_hostname": "ASA-HUB-01",
      "spoke_hostname": "ASA-SPOKE-SITE-B",
      "spoke_site_name": "SITE-B",
      "hub_wan_interface": "GigabitEthernet0/0",
      "spoke_wan_interface": "GigabitEthernet0/0",
      "hub_trustpoint": "HUB-CERT-TP",
      "spoke_trustpoint": "SPOKE-B-CERT-TP",
      "spoke_as": 65002,
      "netbox_prefix_pool_name": "netbox",
      "crypto_map_name": "VPN-MAP",
      "verify_timeout_minutes": 5
    }
  ]
}
```

The batch runs **sequentially** — one spoke at a time, safe for the shared hub ASA. A single SNOW ticket can cover the full batch.

---

## What Happens on Failure

| Phase that fails | Rollback behavior |
|-----------------|-------------------|
| Pre-Flight Check | No config applied — Close Out (Failed), SNOW updated |
| Tunnel Design | No config applied — Close Out (Failed), SNOW updated |
| Config Backup | No config applied — Close Out (Failed), SNOW updated |
| Configure Hub | Hub config removed — SNOW updated to Failed |
| Configure Spoke | Hub + spoke configs removed — SNOW updated to Failed |
| Verify Tunnel | Hub + spoke configs removed — SNOW updated to Failed |

Rollback restores both devices from their pre-change backups taken during Config Backup.

---

## Project Components

```
vpn-tunnel/
├── customer-spec.md        HLD — business requirements and scope
├── feasibility.md          Platform capability assessment
├── solution-design.md      LLD — component inventory, build order, test plan
├── as-built.md             Delivered state, deviations, diagrams, test checklist
├── build_project.py        Generates project-import.json (run to regenerate)
├── final_deploy.py         Deploys to platform (run to redeploy from scratch)
└── project-import.json     Full project JSON artifact (19 components)
```

---

## MOP Command Templates

| Template | Purpose | Key Variables |
|----------|---------|---------------|
| `CT-ASA-Get-WAN-IP` | Resolve current WAN IP from ASA interface | `wan_interface` |
| `CT-ASA-Verify-Trustpoint` | Confirm cert trustpoint exists on ASA | `trustpoint_name` |
| `CT-ASA-Hub-IPsec-Config` | Push crypto map entry + BGP to hub | `crypto_map_name`, `seq_num`, `spoke_wan_ip`, `hub_trustpoint`, `spoke_tunnel_ip`, `spoke_as` |
| `CT-ASA-Spoke-IPsec-Config` | Push full IPsec + BGP config to spoke | `hub_wan_ip`, `spoke_wan_ip`, `hub_tunnel_ip`, `spoke_tunnel_ip`, `spoke_trustpoint`, `spoke_as` |
| `CT-ASA-Verify-IKEv2-SA` | Check IKEv2 SA is established | none |
| `CT-ASA-Verify-BGP` | Check BGP neighbor adjacency | `neighbor_ip` |
| `CT-ASA-Ping-Tunnel` | Ping across tunnel interface | `target_ip`, `source_ip` |
| `CT-ASA-Hub-Rollback` | Remove hub crypto map + BGP neighbor | `crypto_map_name`, `seq_num`, `spoke_tunnel_ip` |
| `CT-ASA-Spoke-Rollback` | Remove all spoke tunnel config | `hub_wan_ip`, `spoke_as`, `hub_tunnel_ip` |

---

## Adapters Used

| System | Adapter | Purpose |
|--------|---------|---------|
| Cisco ASA (CLI) | `selab-iag-4.4` via MOP | Config push, show commands, verification |
| Config backup | `ConfigurationManager` | Pre-change backup + post-rollback restore |
| IPAM | `netbox-selab` (Netbox) | /30 prefix allocation + IP record creation |
| ITSM | `ServiceNow` (Servicenow) | Change ticket validation + close-out update |

---

## Known Gaps (Fix Before Production)

1. **Tunnel IP forwarding** — Verify Tunnel and Close Out receive hub/spoke tunnel IPs as empty strings from the orchestrator. The Tunnel Design child outputs `hub_tunnel_ip`/`spoke_tunnel_ip` which need to be wired through the orchestrator. Fix in `VPN - Single-Spoke Orchestrator` after confirming NetBox output shape at test time.

2. **WAN IP forwarding** — Pre-Flight Check resolves WAN IPs but the orchestrator does not forward them to Tunnel Design. Wire `preflight.hub_wan_ip` → `tunnel_design.hub_wan_ip` in the orchestrator.

3. **Seq num calculation** — Tunnel Design counts all prefixes in the pool and multiplies by 10 (base 100). Verify this produces non-conflicting seq numbers against existing crypto map entries on the hub.

---

## Delivery Artifacts

| Artifact | Status |
|----------|--------|
| customer-spec.md | ✓ Approved |
| feasibility.md | ✓ Approved |
| solution-design.md | ✓ Approved |
| Platform project | ✓ Deployed — 19 components |
| as-built.md | ✓ Complete |
| GitHub repo | ✓ `keepithuman/vpn-tunnel` |
