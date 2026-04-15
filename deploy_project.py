#!/usr/bin/env python3
"""Deploy VPN Tunnel project: create workflows + MOP templates, add to project."""
import json
import subprocess
import sys
import time

TOKEN_FILE = "/tmp/vpn_token.sh"
BASE = "https://platform-6-aidev.se.itential.io"
PROJECT_ID = "7a363f30062b628589e280f0"

def get_token():
    result = subprocess.run(["bash", "-c", f"source {TOKEN_FILE} && echo $TOKEN"],
                            capture_output=True, text=True)
    return result.stdout.strip()

def api(method, path, body=None, token=None):
    cmd = ["curl", "-s", "-X", method,
           f"{BASE}{path}",
           "-H", f"Authorization: Bearer {token}",
           "-H", "Content-Type: application/json"]
    if body:
        cmd += ["-d", json.dumps(body)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        print(f"RAW: {result.stdout[:200]}")
        return {}

def create_workflow(token, wf_doc):
    resp = api("POST", "/automation-studio/automations", {"automation": wf_doc}, token)
    wf_id = resp.get("created", {}).get("_id")
    name = resp.get("created", {}).get("name", "?")
    if wf_id:
        print(f"  ✓ Created WF: {name} ({wf_id})")
    elif "already exists" in str(resp):
        # Find the existing workflow ID
        search = api("GET", f"/automation-studio/automations?name={wf_doc['name']}&limit=5", token=token)
        existing = next((i for i in search.get("items", []) if i.get("name") == wf_doc["name"]), None)
        if existing:
            wf_id = existing.get("_id")
            print(f"  ↩ Reusing existing WF: {wf_doc['name']} ({wf_id})")
        else:
            print(f"  ✗ Could not find existing WF: {wf_doc['name']}")
    else:
        print(f"  ✗ FAILED to create WF: {wf_doc.get('name')} | {str(resp)[:150]}")
    return wf_id

def create_mop(token, mop_doc):
    resp = api("POST", "/mop/createTemplate", {"mop": mop_doc}, token)
    if "error" not in str(resp).lower() and resp:
        print(f"  ✓ Created MOP: {mop_doc['name']}")
        return mop_doc["name"]
    else:
        print(f"  ✗ FAILED to create MOP: {mop_doc['name']} | {resp}")
        return None

def add_to_project(token, project_id, wf_ids, mop_names):
    components = []
    for wf_id in wf_ids:
        if wf_id:
            components.append({"type": "workflow", "reference": wf_id, "folder": "/"})
    for mop_name in mop_names:
        if mop_name:
            components.append({"type": "mopCommandTemplate", "reference": mop_name, "folder": "/"})

    resp = api("POST", f"/automation-studio/projects/{project_id}/components/add",
               {"components": components, "mode": "move"}, token)
    msg = resp.get("message", str(resp)[:100])
    print(f"  Add to project: {msg}")
    return resp

def update_workflow(token, wf_id, wf_doc):
    resp = api("PUT", f"/automation-studio/automations/{wf_id}", {"update": wf_doc}, token)
    if resp.get("updated"):
        print(f"  ✓ Updated WF {wf_id}")
        return True
    else:
        print(f"  ✗ Update failed for {wf_id}: {str(resp)[:100]}")
        return False

def get_project_workflow_ids(token, project_id):
    """Get the IDs of workflows in a project by name."""
    resp = api("GET", f"/automation-studio/projects/{project_id}", token=token)
    comps = resp.get("data", {}).get("components", [])
    result = {}
    for c in comps:
        if c.get("type") == "workflow":
            doc = c.get("document", {})
            result[doc.get("name", "")] = c.get("_id") or doc.get("_id")
    return result

def main():
    token = get_token()
    if not token:
        print("ERROR: No token found")
        sys.exit(1)

    # Load the project data from our build script
    with open("/Users/ankitrbhansali/use-cases/vpn-tunnel/project-import.json") as f:
        project = json.load(f)["project"]

    components = project["components"]
    workflows = [(c["document"], c["iid"]) for c in components if c["type"] == "workflow"]
    mops = [c["document"] for c in components if c["type"] == "mopCommandTemplate"]

    print(f"\n=== Step 1: Create {len(mops)} MOP Command Templates ===")
    mop_names = []
    for mop in mops:
        name = create_mop(token, mop)
        mop_names.append(name)

    print(f"\n=== Step 2: Create {len(workflows)} Workflows ===")
    wf_ids = []
    for wf_doc, iid in workflows:
        # Add encodingVersion for direct creation (not import)
        wf_doc_copy = dict(wf_doc)
        wf_doc_copy["encodingVersion"] = 1
        wf_id = create_workflow(token, wf_doc_copy)
        wf_ids.append(wf_id)

    print(f"\n=== Step 3: Add all components to project {PROJECT_ID} ===")
    add_to_project(token, PROJECT_ID, wf_ids, mop_names)

    time.sleep(2)

    print(f"\n=== Step 4: Get final project workflow names (with @projectId: prefix) ===")
    # After adding to project, workflows are named @projectId: Original Name
    resp = api("GET", f"/automation-studio/projects/{PROJECT_ID}", token=token)
    comps_in_proj = resp.get("data", {}).get("components", [])
    print(f"  Components in project: {len(comps_in_proj)}")

    wf_map = {}  # original_name -> prefixed_name
    wf_id_map = {}  # original_name -> automation_id
    for c in comps_in_proj:
        if c.get("type") == "workflow":
            # Get the actual workflow name via automation ID
            auto_id = c.get("reference") or c.get("_id")
            if auto_id:
                wf_resp = api("GET", f"/automation-studio/automations/{auto_id}", token=token)
                full_name = wf_resp.get("name", "")
                if not full_name:
                    full_name = c.get("reference", "unknown")
                orig_name = full_name.replace(f"@{PROJECT_ID}: ", "")
                wf_map[orig_name] = full_name
                wf_id_map[orig_name] = auto_id
                print(f"  - {full_name}: {auto_id}")

    print(f"\n=== Step 5: Update orchestrators to use @projectId: prefixed child names ===")
    # The Single-Spoke Orchestrator already has the right child names
    # (we hardcoded @PROJECT_ID: VPN - in the build script)
    # But we need to verify and potentially fix
    print("  Orchestrators use hardcoded @projectId: prefix — verifying...")

    # Check if orchestrators have right references
    ss_name = "VPN - Single-Spoke Orchestrator"
    ss_id = wf_id_map.get(ss_name)
    if ss_id:
        print(f"  Single-Spoke Orchestrator ID: {ss_id}")
        wf_resp = api("GET", f"/automation-studio/automations/{ss_id}", token=token)
        tasks = wf_resp.get("tasks", {})
        # Check a childJob task
        for tid, t in tasks.items():
            if isinstance(t, dict) and t.get("name") == "childJob":
                child_wf = t.get("variables", {}).get("incoming", {}).get("workflow", "")
                print(f"  childJob references: {child_wf}")
                break
    else:
        print("  Single-Spoke Orchestrator not found in project")

    print(f"\n=== Done! Project: {BASE}/automation-studio/#/project/{PROJECT_ID} ===")
    print("\nSummary:")
    print(f"  - {len([m for m in mop_names if m])} MOP templates created")
    print(f"  - {len([w for w in wf_ids if w])} workflows created")
    print(f"  - Project ID: {PROJECT_ID}")

if __name__ == "__main__":
    main()
