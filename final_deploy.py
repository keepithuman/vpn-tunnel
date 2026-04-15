#!/usr/bin/env python3
"""Clean deploy: create project, MOP templates, workflows, set membership."""
import json, subprocess, time, sys

BASE = "https://platform-6-aidev.se.itential.io"
PROJECT_ID = "7a363f30062b628589e280f0"
CLIENT_ID = "69ada6313f6ac74ee0dbbe78"
CLIENT_SECRET = "5006a975-fefd-42fb-bf06-7474dc206996"

def fresh_token():
    r = subprocess.run(["curl", "-s", "-X", "POST", f"{BASE}/oauth/token",
                        "-H", "Content-Type: application/x-www-form-urlencoded",
                        "-d", f"client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials"],
                       capture_output=True, text=True)
    return json.loads(r.stdout)["access_token"]

TOKEN = fresh_token()

def api(method, path, body=None, raw=False):
    global TOKEN
    cmd = ["curl", "-s", "-X", method, f"{BASE}{path}",
           "-H", f"Authorization: Bearer {TOKEN}",
           "-H", "Content-Type: application/json"]
    if body:
        cmd += ["-d", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not r.stdout.strip():
        TOKEN = fresh_token()
        r = subprocess.run(cmd[:-2] + ["-H", f"Authorization: Bearer {TOKEN}"] + cmd[-2:] if body else
                           ["curl", "-s", "-X", method, f"{BASE}{path}",
                            "-H", f"Authorization: Bearer {TOKEN}",
                            "-H", "Content-Type: application/json"],
                           capture_output=True, text=True)
    if raw:
        return r.stdout
    try:
        return json.loads(r.stdout)
    except:
        return {"_raw": r.stdout[:300]}

# ── Load build data ──────────────────────────────────────────────────────────
with open("/Users/ankitrbhansali/use-cases/vpn-tunnel/project-import.json") as f:
    project = json.load(f)["project"]

wf_docs  = [(c["document"], c["iid"]) for c in project["components"] if c["type"] == "workflow"]
mop_docs = [c["document"] for c in project["components"] if c["type"] == "mopCommandTemplate"]

# ── Step 1: Create project ────────────────────────────────────────────────────
print(f"\n=== Step 1: Create project {PROJECT_ID} ===")
proj_body = {
    "_id": PROJECT_ID,
    "name": "VPN Tunnel Provisioning",
    "description": "IPsec VPN hub-and-spoke on Cisco ASA with NetBox IPAM and ServiceNow",
    "thumbnail": "", "backgroundColor": "#FFFFFF",
    "components": [], "members": [],
    "createdBy": {"_id": "000000000000000000000000", "provenance": "CloudAAA", "username": "admin@itential"},
}
resp = api("POST", "/automation-studio/projects", proj_body)
resp_str = str(resp)
actual_pid = resp.get("data", {}).get("_id") if isinstance(resp, dict) else None
if actual_pid:
    PROJECT_ID = actual_pid
    print(f"  ✓ Project created: {PROJECT_ID}")
elif "Successfully created project" in resp_str or "already exists" in resp_str:
    # Find the project by name
    list_resp = api("GET", "/automation-studio/projects?limit=100")
    found = next((p for p in list_resp.get("data", []) if p.get("name") == "VPN Tunnel Provisioning"), None)
    if found:
        PROJECT_ID = found["_id"]
        print(f"  ✓ Project found: {PROJECT_ID}")
    else:
        print(f"  ✗ Could not find project: {resp_str[:150]}")
else:
    print(f"  ✗ Project failed: {resp_str[:150]}")

# ── Step 2: Create MOP templates ─────────────────────────────────────────────
print(f"\n=== Step 2: Create {len(mop_docs)} MOP command templates ===")
mop_names = []
for mop in mop_docs:
    # Strip metadata fields that cause validation failures
    body = {k: v for k, v in mop.items() if k not in ("created", "createdBy", "lastUpdated", "lastUpdatedBy", "tags")}
    resp = api("POST", "/mop/createTemplate", {"mop": body})
    name = mop["name"]
    resp_str = str(resp)
    if isinstance(resp, dict) and (resp.get("insertedIds") or resp.get("ops") or resp.get("insertedCount")):
        print(f"  ✓ Created: {name}")
        mop_names.append(name)
    elif "duplicate" in resp_str.lower() or "already" in resp_str.lower():
        print(f"  ↩ Already exists: {name}")
        mop_names.append(name)
    elif isinstance(resp, str) and "duplicate" in resp.lower():
        print(f"  ↩ Already exists: {name}")
        mop_names.append(name)
    else:
        print(f"  ✗ FAILED: {name} | {resp_str[:100]}")

# ── Step 3: Create workflows ─────────────────────────────────────────────────
print(f"\n=== Step 3: Create {len(wf_docs)} workflows ===")
wf_ids = []
for wf_doc, iid in wf_docs:
    wf_copy = dict(wf_doc)
    wf_copy["encodingVersion"] = 1
    resp = api("POST", "/automation-studio/automations", {"automation": wf_copy})
    wf_id = resp.get("created", {}).get("_id")
    name = wf_doc.get("name", "?")

    if wf_id:
        print(f"  ✓ Created: {name} ({wf_id})")
        wf_ids.append(wf_id)
    elif "already exists" in str(resp):
        # Search for it
        search = api("GET", f"/automation-studio/workflows?limit=10&name={name.replace(' ', '%20')}")
        existing = next((i for i in search.get("items", []) if i.get("name") == name), None)
        if existing:
            eid = existing["_id"]
            print(f"  ↩ Reused: {name} ({eid})")
            wf_ids.append(eid)
        else:
            print(f"  ✗ Could not find existing: {name}")
            wf_ids.append(None)
    else:
        print(f"  ✗ FAILED: {name} | {str(resp)[:100]}")
        wf_ids.append(None)

# ── Step 4: Add all to project (copy mode) ───────────────────────────────────
print(f"\n=== Step 4: Add all to project {PROJECT_ID} (copy) ===")
components = []
for wf_id in wf_ids:
    if wf_id:
        components.append({"type": "workflow", "reference": wf_id, "folder": "/"})
for name in mop_names:
    components.append({"type": "mopCommandTemplate", "reference": name, "folder": "/"})

resp = api("POST", f"/automation-studio/projects/{PROJECT_ID}/components/add",
           {"components": components, "mode": "copy"})
print(f"  {resp.get('message', str(resp)[:100])}")

time.sleep(2)

# ── Step 5: Verify project ────────────────────────────────────────────────────
print(f"\n=== Step 5: Verify project ===")
resp = api("GET", f"/automation-studio/projects/{PROJECT_ID}")
p = resp.get("data", {})
comps = p.get("components", [])
wf_count  = sum(1 for c in comps if c.get("type") == "workflow")
mop_count = sum(1 for c in comps if c.get("type") == "mopCommandTemplate")
print(f"  Project: {p.get('name')}")
print(f"  Workflows: {wf_count} | MOP templates: {mop_count}")

# ── Step 6: Set membership (Solutions Engineering) ────────────────────────────
print(f"\n=== Step 6: Set project membership ===")

# Find Solutions Engineering group
print("  Scanning projects for 'Solutions Engineering' group...")
projects_resp = api("GET", "/automation-studio/projects?limit=50")
se_ref = None
owner_ref = None

for p_item in projects_resp.get("data", []):
    pid = p_item.get("_id")
    if not pid or pid == PROJECT_ID:
        continue
    p_detail = api("GET", f"/automation-studio/projects/{pid}")
    members = p_detail.get("data", {}).get("members", [])
    for m in members:
        name_val = m.get("username") or m.get("name") or ""
        if "solutions" in name_val.lower() or "solution" in name_val.lower():
            se_ref = m.get("reference")
            se_type = m.get("type")
            print(f"  ✓ Found Solutions Engineering: {name_val} ({se_ref}, type: {se_type})")
            break
        if "ankit.bhansali@itential.com" in name_val.lower():
            owner_ref = m.get("reference")
    if se_ref and owner_ref:
        break

members = []
if owner_ref:
    members.append({"type": "account", "role": "owner", "reference": owner_ref})
    print(f"  ✓ Owner: ankit.bhansali@itential.com ({owner_ref})")
if se_ref:
    members.append({"type": se_type, "role": "editor", "reference": se_ref})
    print(f"  ✓ Editor: Solutions Engineering ({se_ref})")

if members:
    patch_resp = api("PATCH", f"/automation-studio/projects/{PROJECT_ID}", {"members": members})
    print(f"  PATCH: {patch_resp.get('message', str(patch_resp)[:100])}")
else:
    print("  ⚠ Could not find membership references — check manually in platform UI")

print(f"\n=== Build Complete ===")
print(f"  Project: {BASE}/automation-studio/#/project/{PROJECT_ID}")
print(f"  Workflows built: {len([w for w in wf_ids if w])}/10")
print(f"  MOP templates: {len(mop_names)}/9")
