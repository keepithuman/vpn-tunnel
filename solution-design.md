# Solution Design: IPsec VPN Tunnel Provisioning — Hub-and-Spoke (Cisco ASA)

**Date:** 2026-04-15
**Platform:** https://platform-6-aidev.se.itential.io
**Status:** Approved

---

## A. Environment Summary

The platform provides all capabilities required for this use case. CLI execution against Cisco ASA devices is handled by the `selab-iag-4.4` Automation Gateway adapter combined with MOP's `RunCommand` and `RunCommandTemplate` tasks. Config backup and diff are provided by `ConfigurationManager`. NetBox IPAM (`netbox-selab`) is live and has full prefix and IP address management APIs. ServiceNow (`ServiceNow`) is live with Normal Change Request read and update support. `WorkflowBuilder` and `WorkFlowEngine` provide orchestration with conditional branching and child job support. ASA devices are not yet in inventory — they must be registered in `selab-iag-4.4` and `ConfigurationManager` as a pre-deployment step (noted in feasibility).

---

## B. Requirements Resolution

```
┌──────────────────────────────────────────────────────┬────────┬───────────────────────────────────────────┐
│ Spec Requirement                                     │ Status │ Resolution                                │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ Execute CLI commands on Cisco ASA devices            │ ✓      │ MOP RunCommand/RunCommandTemplate          │
│                                                      │        │ via selab-iag-4.4                          │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ Backup and diff ASA running configurations           │ ✓      │ ConfigurationManager — backUpDevice,       │
│                                                      │        │ lookupDiff                                 │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ Apply multi-device config in sequence with           │ ✓      │ WorkflowBuilder child jobs with            │
│ conditions                                           │        │ conditional branching                      │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ Orchestrate multi-step workflows with rollback       │ ✓      │ WorkflowBuilder + WorkFlowEngine           │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ Resolve dynamic WAN IPs from device                  │ ✓      │ MOP RunCommand (show interface) via        │
│                                                      │        │ selab-iag-4.4                              │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ Generate reports from templates                      │ ✓      │ MOP runAnalyticsTemplate +                 │
│                                                      │        │ TemplateBuilder                            │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ NetBox — /30 allocation + tunnel inventory           │ ✓      │ netbox-selab adapter —                     │
│                                                      │        │ getIpamPrefixesIdAvailablePrefixes,        │
│                                                      │        │ postIpamPrefixesIdAvailablePrefixes,       │
│                                                      │        │ patchIpamIpAddressesId                     │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ ServiceNow — ticket validation + close-out           │ ✓      │ ServiceNow adapter —                       │
│                                                      │        │ getNormalChangeRequestById,                │
│                                                      │        │ updateNormalChangeRequestById              │
├──────────────────────────────────────────────────────┼────────┼───────────────────────────────────────────┤
│ PKI / Certificate Authority                          │ ✓      │ Pre-condition only — trustpoint validated  │
│                                                      │        │ on device via show crypto ca trustpoints   │
└──────────────────────────────────────────────────────┴────────┴───────────────────────────────────────────┘
```

---

## C. Design Decisions

```
┌──────────────────────────────────────────────────┬────────────────────────────────────────────────────┐
│ Decision                                         │ In This Environment                                │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ CLI execution method                             │ MOP RunCommand + RunCommandTemplate via             │
│                                                  │ selab-iag-4.4 (no native ASA adapter)              │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Config backup                                    │ ConfigurationManager backUpDevice before any        │
│                                                  │ config push                                        │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Crypto policy                                    │ "High" — IKEv2, AES-256, SHA-256, DH Group 14,     │
│                                                  │ SA lifetime 86400s. AES-256-GCM/SHA-256/PFS14      │
│                                                  │ for IPsec. Hardcoded in command templates.         │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Authentication                                   │ IKEv2 certificate-based. Trustpoint reference      │
│                                                  │ passed as workflow input. Cert pre-installed.      │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ BGP type                                         │ eBGP — hub AS hardcoded 65000. Spoke AS            │
│                                                  │ provided as workflow input per spoke.              │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Crypto map seq number                            │ Auto-incremented from NetBox — Tunnel Design        │
│                                                  │ queries existing tunnel prefixes, derives next      │
│                                                  │ seq (base 100, step 10). No manual input.          │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ IP allocation                                    │ NetBox prefix pool named "netbox" — /30 per        │
│                                                  │ spoke allocated and reserved at design time.        │
│                                                  │ No manual IP input accepted.                       │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ SNOW integration                                 │ Normal Change Request — validate Approved/          │
│                                                  │ In-Progress state before provisioning.             │
│                                                  │ Update to Implemented or Failed at close-out.      │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Batch execution                                  │ Rolling — max 3 spokes parallel.                   │
│                                                  │ Batch Orchestrator fans out to Single-Spoke        │
│                                                  │ Orchestrator per spoke with concurrency limit.     │
├──────────────────────────────────────────────────┼────────────────────────────────────────────────────┤
│ Verification timeout                             │ 5 minutes for IKEv2 SA + BGP adjacency.            │
│                                                  │ Configurable workflow input.                       │
└──────────────────────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## D. Modular Design

Each spec phase maps to an independently testable child workflow. The Single-Spoke Orchestrator sequences them. The Batch Orchestrator drives concurrency over all spokes.

```
Spec Phase                  → Component
─────────────────────────────────────────────────────────────────────
SNOW ticket validation      → Child WF: Pre-Flight Check
WAN IP resolution           → Child WF: Pre-Flight Check
Trustpoint validation       → Child WF: Pre-Flight Check
Device reachability         → Child WF: Pre-Flight Check
NetBox /30 allocation       → Child WF: Tunnel Design
ASA config block generation → Child WF: Tunnel Design
Config backup (pre-change)  → Child WF: Config Backup
Hub ASA config push         → Child WF: Configure Hub
Spoke ASA config push       → Child WF: Configure Spoke
IKEv2/IPsec SA verify       → Child WF: Verify Tunnel
BGP adjacency + ping        → Child WF: Verify Tunnel
Rollback (conditional)      → Child WF: Rollback
Evidence report             → Child WF: Close Out
SNOW + NetBox update        → Child WF: Close Out
─────────────────────────────────────────────────────────────────────
One spoke end-to-end        → Single-Spoke Orchestrator
~25 spokes rolling-3        → Batch Orchestrator
```

---

## E. Component Inventory

```
┌────┬────────────────────────────────────────┬───────────────────────┬──────────┐
│ #  │ Component                              │ Type                  │ Action   │
├────┼────────────────────────────────────────┼───────────────────────┼──────────┤
│ 1  │ CT-ASA-Get-WAN-IP                      │ MOP Command Template  │ Build    │
│ 2  │ CT-ASA-Verify-Trustpoint               │ MOP Command Template  │ Build    │
│ 3  │ CT-ASA-Hub-IPsec-Config                │ MOP Command Template  │ Build    │
│ 4  │ CT-ASA-Spoke-IPsec-Config              │ MOP Command Template  │ Build    │
│ 5  │ CT-ASA-Verify-IKEv2-SA                 │ MOP Command Template  │ Build    │
│ 6  │ CT-ASA-Verify-BGP                      │ MOP Command Template  │ Build    │
│ 7  │ CT-ASA-Ping-Tunnel                     │ MOP Command Template  │ Build    │
│ 8  │ CT-ASA-Hub-Rollback                    │ MOP Command Template  │ Build    │
│ 9  │ CT-ASA-Spoke-Rollback                  │ MOP Command Template  │ Build    │
│ 10 │ Pre-Flight Check                       │ Child Workflow        │ Build    │
│ 11 │ Tunnel Design                          │ Child Workflow        │ Build    │
│ 12 │ Config Backup                          │ Child Workflow        │ Build    │
│ 13 │ Configure Hub                          │ Child Workflow        │ Build    │
│ 14 │ Configure Spoke                        │ Child Workflow        │ Build    │
│ 15 │ Verify Tunnel                          │ Child Workflow        │ Build    │
│ 16 │ Rollback                               │ Child Workflow        │ Build    │
│ 17 │ Close Out                              │ Child Workflow        │ Build    │
│ 18 │ VPN Tunnel Evidence Report             │ TemplateBuilder       │ Build    │
│ 19 │ Single-Spoke Orchestrator              │ Parent Workflow       │ Build    │
│ 20 │ Batch Orchestrator                     │ Parent Workflow       │ Build    │
└────┴────────────────────────────────────────┴───────────────────────┴──────────┘
```

---

## F. Component Detail

### Command Templates (MOP)

| # | Template | Commands | Variables |
|---|---------|----------|-----------|
| CT-01 | CT-ASA-Get-WAN-IP | `show interface {{ wan_interface }}` | `wan_interface` |
| CT-02 | CT-ASA-Verify-Trustpoint | `show crypto ca trustpoints {{ trustpoint_name }}` | `trustpoint_name` |
| CT-03 | CT-ASA-Hub-IPsec-Config | `crypto map {{ crypto_map_name }} {{ seq_num }} match address {{ acl_name }}` `crypto map {{ crypto_map_name }} {{ seq_num }} set peer {{ spoke_wan_ip }}` `crypto map {{ crypto_map_name }} {{ seq_num }} set ikev2 ipsec-proposal HIGH` `crypto map {{ crypto_map_name }} {{ seq_num }} set trustpoint {{ hub_trustpoint }}` `router bgp 65000` ` neighbor {{ spoke_tunnel_ip }} remote-as {{ spoke_as }}` ` neighbor {{ spoke_tunnel_ip }} activate` | `crypto_map_name`, `seq_num` (from NetBox), `acl_name`, `spoke_wan_ip`, `hub_trustpoint`, `spoke_tunnel_ip`, `spoke_as` |
| CT-04 | CT-ASA-Spoke-IPsec-Config | Full IKEv2 policy, IPsec proposal, tunnel group, crypto map, interface tunnel, BGP config | `hub_wan_ip`, `spoke_wan_ip`, `hub_tunnel_ip`, `spoke_tunnel_ip`, `spoke_trustpoint`, `spoke_as` (hub AS hardcoded 65000) |
| CT-05 | CT-ASA-Verify-IKEv2-SA | `show crypto ikev2 sa` | none |
| CT-06 | CT-ASA-Verify-BGP | `show bgp neighbors {{ neighbor_ip }} \| include BGP state` | `neighbor_ip` |
| CT-07 | CT-ASA-Ping-Tunnel | `ping {{ target_ip }} source {{ source_ip }} repeat 5` | `target_ip`, `source_ip` |
| CT-08 | CT-ASA-Hub-Rollback | Remove crypto map entry and BGP neighbor for this spoke | `crypto_map_name`, `seq_num`, `spoke_tunnel_ip`, `hub_as` |
| CT-09 | CT-ASA-Spoke-Rollback | Remove tunnel interface, tunnel group, crypto map, IKEv2 policy | `spoke_wan_ip` |

---

### Child Workflow: Pre-Flight Check
**Inputs:** `snow_ticket_id`, `hub_hostname`, `spoke_hostname`, `hub_wan_interface`, `spoke_wan_interface`, `hub_trustpoint`, `spoke_trustpoint`
**Steps:**
1. `getNormalChangeRequestById` (ServiceNow) — halt if state ≠ Approved/In Progress
2. `isAlive` (ConfigurationManager) on hub — halt if unreachable
3. `isAlive` (ConfigurationManager) on spoke — halt if unreachable
4. MOP `RunCommandTemplate` CT-01 on hub — parse WAN IP from output
5. MOP `RunCommandTemplate` CT-01 on spoke — parse WAN IP from output
6. MOP `RunCommandTemplate` CT-02 on hub — halt if trustpoint not found
7. MOP `RunCommandTemplate` CT-02 on spoke — halt if trustpoint not found
**Outputs:** `hub_wan_ip`, `spoke_wan_ip`, `preflight_status`

---

### Child Workflow: Tunnel Design
**Inputs:** `netbox_prefix_pool_name` (default: `"netbox"`), `spoke_site_name`, `spoke_as`, `hub_wan_ip`, `spoke_wan_ip`, `hub_trustpoint`, `spoke_trustpoint`, `crypto_map_name`
**Steps:**
1. `getIpamPrefixes` (netbox-selab) — look up parent prefix pool by name/role (`netbox_prefix_pool_name`)
2. `getIpamPrefixesIdAvailablePrefixes` (netbox-selab) — request next available /30 from pool
3. `postIpamPrefixesIdAvailablePrefixes` (netbox-selab) — reserve /30 (description = spoke_site_name)
4. Derive hub tunnel IP (.1) and spoke tunnel IP (.2) from reserved /30
5. `getIpamPrefixes` (netbox-selab) — query existing tunnel prefixes to determine next crypto map seq number (count + auto-increment from base, e.g. 100, 110, 120…)
6. JST task — generate hub config variables (seq_num, acl_name, BGP params with hub_as=65000)
7. JST task — generate spoke config variables (hub_as hardcoded 65000)
**Outputs:** `hub_tunnel_ip`, `spoke_tunnel_ip`, `allocated_prefix`, `seq_num`, `hub_config_vars`, `spoke_config_vars`

---

### Child Workflow: Config Backup
**Inputs:** `hub_hostname`, `spoke_hostname`
**Steps:**
1. `backUpDevice` (ConfigurationManager) on hub — store backup ID
2. `backUpDevice` (ConfigurationManager) on spoke — store backup ID
**Outputs:** `hub_backup_id`, `spoke_backup_id`

---

### Child Workflow: Configure Hub
**Inputs:** `hub_hostname`, `hub_config_vars`
**Steps:**
1. MOP `RunCommandTemplate` CT-03 on hub — apply crypto map entry + BGP neighbor
2. Check for config errors in output — halt + flag if errors detected
**Outputs:** `hub_config_status`, `hub_config_output`

---

### Child Workflow: Configure Spoke
**Inputs:** `spoke_hostname`, `spoke_config_vars`
**Steps:**
1. MOP `RunCommandTemplate` CT-04 on spoke — apply full IPsec + BGP config
2. Check for config errors in output — halt + flag if errors detected
**Outputs:** `spoke_config_status`, `spoke_config_output`

---

### Child Workflow: Verify Tunnel
**Inputs:** `hub_hostname`, `spoke_hostname`, `hub_tunnel_ip`, `spoke_tunnel_ip`, `spoke_as`, `verify_timeout_minutes`
**Steps:**
1. MOP `RunCommandTemplate` CT-05 on hub — check IKEv2 SA state (retry up to timeout)
2. MOP `RunCommandTemplate` CT-05 on spoke — check IKEv2 SA state
3. MOP `RunCommandTemplate` CT-06 on hub — check BGP neighbor state toward spoke tunnel IP
4. MOP `RunCommandTemplate` CT-06 on spoke — check BGP neighbor state toward hub tunnel IP
5. MOP `RunCommandTemplate` CT-07 on hub — ping spoke tunnel IP from hub
6. MOP `RunCommandTemplate` CT-07 on spoke — ping hub tunnel IP from spoke
7. All checks pass → return `verify_status: success`; any failure → return `verify_status: failed`
**Outputs:** `verify_status`, `ikev2_sa_hub`, `ikev2_sa_spoke`, `bgp_state_hub`, `bgp_state_spoke`, `ping_hub`, `ping_spoke`

---

### Child Workflow: Rollback
**Inputs:** `hub_hostname`, `spoke_hostname`, `hub_backup_id`, `spoke_backup_id`, `hub_config_vars`, `spoke_config_vars`, `configured_spoke`, `configured_hub`
**Steps:**
1. If `configured_spoke` = true: MOP `RunCommandTemplate` CT-09 on spoke — remove spoke config
2. If `configured_hub` = true: MOP `RunCommandTemplate` CT-08 on hub — remove hub entry
3. `getDeviceBackupById` + restore via `applyDeviceConfig` (ConfigurationManager) — spoke
4. `getDeviceBackupById` + restore via `applyDeviceConfig` (ConfigurationManager) — hub
5. MOP `RunCommand` on hub — verify existing tunnels still up (`show crypto ikev2 sa`)
**Outputs:** `rollback_status`, `rollback_notes`

---

### Child Workflow: Close Out
**Inputs:** `snow_ticket_id`, `spoke_site_name`, `allocated_prefix`, `hub_tunnel_ip`, `spoke_tunnel_ip`, `verify_status`, `rollback_status`, `hub_config_output`, `spoke_config_output`, `hub_backup_id`, `spoke_backup_id`, all verify outputs
**Steps:**
1. MOP `runAnalyticsTemplate` — generate evidence report (VPN Tunnel Evidence Report template)
2. `lookupDiff` (ConfigurationManager) — capture config diff for hub
3. `lookupDiff` (ConfigurationManager) — capture config diff for spoke
4. `updateNormalChangeRequestById` (ServiceNow) — set state to Implemented (success) or Failed (rollback)
5. `patchIpamIpAddressesId` (netbox-selab) — assign hub_tunnel_ip to hub device in NetBox
6. `patchIpamIpAddressesId` (netbox-selab) — assign spoke_tunnel_ip to spoke device in NetBox
7. `postIpamPrefixes` (netbox-selab) — create tunnel record with description = spoke_site_name
**Outputs:** `evidence_report`, `snow_update_status`, `netbox_update_status`

---

### Single-Spoke Orchestrator
**Inputs:** All per-spoke inputs (hub/spoke hostnames, site name, SNOW ticket, trustpoints, spoke AS, NetBox pool name, interfaces, timeout). Hub AS hardcoded 65000. Crypto map seq auto-incremented by Tunnel Design via NetBox.
**Flow:**
```
Pre-Flight Check
    │ FAIL → Close Out (Failed) → END
    ▼
Tunnel Design
    │ FAIL → Close Out (Failed) → END
    ▼
Config Backup
    │ FAIL → Close Out (Failed) → END
    ▼
Configure Hub
    │ FAIL → Rollback (hub only) → Close Out (Failed) → END
    ▼
Configure Spoke
    │ FAIL → Rollback (hub + spoke) → Close Out (Failed) → END
    ▼
Verify Tunnel (with timeout)
    │ FAIL → Rollback (hub + spoke) → Close Out (Failed) → END
    ▼
Close Out (Implemented) → END
```

---

### Batch Orchestrator
**Inputs:** Array of spoke definitions (each with per-spoke inputs above), `max_parallel` (default: 3)
**Flow:**
1. Chunk spoke array into groups of `max_parallel`
2. For each group: fan out to Single-Spoke Orchestrator in parallel (childJob)
3. Wait for group to complete before starting next group
4. If any spoke rollback fails (rollback_status = escalate): halt batch, create SNOW P1 incident
5. Individual spoke verification failures: log, continue batch
6. Generate batch summary report at completion
**Outputs:** `batch_summary`, per-spoke results array

---

## G. Implementation Plan

Build in this order — each component is testable before the next is added.

| Step | Component | Test Method |
|------|-----------|-------------|
| 1 | CT-ASA-Get-WAN-IP | Run against any IOS device in selab-iag-4.4; verify output parsed |
| 2 | CT-ASA-Verify-Trustpoint | Run against test device; verify output parsed |
| 3 | CT-ASA-Hub-IPsec-Config | Render template with test vars; inspect config output |
| 4 | CT-ASA-Spoke-IPsec-Config | Render template with test vars; inspect config output |
| 5 | CT-ASA-Verify-IKEv2-SA | Run against test device; verify SA state parsed |
| 6 | CT-ASA-Verify-BGP | Run against test device; verify BGP state parsed |
| 7 | CT-ASA-Ping-Tunnel | Run against test device; verify success/fail parsed |
| 8 | CT-ASA-Hub-Rollback | Render template with test vars; inspect output |
| 9 | CT-ASA-Spoke-Rollback | Render template with test vars; inspect output |
| 10 | Pre-Flight Check | Run with valid + invalid SNOW ticket IDs; test with unreachable device |
| 11 | Tunnel Design | Run against NetBox — verify /30 reserved; check output vars |
| 12 | Config Backup | Run against test devices — verify backup IDs returned |
| 13 | Configure Hub | Run against hub test device — verify config applied, no errors |
| 14 | Configure Spoke | Run against spoke test device — verify config applied, no errors |
| 15 | Verify Tunnel | Run against live tunnel — verify all checks pass; inject failure, verify fail path |
| 16 | Rollback | Inject failure after hub config — verify hub config removed cleanly |
| 17 | VPN Tunnel Evidence Report | Run template with test data; verify report renders correctly |
| 18 | Close Out | Run with success + failure inputs; verify SNOW + NetBox updated |
| 19 | Single-Spoke Orchestrator | End-to-end test against one spoke; test failure at each phase |
| 20 | Batch Orchestrator | Run with 3-spoke batch; verify rolling-3 concurrency; verify batch summary |

---

## H. Acceptance Criteria → Tests

| # | Acceptance Criterion | Test |
|---|---------------------|------|
| 1 | Provisioning only starts if valid Approved/In-Progress SNOW ticket exists | Run Pre-Flight Check with closed ticket → verify halt |
| 2 | Halts if WAN IP cannot be resolved | Mock show interface failure → verify Pre-Flight halts |
| 3 | Halts if trustpoint not found | Mock show crypto ca trustpoints empty → verify halt |
| 4 | /30 IPs allocated from NetBox — no manual input | Inspect Tunnel Design output — no IP input in workflow form |
| 5 | Crypto params identical on hub and spoke | Inspect CT-03 + CT-04 output — same policy values from single source |
| 6 | Config applied to both endpoints — never just one | Inject spoke config failure → verify hub rollback triggered |
| 7 | IKEv2 SA + IPsec SA confirmed active | Inspect Verify Tunnel output — SA state = ESTABLISHED |
| 8 | BGP adjacency confirmed on both sides | Inspect Verify Tunnel output — BGP state = ESTABLISHED |
| 9 | Ping succeeds from both sides | Inspect Verify Tunnel output — ping success both directions |
| 10 | Config backup exists before changes | Inspect Config Backup output — backup IDs timestamped pre-change |
| 11 | Rollback removes config from both sides | Inject verify failure → inspect device config — tunnel config absent |
| 12 | Rollback does not disrupt existing hub tunnels | Post-rollback: run CT-05 on hub → existing SAs still ESTABLISHED |
| 13 | Evidence report generated per spoke | Inspect Close Out output — report file present |
| 14 | SNOW updated to Implemented or Failed | Inspect Close Out output — SNOW ticket state updated |
| 15 | NetBox updated with IPs + inventory record | Inspect NetBox after run — /30 assigned, tunnel record created |
| 16 | Batch respects max-3 concurrency | Run 6-spoke batch — verify max 3 active simultaneously |

---

## I. Workflow Input Schema (Single-Spoke Orchestrator)

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

**Locked constants (not workflow inputs):**
- `hub_as`: `65000` — hardcoded in all command templates and child workflows
- `crypto_map_seq_num`: auto-incremented from NetBox tunnel prefix count during Tunnel Design
