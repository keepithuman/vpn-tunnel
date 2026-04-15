# Feasibility Assessment: IPsec VPN Tunnel Provisioning — Hub-and-Spoke (Cisco ASA)

**Date:** 2026-04-15
**Platform:** https://platform-6-aidev.se.itential.io
**Decision:** FEASIBLE WITH CONSTRAINTS

---

## 1. Environment Summary

The platform is a fully operational Itential instance running 18 adapters and 19 applications. All core orchestration capabilities required by the spec are present and running: WorkflowBuilder, WorkFlowEngine, ConfigurationManager, MOP, GatewayManager, and TemplateBuilder. Both external system integrations required by the spec — NetBox (`netbox-selab`) and ServiceNow (`ServiceNow`) — are running and connected online. IAG is available via two gateway adapters (`selab-compute-iag`, `selab-iag-4.4`) for CLI execution on network devices. The single constraint is that no Cisco ASA devices are currently registered in the platform inventory; they must be onboarded before the workflow can execute.

---

## 2. Capabilities Assessment

| Spec Requirement | Status | Resolution |
|-----------------|--------|------------|
| Execute CLI commands on Cisco ASA devices | ✓ | IAG via `selab-iag-4.4` + MOP `RunCommand` / `RunCommandTemplate`. ASA devices must be registered in IAG first (see Constraints). |
| Backup and diff ASA running configurations | ✓ | `ConfigurationManager` — `backUpDevice`, `getDeviceConfig`, `lookupDiff` tasks available. Requires ASA devices onboarded. |
| Apply multi-device configuration in sequence with conditions | ✓ | `WorkflowBuilder` + `WorkFlowEngine` + MOP `RunCommandTemplate` |
| Orchestrate multi-step workflows with rollback logic | ✓ | `WorkflowBuilder` + `WorkFlowEngine` — conditional branching and child job support confirmed |
| Resolve dynamic WAN IPs from device or inventory | ✓ | IAG `getOperationalData` + MOP `RunCommand` (`show interface`) on ASA |
| Generate reports from templates | ✓ | `TemplateBuilder` + MOP `runAnalyticsTemplate` + `viewTemplateResults` |

---

## 3. Integrations Assessment

| System | Adapter | State | Connection | Tasks Confirmed | Status |
|--------|---------|-------|------------|-----------------|--------|
| NetBox (IPAM) | `netbox-selab` | RUNNING | ONLINE | `getIpamPrefixesIdAvailablePrefixes`, `postIpamPrefixesIdAvailablePrefixes`, `getIpamIpAddresses`, `postIpamIpAddresses`, `getIpamPrefixesIdAvailableIps` | ✓ Ready |
| ServiceNow | `ServiceNow` | RUNNING | ONLINE | `getNormalChangeRequestById`, `updateNormalChangeRequestById`, `createNormalChangeRequest`, `autoApproveChangeRequest` | ✓ Ready |
| PKI / Certificate Authority | N/A | Pre-condition only | N/A | Trustpoint reference used in config — no platform API integration needed | ✓ Pre-condition |
| IAG (CLI execution) | `selab-iag-4.4` | RUNNING | ONLINE | `getConfig`, `setConfig`, `runCommand`-equivalent via MOP, `getOperationalData`, `isAlive` | ✓ Ready |

---

## 4. Constraints

| # | Constraint | Impact | Resolution |
|---|-----------|--------|------------|
| 1 | **No Cisco ASA devices in device inventory** | Workflow cannot execute against ASA hub or spokes until they are registered | Register hub ASA + all spoke ASAs in `selab-iag-4.4` and `ConfigurationManager` before first run. This is a pre-deployment step, not a platform capability gap. |
| 2 | **No existing IPsec/VPN workflows to reuse** | Full build required — no reuse for tunnel phases | All tunnel-specific components must be built from scratch. ServiceNow and health-check patterns can be adapted from existing workflows. |

---

## 5. Reuse Opportunities

| Existing Workflow | Relevance | Reuse Decision |
|------------------|-----------|----------------|
| `ServiceNow Create CR and Wait for Approval` | SNOW change ticket validation pattern | ↻ Adapt — modify for ticket state check (not CR creation) |
| `Update Change Request - ServiceNow` | SNOW close-out update pattern | ↻ Adapt — reuse update logic for Implemented/Failed close-out |
| `Network Health Check` | Pre-flight device reachability pattern | ↻ Reference — adapt for ASA-specific health check |
| `DNS - Pre-Flight Check` | Pre-flight pattern (DNS-specific) | Reference only — not directly reusable |
| `DNS - Rollback` | Rollback pattern | Reference only — not directly reusable |

---

## 6. Platform Component Map

| Spec Phase | Platform Component | App / Adapter |
|-----------|-------------------|---------------|
| SNOW ticket validation | `getNormalChangeRequestById` | ServiceNow adapter |
| Dynamic WAN IP resolution | `RunCommand` (`show interface`) | MOP + selab-iag-4.4 |
| Trustpoint validation | `RunCommand` (`show crypto ca trustpoints`) | MOP + selab-iag-4.4 |
| Device reachability check | `isAlive` | ConfigurationManager |
| NetBox /30 allocation | `getIpamPrefixesIdAvailablePrefixes` + `postIpamPrefixesIdAvailablePrefixes` | netbox-selab |
| Config backup (pre-change) | `backUpDevice` | ConfigurationManager |
| Hub ASA config push | `RunCommandTemplate` | MOP + selab-iag-4.4 |
| Spoke ASA config push | `RunCommandTemplate` | MOP + selab-iag-4.4 |
| IKEv2 / IPsec SA verification | `RunCommand` (`show crypto ikev2 sa`, `show crypto ipsec sa`) | MOP + selab-iag-4.4 |
| BGP adjacency verification | `RunCommand` (`show bgp neighbors`) | MOP + selab-iag-4.4 |
| Tunnel ping test | `RunCommand` (`ping <tunnel-ip>`) | MOP + selab-iag-4.4 |
| Rollback config restore | `backUpDevice` restore + `RunCommandTemplate` | ConfigurationManager + MOP |
| Config diff (post-change) | `lookupDiff` | ConfigurationManager |
| Evidence report generation | `runAnalyticsTemplate` | MOP / TemplateBuilder |
| SNOW ticket close-out | `updateNormalChangeRequestById` | ServiceNow adapter |
| NetBox IP record update | `patchIpamIpAddressesId` | netbox-selab |

---

## 7. Decision

**FEASIBLE WITH CONSTRAINTS**

All platform capabilities required by the spec are present and running. NetBox and ServiceNow integrations are confirmed live. IAG handles CLI execution on ASA devices via `selab-iag-4.4`. The only pre-deployment action required is onboarding Cisco ASA devices (hub + spokes) into `selab-iag-4.4` and `ConfigurationManager` — this is an environment setup step, not a platform limitation.

Full build is required; no existing workflows directly cover IPsec tunnel provisioning on ASA. SNOW and health-check workflow patterns exist and will be adapted.

---

## 8. Pre-Deployment Checklist (before first run)

- [ ] Register hub ASA in `selab-iag-4.4` with SSH credentials
- [ ] Register all spoke ASAs in `selab-iag-4.4` with SSH credentials
- [ ] Add hub + spoke ASAs to `ConfigurationManager` device inventory
- [ ] Confirm certificate trustpoints are installed on hub and spoke ASAs
- [ ] Confirm NetBox has a designated prefix pool for tunnel /30 allocations
- [ ] Confirm ServiceNow adapter credentials have permission to read + update Normal Change Requests
