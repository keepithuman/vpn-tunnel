# Use Case: IPsec VPN Tunnel Provisioning — Hub-and-Spoke (Cisco ASA)

## 1. Problem Statement

Provisioning site-to-site IPsec VPN tunnels across a hub-and-spoke topology is a coordination-heavy, error-prone process. An engineer must configure both the hub ASA and each spoke ASA with matching crypto parameters, certificate-based authentication, and BGP neighbor config — and a single mismatch means the tunnel never comes up. With ~25 spoke tunnels, manual provisioning is impractical and inconsistent.

**Goal:** Automate the end-to-end IPsec tunnel provisioning lifecycle — dynamic WAN IP resolution, NetBox IP allocation, certificate reference, both-endpoint ASA configuration, IKEv2 SA verification, BGP adjacency confirmation, and SNOW change tracking — so that spoke tunnels come up correctly on the first attempt, every time.

---

## 2. High-Level Flow

```
Request     →  Design     →  Configure     →  Verify        →  Close Out
  │               │              │               │                 │
Validate        Resolve       Backup hub    IKEv2 SA up?       Evidence
inputs,         dynamic       + spoke,      BGP neighbor       report,
resolve         WAN IPs,      apply IPsec   forms?             update
hub + spoke     allocate      + BGP config  Ping across        SNOW ticket,
hostnames,      tunnel IPs    to hub then   tunnel,            update
check           from NetBox,  spoke ASA     traffic passes     NetBox
reachability    build ASA                        │
                configs                     FAIL? → Rollback
```

---

## 3. Phases

### Request Validation
Validate the tunnel request: hub ASA hostname, spoke ASA hostname, spoke site name. Resolve management IPs from inventory. **Dynamically resolve the current WAN IP** for both hub and spoke (via device query or SNMP/API — not statically entered). Confirm both endpoints are reachable and healthy via management plane. If either endpoint is unreachable or unhealthy, **stop — do not proceed**.

### Tunnel Design
Allocate a /30 tunnel interface subnet from NetBox for this spoke. Retrieve the certificate trustpoint reference for both hub and spoke (certificate is pre-installed; workflow references it, does not generate it). Apply the **"high" crypto policy**:
- IKEv2, AES-256, SHA-256, DH Group 14, SA lifetime 86400s
- IPsec: AES-256-GCM, SHA-256, PFS Group 14, lifetime 3600s

Generate ASA-specific configuration blocks for both hub (crypto map entry, BGP neighbor statement) and spoke (full tunnel config).

### Configuration
Take a running-config backup of both hub ASA and spoke ASA before any changes. Apply configuration to the hub ASA first (add new crypto map entry, new BGP neighbor), then apply full tunnel configuration to the spoke ASA. If configuration fails on either device, **rollback changes already applied and stop**.

### Verification
Confirm the IKEv2 SA is established (`show crypto ikev2 sa`). Confirm the IPsec SA is active (`show crypto ipsec sa`). Ping across the tunnel interface from each side. Verify BGP neighbor adjacency forms on both hub and spoke (`show bgp neighbors`). If the tunnel is not fully up and BGP is not adjacent within a configurable timeout (default: 5 minutes), **trigger rollback**.

### Rollback (conditional)
Remove the spoke tunnel configuration from both ASAs in reverse order (spoke first, then hub). Restore running configs from backup. Verify rollback did not impact existing tunnels or BGP sessions on the hub. If rollback fails, **escalate immediately via SNOW P1 incident**.

### Close Out
Generate an evidence report: tunnel parameters, config diffs (hub and spoke), IKEv2/IPsec SA output, BGP adjacency state, timing. Update the SNOW change ticket to Closed/Implemented. Update NetBox with the allocated tunnel IP pair. Record the tunnel in NetBox inventory for lifecycle tracking.

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Both endpoints configured in single orchestrated workflow | Hub first, spoke second | A half-configured tunnel is useless; hub is shared resource so configure it atomically |
| WAN IPs resolved dynamically at runtime | Query device or inventory at execution time | Static IPs break for dynamic spoke sites; must reflect current state |
| Tunnel interface IPs allocated from NetBox | Required — not manual | Prevents /30 conflicts across all 25 spoke tunnels |
| Crypto policy is fixed at "high" tier | IKEv2, AES-256, SHA-256, DH14 | Enforces security standards; no per-tunnel negotiation |
| Authentication is certificate-based (IKEv2) | Trustpoint reference — cert pre-installed | Stronger than PSK; PKI management is out of scope (certs exist already) |
| BGP over tunnel | iBGP or eBGP neighbor per spoke | Routing adjacency is required for traffic — not optional |
| SNOW change ticket required | Must exist before provisioning starts | Audit trail; no change without a ticket |
| Hub concurrency limited | Max 3 spokes provisioned in parallel | Hub ASA is a shared resource; avoid overload during batch runs |
| Config backup is mandatory on both sides | No backup = no provisioning | Must have restore point for rollback |

---

## 5. Scope

**In scope:**
- IPsec IKEv2 tunnel provisioning on Cisco ASA (hub-and-spoke)
- Dynamic WAN IP resolution for hub and spoke
- Tunnel interface IP allocation from NetBox
- Certificate-based IKEv2 authentication (trustpoint reference, cert pre-installed)
- "High" crypto policy: AES-256, SHA-256, DH Group 14
- BGP neighbor configuration over the tunnel (hub and spoke)
- Config backup (pre-change) and diff (post-change) on both ASAs
- IKEv2/IPsec SA verification and BGP adjacency verification
- Rollback on verification failure
- SNOW change ticket update (open → implemented or failed)
- NetBox IP allocation and tunnel record creation
- Batch provisioning of ~25 spokes with rolling concurrency (max 3 parallel)

**Out of scope:**
- Certificate generation, enrollment, or PKI management (certs assumed pre-installed)
- GRE or GRE-over-IPsec (IPsec only)
- IKEv1 (IKEv2 only)
- Pre-shared key authentication
- OSPF or static routing over tunnel (BGP only)
- Firewall ACL changes on intermediate devices
- Full-mesh topology
- DMVPN/NHRP
- SD-WAN overlay provisioning
- QoS policy over tunnels

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dynamic WAN IP resolution fails | Cannot build tunnel config | Pre-flight check; halt provisioning for that spoke if IP cannot be resolved |
| Crypto parameter mismatch between hub and spoke | Tunnel never establishes | Generate both configs from a single parameter set — never configure endpoints independently |
| Certificate trustpoint not found on device | IKEv2 auth fails | Validate trustpoint exists on both devices before applying config; halt if missing |
| Hub ASA overloaded during batch run | Existing tunnels disrupted | Limit parallel spoke provisioning to 3; check hub CPU/memory before each batch |
| One endpoint configured, other fails | Dangling half-tunnel, BGP never forms | Rollback hub config if spoke config fails |
| NetBox /30 allocation conflict | Overlapping tunnel IPs | Allocate from NetBox with reservation; validate before applying |
| BGP adjacency never forms after tunnel up | Traffic does not pass | BGP check is part of verification; trigger rollback if adjacency not established in timeout |
| SNOW ticket not found or not in correct state | Change proceeds without authorization | Validate SNOW ticket state (Approved/In Progress) before provisioning begins |

---

## 7. Requirements

### What the platform must be able to do

| Capability | Required | If Not Available |
|-----------|----------|------------------|
| Execute CLI commands on Cisco ASA devices | Yes | Cannot proceed |
| Backup and diff ASA running configurations | Yes | Cannot proceed |
| Apply multi-device configuration in sequence with conditions | Yes | Cannot proceed |
| Orchestrate multi-step workflows with rollback logic | Yes | Cannot proceed |
| Resolve dynamic WAN IPs from device or inventory | Yes | Cannot proceed |
| Generate reports from templates | Yes | Cannot proceed |

### What external systems are involved

| System | Purpose | Required | If Not Available |
|--------|---------|----------|------------------|
| NetBox (IPAM) | Allocate /30 tunnel interface IPs; record tunnel inventory | Yes | Cannot proceed — no fallback to manual for 25 tunnels |
| ServiceNow (SNOW) | Validate change ticket; update to Implemented or Failed | Yes | Provisioning blocked — no unauthorized changes |
| Certificate Authority / PKI | Certificates must be pre-installed on devices; workflow references trustpoint name only | Pre-condition | If trustpoint missing, halt provisioning for that spoke |

### Engineer-Provided Inputs (per tunnel request)

| Input | Description |
|-------|-------------|
| Hub ASA hostname | Identifies the hub device |
| Spoke ASA hostname | Identifies the spoke device |
| Spoke site name | Used for naming, evidence report, NetBox record |
| SNOW change ticket number | Must be in Approved/In-Progress state |
| Trustpoint name (hub) | Certificate trustpoint reference on hub ASA |
| Trustpoint name (spoke) | Certificate trustpoint reference on spoke ASA |
| BGP AS numbers (hub + spoke) | Required for BGP neighbor configuration |
| BGP neighbor IPs | Tunnel interface addresses (allocated from NetBox, confirmed at design time) |

---

## 8. Batch Strategy

**~25 spoke tunnels, hub-and-spoke topology.**

| Strategy | Behavior |
|----------|----------|
| **Rolling — max 3 parallel** | Provision 3 spoke tunnels concurrently; wait for all 3 to complete before starting next group. Stop batch if any tunnel fails rollback (escalate). Continue batch on individual tunnel verification failure (rollback that spoke, proceed to next). |

- Hub ASA is a shared resource — limit concurrency to 3 to avoid overloading it.
- Each spoke tunnel is independent; individual failure does not block the batch unless hub is affected.
- SNOW ticket covers the full batch (single change record).
- Evidence report generated per spoke; batch summary report generated at completion.

---

## 9. Acceptance Criteria

1. Provisioning only starts if a valid, Approved/In-Progress SNOW change ticket exists
2. Provisioning halts for a spoke if WAN IP cannot be dynamically resolved
3. Provisioning halts for a spoke if the certificate trustpoint is not found on either device
4. Tunnel interface /30 IPs are allocated from NetBox — no manual IP input accepted
5. Crypto parameters are identical on hub and spoke (generated from single "high" policy source)
6. Configuration is applied to both endpoints — never just one
7. IKEv2 SA and IPsec SA are confirmed active on both hub and spoke
8. BGP neighbor adjacency is confirmed on both hub and spoke before close-out
9. Traffic passes across the tunnel (ping succeeds from both sides)
10. Config backup exists for both hub and spoke before changes are applied
11. Rollback removes tunnel config from both hub and spoke if verification fails
12. Rollback does not disrupt other active tunnels or BGP sessions on the hub
13. Evidence report is generated per spoke (success or failure)
14. SNOW change ticket is updated to Implemented (success) or Failed (rollback) at close-out
15. NetBox is updated with allocated tunnel IPs and tunnel inventory record
16. Batch run respects max-3 concurrency on the hub; batch stops only on hub-impacting failures
