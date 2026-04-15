#!/usr/bin/env python3
"""Generate the VPN Tunnel project import JSON for Itential platform."""
import json, uuid as uuidlib

PROJECT_ID = "7a363f30062b628589e280f0"
TODAY = "2026-04-15T00:00:00.000Z"

# Workflow doc UUIDs (inside the document)
WF = {
    "preflight":     "ff7cd061-414d-420b-a3f8-86391386dd5b",
    "tunnel_design": "1f52a72b-21e4-4f99-8643-79bde7e09ca0",
    "config_backup": "89271fe6-7c7a-437a-a3b9-18ed464ced31",
    "configure_hub": "281bf45a-1dfb-4a87-a1c1-97387ae968c0",
    "configure_spoke":"5c55023d-8aeb-4af4-a868-cda4c0b7c59a",
    "verify_tunnel": "9adb0c3b-5516-4a6e-aa3b-f2eb1bc5c202",
    "rollback":      "484ce147-8665-4134-aac8-cf6a3f65ab6f",
    "close_out":     "a0c7a6f0-2363-4c7d-99e4-52606cabd31d",
    "single_spoke":  "b5a2ceec-6d64-4d20-8aa7-c0d687c9bcf9",
    "batch":         "a8695a48-a5cc-441b-a6d5-f44597dd88b1",
}
# Component reference UUIDs (different from doc UUIDs — matches export format)
WF_REF = {k: str(uuidlib.uuid4()) for k in WF}

CREATED_BY_WF = {"provenance":"CloudAAA","username":"admin@itential","firstname":"Admin","inactive":False,"sso":False}
CREATED_BY_PRJ = {"_id":"000000000000000000000000","provenance":"CloudAAA","username":"admin@itential"}


def wf_base(name, uuid_key, description, tasks, transitions, input_schema, output_schema):
    # NOTE: no top-level "description" field — causes schema validation failure in import
    # NOTE: preAutomationTime and sla are required by import schema
    return {
        "name": name,
        "type": "automation",
        "canvasVersion": 3,
        "font_size": 12,
        "preAutomationTime": 0,
        "sla": 0,
        "created": TODAY, "created_by": CREATED_BY_WF,
        "last_updated": TODAY, "last_updated_by": CREATED_BY_WF,
        "createdVersion": "2024.1", "lastUpdatedVersion": "2024.1",
        "migrationVersion": 1, "tags": [], "groups": [],
        "uuid": WF[uuid_key], "scenarios": [],
        "tasks": tasks,
        "transitions": transitions,
        "inputSchema": input_schema,
        "outputSchema": output_schema,
    }


def app_task(task_id, name, app, task_type, incoming, outgoing, summary="", x=0, y=600, canvas=None, display=None):
    return {task_id: {
        "name": name, "canvasName": canvas or name, "summary": summary,
        "location": "Application", "locationType": None, "app": app,
        "type": task_type, "displayName": display or app,
        "variables": {"incoming": incoming, "outgoing": outgoing, "error": "", "decorators": []},
        "groups": [], "actor": "Pronghorn", "scheduled": False,
        "nodeLocation": {"x": x, "y": y}
    }}


def adapter_task(task_id, name, app, adapter_id, task_type, incoming, outgoing, summary="", x=0, y=600, canvas=None, display=None):
    inc = dict(incoming)
    inc["adapter_id"] = adapter_id
    return {task_id: {
        "name": name, "canvasName": canvas or name, "summary": summary,
        "location": "Adapter", "locationType": app, "app": app,
        "type": task_type, "displayName": display or adapter_id,
        "variables": {"incoming": inc, "outgoing": outgoing, "error": "", "decorators": []},
        "groups": [], "actor": "Pronghorn", "scheduled": False,
        "nodeLocation": {"x": x, "y": y}
    }}


def newvar(task_id, name, value, out_var, x=0, y=600, summary=""):
    return app_task(task_id, "newVariable", "WorkFlowEngine", "operation",
                    {"name": name, "value": value}, {"value": f"$var.job.{out_var}"},
                    summary=summary, x=x, y=y)


def query_task(task_id, q, obj, out_var, x=0, y=600, pass_null=False):
    return app_task(task_id, "query", "WorkFlowEngine", "operation",
                    {"pass_on_null": pass_null, "query": q, "obj": obj},
                    {"return_data": f"$var.job.{out_var}"},
                    summary=f"Extract {out_var}", x=x, y=y)


def eval_task(task_id, var1, task1, op, var2, task2="static", x=0, y=600, summary=""):
    return app_task(task_id, "evaluation", "WorkFlowEngine", "operation", {
        "all_true_flag": True,
        "evaluation_groups": [{"all_true_flag": True, "evaluations": [{
            "operand_1": {"task": task1, "variable": var1},
            "operator": op,
            "operand_2": {"task": task2, "variable": var2}
        }]}]
    }, {"return_value": None}, summary=summary, x=x, y=y)


def merge_task(task_id, items, out_var, x=0, y=600, summary="Build object"):
    return app_task(task_id, "merge", "WorkFlowEngine", "operation",
                    {"data_to_merge": items},
                    {"merged_object": f"$var.job.{out_var}"},
                    summary=summary, x=x, y=y)


def childjob_task(task_id, wf_name, variables, x=0, y=600, summary="", loop_type="", data_array=""):
    return {task_id: {
        "name": "childJob", "canvasName": "childJob", "summary": summary,
        "location": "Application", "locationType": None, "app": "WorkFlowEngine",
        "type": "operation", "displayName": "WorkFlowEngine",
        "variables": {"incoming": {
            "task": "", "workflow": wf_name, "variables": variables,
            "data_array": data_array, "transformation": "", "loopType": loop_type
        }, "outgoing": {"job_details": None}, "error": "", "decorators": []},
        "groups": [], "actor": "job", "scheduled": False,
        "nodeLocation": {"x": x, "y": y}
    }}


def start_end(sx, sy, ex, ey):
    return {
        "workflow_start": {"name": "workflow_start", "groups": [], "nodeLocation": {"x": sx, "y": sy}},
        "workflow_end":   {"name": "workflow_end",   "groups": [], "nodeLocation": {"x": ex, "y": ey}}
    }


def mop_run(task_id, template, devices_var, variables_var, x=0, y=600, summary="Run MOP Template"):
    """RunCommandTemplate task — devices is a job var (array), variables is a job var (object)."""
    return app_task(task_id, "RunCommandTemplate", "MOP", "automatic", {
        "template": template,
        "devices":   f"$var.job.{devices_var}",
        "variables": f"$var.job.{variables_var}",
    }, {"mop_template_results": f"$var.job.{task_id}_results"},
    summary=summary, x=x, y=y, display="MOP")


def make_array_task(task_id, hostname_var, out_var, x=0, y=600):
    """Convert a hostname string to a single-element array via makeData."""
    return {task_id: {
        "name": "makeData", "canvasName": "makeData", "summary": f"Wrap {hostname_var} in array",
        "location": "Application", "locationType": None, "app": "WorkFlowEngine",
        "type": "operation", "displayName": "WorkFlowEngine",
        "variables": {"incoming": {
            "input": '[\"<!hostname!>\"]',
            "outputType": "json",
            "variables": f"$var.job.{hostname_var}_wrap"
        }, "outgoing": {"output": f"$var.job.{out_var}"}, "error": "", "decorators": []},
        "groups": [], "actor": "Pronghorn", "scheduled": False,
        "nodeLocation": {"x": x, "y": y}
    }}


def make_array_merge(merge_id, array_id, hostname_var, out_var, x=0, y=600):
    """merge + makeData to create array from a string hostname."""
    m = merge_task(merge_id, [{"key": "hostname", "value": {"task": "job", "variable": hostname_var}}],
                   f"{hostname_var}_wrap", x=x, y=y, summary=f"Prep {hostname_var} for array")
    a = make_array_task(array_id, hostname_var, out_var, x=x+160, y=y)
    return {**m, **a}


# ─────────────────────────────────────────────────────────────────────────────
# 1. PRE-FLIGHT CHECK
# ─────────────────────────────────────────────────────────────────────────────
def build_preflight():
    tasks = {
        **start_end(50, 600, 2600, 600),
        # SNOW check
        **merge_task("a1b2", [
            {"key": "changeId", "value": {"task": "job", "variable": "snow_ticket_id"}}
        ], "snow_req", x=250, y=600, summary="Build SNOW request"),
        **adapter_task("b2c3", "getNormalChangeRequestById", "Servicenow", "ServiceNow", "automatic",
                       {"changeId": "$var.job.snow_ticket_id", "sysparmQuery": ""},
                       {"result": "$var.job.snow_result"},
                       summary="Get SNOW Change Request", x=500, y=600),
        **query_task("c3d4", "response.state", "$var.job.snow_result", "snow_state", x=750, y=600),
        **eval_task("d4e5", "snow_state", "job", "!=", "Closed", summary="SNOW state != Closed", x=1000, y=600),
        # Hub alive check
        **app_task("e5f6", "isAlive", "ConfigurationManager", "automatic",
                   {"name": "$var.job.hub_hostname"}, {"status": "$var.job.hub_alive_status"},
                   summary="Check hub reachability", x=1250, y=600),
        **eval_task("f6a7", "hub_alive_status", "job", "!=", "false", summary="Hub is alive", x=1500, y=600),
        # Spoke alive check
        **app_task("a7b8", "isAlive", "ConfigurationManager", "automatic",
                   {"name": "$var.job.spoke_hostname"}, {"status": "$var.job.spoke_alive_status"},
                   summary="Check spoke reachability", x=1750, y=600),
        **eval_task("b8c9", "spoke_alive_status", "job", "!=", "false", summary="Spoke is alive", x=2000, y=600),
        **newvar("c9d0", "preflight_status", "success", "preflight_status", x=2250, y=600, summary="Set success"),
        # Error / halt handlers
        **newvar("e1f2", "preflight_status", "failed_snow_check", "preflight_status", x=1000, y=870, summary="SNOW check failed"),
        **newvar("f2a3", "preflight_status", "failed_hub_unreachable", "preflight_status", x=1250, y=870, summary="Hub unreachable"),
        **newvar("a3b4", "preflight_status", "failed_spoke_unreachable", "preflight_status", x=1750, y=870, summary="Spoke unreachable"),
        **newvar("b4c5", "preflight_status", "failed_snow_error", "preflight_status", x=500, y=870, summary="SNOW adapter error"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}, "b4c5": {"type": "standard", "state": "error"}},
        "c3d4": {"d4e5": {"type": "standard", "state": "success"}, "e1f2": {"type": "standard", "state": "failure"}},
        "d4e5": {"e5f6": {"type": "standard", "state": "success"}, "e1f2": {"type": "standard", "state": "failure"}},
        "e5f6": {"f6a7": {"type": "standard", "state": "success"}},
        "f6a7": {"a7b8": {"type": "standard", "state": "success"}, "f2a3": {"type": "standard", "state": "failure"}},
        "a7b8": {"b8c9": {"type": "standard", "state": "success"}},
        "b8c9": {"c9d0": {"type": "standard", "state": "success"}, "a3b4": {"type": "standard", "state": "failure"}},
        "c9d0": {"workflow_end": {"type": "standard", "state": "success"}},
        "e1f2": {"workflow_end": {"type": "standard", "state": "success"}},
        "f2a3": {"workflow_end": {"type": "standard", "state": "success"}},
        "a3b4": {"workflow_end": {"type": "standard", "state": "success"}},
        "b4c5": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Pre-Flight Check", "preflight",
        "Validates SNOW ticket state and device reachability for hub and spoke ASA",
        tasks, transitions,
        {"type": "object", "properties": {
            "snow_ticket_id": {"title": "snow_ticket_id", "type": "string"},
            "hub_hostname":   {"title": "hub_hostname",   "type": "string"},
            "spoke_hostname": {"title": "spoke_hostname", "type": "string"},
            "hub_wan_interface":   {"title": "hub_wan_interface",   "type": "string"},
            "spoke_wan_interface": {"title": "spoke_wan_interface", "type": "string"},
            "hub_trustpoint":   {"title": "hub_trustpoint",   "type": "string"},
            "spoke_trustpoint": {"title": "spoke_trustpoint", "type": "string"},
        }, "required": ["snow_ticket_id", "hub_hostname", "spoke_hostname"]},
        {"type": "object", "properties": {
            "preflight_status": {"type": "string"},
            "hub_alive_status": {"type": "string"},
            "spoke_alive_status": {"type": "string"},
            "snow_state": {"type": "string"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. TUNNEL DESIGN
# ─────────────────────────────────────────────────────────────────────────────
def build_tunnel_design():
    tasks = {
        **start_end(50, 600, 2800, 600),
        # Look up prefix pool by name/role tag
        **adapter_task("a1b2", "getIpamPrefixes", "Netbox", "netbox-selab", "automatic",
                       {"q": "$var.job.netbox_prefix_pool_name", "isPool": True, "limit": 1, "offset": 0},
                       {"result": "$var.job.prefix_pool_result"},
                       summary="Find NetBox prefix pool", x=250, y=600),
        **query_task("b2c3", "response.results[0].id", "$var.job.prefix_pool_result", "prefix_pool_id", x=500, y=600),
        # Get available /30
        **adapter_task("c3d4", "getIpamPrefixesIdAvailablePrefixes", "Netbox", "netbox-selab", "automatic",
                       {"id": "$var.job.prefix_pool_id"},
                       {"result": "$var.job.available_prefixes_result"},
                       summary="Get available /30 prefixes", x=750, y=600),
        **query_task("d4e5", "response[0].prefix", "$var.job.available_prefixes_result", "allocated_prefix", x=1000, y=600),
        # Reserve /30
        **merge_task("e5f6", [
            {"key": "prefix_length", "value": {"task": "static", "variable": 30}},
            {"key": "description",   "value": {"task": "job",    "variable": "spoke_site_name"}},
        ], "reserve_body", x=1250, y=600, summary="Build reservation body"),
        **adapter_task("f6a7", "postIpamPrefixesIdAvailablePrefixes", "Netbox", "netbox-selab", "automatic",
                       {"id": "$var.job.prefix_pool_id", "data": "$var.job.reserve_body"},
                       {"result": "$var.job.reserved_prefix_result"},
                       summary="Reserve /30 prefix", x=1500, y=600),
        # Count existing tunnels for seq_num
        **adapter_task("a7b8", "getIpamPrefixes", "Netbox", "netbox-selab", "automatic",
                       {"q": "$var.job.netbox_prefix_pool_name", "limit": 500},
                       {"result": "$var.job.tunnel_prefixes_result"},
                       summary="Count existing tunnel prefixes for seq_num", x=1750, y=600),
        **query_task("b8c9", "response.count", "$var.job.tunnel_prefixes_result", "tunnel_count", x=2000, y=600),
        # Build hub and spoke config vars
        **merge_task("c9d0", [
            {"key": "seq_num",         "value": {"task": "job", "variable": "tunnel_count"}},
            {"key": "spoke_wan_ip",    "value": {"task": "job", "variable": "spoke_wan_ip"}},
            {"key": "hub_trustpoint",  "value": {"task": "job", "variable": "hub_trustpoint"}},
            {"key": "spoke_as",        "value": {"task": "job", "variable": "spoke_as"}},
            {"key": "crypto_map_name", "value": {"task": "job", "variable": "crypto_map_name"}},
            {"key": "allocated_prefix","value": {"task": "job", "variable": "allocated_prefix"}},
        ], "hub_config_vars", x=2250, y=600, summary="Build hub config vars"),
        **newvar("d0e1", "taskStatus", "success", "taskStatus", x=2550, y=600, summary="Set success"),
        # Error handlers
        **newvar("err1", "taskStatus", "error_netbox", "taskStatus", x=250, y=870, summary="NetBox pool lookup failed"),
        **newvar("err2", "taskStatus", "error_prefix_reserve", "taskStatus", x=1500, y=870, summary="Prefix reservation failed"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "failure"}},
        "c3d4": {"d4e5": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "d4e5": {"e5f6": {"type": "standard", "state": "success"}},
        "e5f6": {"f6a7": {"type": "standard", "state": "success"}},
        "f6a7": {"a7b8": {"type": "standard", "state": "success"}, "err2": {"type": "standard", "state": "error"}},
        "a7b8": {"b8c9": {"type": "standard", "state": "success"}, "err2": {"type": "standard", "state": "error"}},
        "b8c9": {"c9d0": {"type": "standard", "state": "success"}},
        "c9d0": {"d0e1": {"type": "standard", "state": "success"}},
        "d0e1": {"workflow_end": {"type": "standard", "state": "success"}},
        "err1": {"workflow_end": {"type": "standard", "state": "success"}},
        "err2": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Tunnel Design", "tunnel_design",
        "Allocates /30 from NetBox prefix pool and builds ASA config variable objects",
        tasks, transitions,
        {"type": "object", "properties": {
            "netbox_prefix_pool_name": {"title": "netbox_prefix_pool_name", "type": "string"},
            "spoke_site_name":  {"title": "spoke_site_name",  "type": "string"},
            "spoke_as":         {"title": "spoke_as",         "type": "number"},
            "hub_wan_ip":       {"title": "hub_wan_ip",       "type": "string"},
            "spoke_wan_ip":     {"title": "spoke_wan_ip",     "type": "string"},
            "hub_trustpoint":   {"title": "hub_trustpoint",   "type": "string"},
            "spoke_trustpoint": {"title": "spoke_trustpoint", "type": "string"},
            "crypto_map_name":  {"title": "crypto_map_name",  "type": "string"},
        }, "required": ["netbox_prefix_pool_name", "spoke_site_name", "spoke_as", "crypto_map_name"]},
        {"type": "object", "properties": {
            "taskStatus":       {"type": "string"},
            "allocated_prefix": {"type": "string"},
            "hub_config_vars":  {"type": "object"},
            "tunnel_count":     {"type": "number"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. CONFIG BACKUP
# ─────────────────────────────────────────────────────────────────────────────
def build_config_backup():
    tasks = {
        **start_end(50, 600, 1000, 600),
        **app_task("a1b2", "backUpDevice", "ConfigurationManager", "automatic",
                   {"name": "$var.job.hub_hostname", "options": {}},
                   {"status": "$var.job.hub_backup_status"},
                   summary="Backup hub ASA config", x=250, y=600),
        **app_task("b2c3", "backUpDevice", "ConfigurationManager", "automatic",
                   {"name": "$var.job.spoke_hostname", "options": {}},
                   {"status": "$var.job.spoke_backup_status"},
                   summary="Backup spoke ASA config", x=500, y=600),
        **newvar("c3d4", "taskStatus", "success", "taskStatus", x=750, y=600, summary="Backup complete"),
        **newvar("err1", "taskStatus", "error_backup", "taskStatus", x=250, y=870, summary="Backup failed"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "c3d4": {"workflow_end": {"type": "standard", "state": "success"}},
        "err1": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Config Backup", "config_backup",
        "Takes running-config backup of hub and spoke ASA before changes",
        tasks, transitions,
        {"type": "object", "properties": {
            "hub_hostname":   {"title": "hub_hostname",   "type": "string"},
            "spoke_hostname": {"title": "spoke_hostname", "type": "string"},
        }, "required": ["hub_hostname", "spoke_hostname"]},
        {"type": "object", "properties": {
            "taskStatus":          {"type": "string"},
            "hub_backup_status":   {"type": "object"},
            "spoke_backup_status": {"type": "object"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONFIGURE HUB
# ─────────────────────────────────────────────────────────────────────────────
def build_configure_hub():
    tasks = {
        **start_end(50, 600, 850, 600),
        # hub_devices must be an array — parent passes it as ["hub_hostname"]
        **app_task("a1b2", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Hub-IPsec-Config",
            "devices":   "$var.job.hub_devices",
            "variables": "$var.job.hub_config_vars",
        }, {"mop_template_results": "$var.job.hub_mop_results"},
        summary="Push hub IPsec config", x=250, y=600, display="MOP"),
        **query_task("b2c3", "all_pass_flag", "$var.job.hub_mop_results", "hub_config_pass", x=500, y=600),
        **eval_task("c3d4", "hub_config_pass", "job", "==", "true", summary="Hub config applied ok", x=650, y=600),
        **newvar("d4e5", "taskStatus", "success", "taskStatus", x=800, y=530, summary="Config success"),
        **newvar("err1", "taskStatus", "error_hub_config", "taskStatus", x=650, y=870, summary="Hub config failed"),
        **newvar("err2", "taskStatus", "error_hub_mop", "taskStatus", x=250, y=870, summary="MOP run failed"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}, "err2": {"type": "standard", "state": "error"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}},
        "c3d4": {"d4e5": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "failure"}},
        "d4e5": {"workflow_end": {"type": "standard", "state": "success"}},
        "err1": {"workflow_end": {"type": "standard", "state": "success"}},
        "err2": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Configure Hub", "configure_hub",
        "Applies IPsec crypto map entry and BGP neighbor config to hub ASA",
        tasks, transitions,
        {"type": "object", "properties": {
            "hub_hostname":    {"title": "hub_hostname",    "type": "string"},
            "hub_devices":     {"title": "hub_devices",     "type": "array"},
            "hub_config_vars": {"title": "hub_config_vars", "type": "object"},
        }, "required": ["hub_devices", "hub_config_vars"]},
        {"type": "object", "properties": {
            "taskStatus":      {"type": "string"},
            "hub_mop_results": {"type": "object"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. CONFIGURE SPOKE
# ─────────────────────────────────────────────────────────────────────────────
def build_configure_spoke():
    tasks = {
        **start_end(50, 600, 850, 600),
        **app_task("a1b2", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Spoke-IPsec-Config",
            "devices":   "$var.job.spoke_devices",
            "variables": "$var.job.spoke_config_vars",
        }, {"mop_template_results": "$var.job.spoke_mop_results"},
        summary="Push spoke IPsec config", x=250, y=600, display="MOP"),
        **query_task("b2c3", "all_pass_flag", "$var.job.spoke_mop_results", "spoke_config_pass", x=500, y=600),
        **eval_task("c3d4", "spoke_config_pass", "job", "==", "true", summary="Spoke config applied ok", x=650, y=600),
        **newvar("d4e5", "taskStatus", "success", "taskStatus", x=800, y=530, summary="Config success"),
        **newvar("err1", "taskStatus", "error_spoke_config", "taskStatus", x=650, y=870, summary="Spoke config failed"),
        **newvar("err2", "taskStatus", "error_spoke_mop", "taskStatus", x=250, y=870, summary="MOP run failed"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}, "err2": {"type": "standard", "state": "error"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}},
        "c3d4": {"d4e5": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "failure"}},
        "d4e5": {"workflow_end": {"type": "standard", "state": "success"}},
        "err1": {"workflow_end": {"type": "standard", "state": "success"}},
        "err2": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Configure Spoke", "configure_spoke",
        "Applies full IPsec tunnel and BGP neighbor config to spoke ASA",
        tasks, transitions,
        {"type": "object", "properties": {
            "spoke_hostname":    {"title": "spoke_hostname",    "type": "string"},
            "spoke_devices":     {"title": "spoke_devices",     "type": "array"},
            "spoke_config_vars": {"title": "spoke_config_vars", "type": "object"},
        }, "required": ["spoke_devices", "spoke_config_vars"]},
        {"type": "object", "properties": {
            "taskStatus":        {"type": "string"},
            "spoke_mop_results": {"type": "object"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. VERIFY TUNNEL
# ─────────────────────────────────────────────────────────────────────────────
def build_verify_tunnel():
    tasks = {
        **start_end(50, 600, 2500, 600),
        # IKEv2 SA check on hub
        **app_task("a1b2", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Verify-IKEv2-SA",
            "devices":   "$var.job.hub_devices",
            "variables": {},
        }, {"mop_template_results": "$var.job.hub_ikev2_results"},
        summary="Check IKEv2 SA on hub", x=250, y=600, display="MOP"),
        **query_task("b2c3", "all_pass_flag", "$var.job.hub_ikev2_results", "hub_ikev2_pass", x=500, y=600),
        # IKEv2 SA check on spoke
        **app_task("c3d4", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Verify-IKEv2-SA",
            "devices":   "$var.job.spoke_devices",
            "variables": {},
        }, {"mop_template_results": "$var.job.spoke_ikev2_results"},
        summary="Check IKEv2 SA on spoke", x=750, y=600, display="MOP"),
        **query_task("d4e5", "all_pass_flag", "$var.job.spoke_ikev2_results", "spoke_ikev2_pass", x=1000, y=600),
        # BGP check on hub
        **merge_task("e5f6", [
            {"key": "neighbor_ip", "value": {"task": "job", "variable": "spoke_tunnel_ip"}}
        ], "hub_bgp_vars", x=1250, y=600, summary="Build hub BGP check vars"),
        **app_task("f6a7", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Verify-BGP",
            "devices":   "$var.job.hub_devices",
            "variables": "$var.job.hub_bgp_vars",
        }, {"mop_template_results": "$var.job.hub_bgp_results"},
        summary="Check BGP neighbor on hub", x=1450, y=600, display="MOP"),
        # BGP check on spoke
        **merge_task("a7b8", [
            {"key": "neighbor_ip", "value": {"task": "job", "variable": "hub_tunnel_ip"}}
        ], "spoke_bgp_vars", x=1700, y=600, summary="Build spoke BGP check vars"),
        **app_task("b8c9", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Verify-BGP",
            "devices":   "$var.job.spoke_devices",
            "variables": "$var.job.spoke_bgp_vars",
        }, {"mop_template_results": "$var.job.spoke_bgp_results"},
        summary="Check BGP neighbor on spoke", x=1900, y=600, display="MOP"),
        # Ping hub → spoke
        **merge_task("c9d0", [
            {"key": "target_ip", "value": {"task": "job", "variable": "spoke_tunnel_ip"}},
            {"key": "source_ip", "value": {"task": "job", "variable": "hub_tunnel_ip"}},
        ], "hub_ping_vars", x=2100, y=600, summary="Build hub ping vars"),
        **app_task("d0e1", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Ping-Tunnel",
            "devices":   "$var.job.hub_devices",
            "variables": "$var.job.hub_ping_vars",
        }, {"mop_template_results": "$var.job.hub_ping_results"},
        summary="Ping spoke from hub", x=2250, y=600, display="MOP"),
        **newvar("e1f2", "verify_status", "success", "verify_status", x=2400, y=530, summary="All checks passed"),
        # Failure handler
        **newvar("err1", "verify_status", "failed", "verify_status", x=600, y=870, summary="Verification failed"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "failure"}},
        "c3d4": {"d4e5": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "d4e5": {"e5f6": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "failure"}},
        "e5f6": {"f6a7": {"type": "standard", "state": "success"}},
        "f6a7": {"a7b8": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "a7b8": {"b8c9": {"type": "standard", "state": "success"}},
        "b8c9": {"c9d0": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "c9d0": {"d0e1": {"type": "standard", "state": "success"}},
        "d0e1": {"e1f2": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "e1f2": {"workflow_end": {"type": "standard", "state": "success"}},
        "err1": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Verify Tunnel", "verify_tunnel",
        "Verifies IKEv2 SA, BGP adjacency, and ping across the IPsec tunnel",
        tasks, transitions,
        {"type": "object", "properties": {
            "hub_hostname":    {"title": "hub_hostname",    "type": "string"},
            "spoke_hostname":  {"title": "spoke_hostname",  "type": "string"},
            "hub_devices":     {"title": "hub_devices",     "type": "array"},
            "spoke_devices":   {"title": "spoke_devices",   "type": "array"},
            "hub_tunnel_ip":   {"title": "hub_tunnel_ip",   "type": "string"},
            "spoke_tunnel_ip": {"title": "spoke_tunnel_ip", "type": "string"},
            "spoke_as":        {"title": "spoke_as",        "type": "number"},
            "verify_timeout_minutes": {"title": "verify_timeout_minutes", "type": "number"},
        }, "required": ["hub_devices", "spoke_devices", "hub_tunnel_ip", "spoke_tunnel_ip"]},
        {"type": "object", "properties": {
            "verify_status":       {"type": "string"},
            "hub_ikev2_results":   {"type": "object"},
            "spoke_ikev2_results": {"type": "object"},
            "hub_bgp_results":     {"type": "object"},
            "spoke_bgp_results":   {"type": "object"},
            "hub_ping_results":    {"type": "object"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. ROLLBACK
# ─────────────────────────────────────────────────────────────────────────────
def build_rollback():
    tasks = {
        **start_end(50, 600, 1600, 600),
        # Remove spoke config (if spoke was configured)
        **eval_task("a1b2", "configured_spoke", "job", "==", "true", summary="Was spoke configured?", x=250, y=600),
        **app_task("b2c3", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Spoke-Rollback",
            "devices":   "$var.job.spoke_devices",
            "variables": "$var.job.spoke_config_vars",
        }, {"mop_template_results": "$var.job.spoke_rollback_results"},
        summary="Remove spoke tunnel config", x=500, y=500, display="MOP"),
        # Remove hub config (if hub was configured)
        **eval_task("c3d4", "configured_hub", "job", "==", "true", summary="Was hub configured?", x=750, y=600),
        **app_task("d4e5", "RunCommandTemplate", "MOP", "automatic", {
            "template": f"@{PROJECT_ID}: CT-ASA-Hub-Rollback",
            "devices":   "$var.job.hub_devices",
            "variables": "$var.job.hub_config_vars",
        }, {"mop_template_results": "$var.job.hub_rollback_results"},
        summary="Remove hub tunnel entry", x=1000, y=500, display="MOP"),
        # Restore backups
        **app_task("e5f6", "backUpDevice", "ConfigurationManager", "automatic",
                   {"name": "$var.job.hub_hostname", "options": {}},
                   {"status": "$var.job.hub_restore_status"},
                   summary="Restore hub from backup", x=1250, y=600),
        **app_task("f6a7", "backUpDevice", "ConfigurationManager", "automatic",
                   {"name": "$var.job.spoke_hostname", "options": {}},
                   {"status": "$var.job.spoke_restore_status"},
                   summary="Restore spoke from backup", x=1450, y=600),
        **newvar("a7b8", "rollback_status", "success", "rollback_status", x=1600, y=530, summary="Rollback complete"),
        **newvar("err1", "rollback_status", "error", "rollback_status", x=500, y=870, summary="Rollback error"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}, "c3d4": {"type": "standard", "state": "failure"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "c3d4": {"d4e5": {"type": "standard", "state": "success"}, "e5f6": {"type": "standard", "state": "failure"}},
        "d4e5": {"e5f6": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "e5f6": {"f6a7": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "f6a7": {"a7b8": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "a7b8": {"workflow_end": {"type": "standard", "state": "success"}},
        "err1": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Rollback", "rollback",
        "Removes tunnel config from spoke and/or hub ASA and restores from pre-change backup",
        tasks, transitions,
        {"type": "object", "properties": {
            "hub_hostname":    {"title": "hub_hostname",    "type": "string"},
            "spoke_hostname":  {"title": "spoke_hostname",  "type": "string"},
            "hub_devices":     {"title": "hub_devices",     "type": "array"},
            "spoke_devices":   {"title": "spoke_devices",   "type": "array"},
            "hub_config_vars": {"title": "hub_config_vars", "type": "object"},
            "spoke_config_vars": {"title": "spoke_config_vars", "type": "object"},
            "configured_hub":   {"title": "configured_hub",   "type": "boolean"},
            "configured_spoke": {"title": "configured_spoke", "type": "boolean"},
        }, "required": ["hub_devices", "spoke_devices"]},
        {"type": "object", "properties": {
            "rollback_status":       {"type": "string"},
            "hub_rollback_results":  {"type": "object"},
            "spoke_rollback_results":{"type": "object"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. CLOSE OUT
# ─────────────────────────────────────────────────────────────────────────────
def build_close_out():
    tasks = {
        **start_end(50, 600, 2200, 600),
        # Determine SNOW state from verify_status
        **eval_task("a1b2", "verify_status", "job", "==", "success", summary="Did tunnel verify succeed?", x=250, y=600),
        # Success path: update SNOW to Implemented
        **merge_task("b2c3", [
            {"key": "state",       "value": {"task": "static", "variable": "Implement"}},
            {"key": "work_notes",  "value": {"task": "job",    "variable": "spoke_site_name"}},
        ], "snow_success_body", x=500, y=500, summary="Build SNOW Implemented body"),
        **adapter_task("c3d4", "updateNormalChangeRequestById", "Servicenow", "ServiceNow", "automatic",
                       {"changeId": "$var.job.snow_ticket_id", "change": "$var.job.snow_success_body"},
                       {"result": "$var.job.snow_update_result"},
                       summary="Update SNOW to Implemented", x=750, y=500),
        # Failure path: update SNOW to Failed
        **merge_task("d4e5", [
            {"key": "state",       "value": {"task": "static", "variable": "Failed"}},
            {"key": "work_notes",  "value": {"task": "job",    "variable": "spoke_site_name"}},
        ], "snow_fail_body", x=500, y=700, summary="Build SNOW Failed body"),
        **adapter_task("e5f6", "updateNormalChangeRequestById", "Servicenow", "ServiceNow", "automatic",
                       {"changeId": "$var.job.snow_ticket_id", "change": "$var.job.snow_fail_body"},
                       {"result": "$var.job.snow_fail_result"},
                       summary="Update SNOW to Failed", x=750, y=700),
        # NetBox: create hub tunnel IP record
        **merge_task("f6a7", [
            {"key": "address",     "value": {"task": "job", "variable": "hub_tunnel_ip"}},
            {"key": "description", "value": {"task": "job", "variable": "spoke_site_name"}},
        ], "hub_ip_body", x=1100, y=600, summary="Build hub IP record"),
        **adapter_task("a7b8", "postIpamIpAddresses", "Netbox", "netbox-selab", "automatic",
                       {"data": "$var.job.hub_ip_body"},
                       {"result": "$var.job.hub_ip_result"},
                       summary="Create hub tunnel IP in NetBox", x=1350, y=600),
        # NetBox: create spoke tunnel IP record
        **merge_task("b8c9", [
            {"key": "address",     "value": {"task": "job", "variable": "spoke_tunnel_ip"}},
            {"key": "description", "value": {"task": "job", "variable": "spoke_site_name"}},
        ], "spoke_ip_body", x=1600, y=600, summary="Build spoke IP record"),
        **adapter_task("c9d0", "postIpamIpAddresses", "Netbox", "netbox-selab", "automatic",
                       {"data": "$var.job.spoke_ip_body"},
                       {"result": "$var.job.spoke_ip_result"},
                       summary="Create spoke tunnel IP in NetBox", x=1850, y=600),
        **newvar("d0e1", "close_out_status", "complete", "close_out_status", x=2100, y=600, summary="Close out complete"),
        # Error handlers
        **newvar("err1", "close_out_status", "error_snow_update", "close_out_status", x=750, y=870, summary="SNOW update error"),
        **newvar("err2", "close_out_status", "error_netbox_update", "close_out_status", x=1350, y=870, summary="NetBox update error"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}, "d4e5": {"type": "standard", "state": "failure"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}},
        "c3d4": {"f6a7": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "d4e5": {"e5f6": {"type": "standard", "state": "success"}},
        "e5f6": {"f6a7": {"type": "standard", "state": "success"}, "err1": {"type": "standard", "state": "error"}},
        "f6a7": {"a7b8": {"type": "standard", "state": "success"}},
        "a7b8": {"b8c9": {"type": "standard", "state": "success"}, "err2": {"type": "standard", "state": "error"}},
        "b8c9": {"c9d0": {"type": "standard", "state": "success"}},
        "c9d0": {"d0e1": {"type": "standard", "state": "success"}, "err2": {"type": "standard", "state": "error"}},
        "d0e1": {"workflow_end": {"type": "standard", "state": "success"}},
        "err1": {"workflow_end": {"type": "standard", "state": "success"}},
        "err2": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Close Out", "close_out",
        "Updates SNOW change request, creates NetBox IP records for tunnel interfaces",
        tasks, transitions,
        {"type": "object", "properties": {
            "snow_ticket_id":  {"title": "snow_ticket_id",  "type": "string"},
            "spoke_site_name": {"title": "spoke_site_name", "type": "string"},
            "verify_status":   {"title": "verify_status",   "type": "string"},
            "hub_tunnel_ip":   {"title": "hub_tunnel_ip",   "type": "string"},
            "spoke_tunnel_ip": {"title": "spoke_tunnel_ip", "type": "string"},
            "allocated_prefix":{"title": "allocated_prefix","type": "string"},
        }, "required": ["snow_ticket_id", "spoke_site_name", "verify_status"]},
        {"type": "object", "properties": {
            "close_out_status": {"type": "string"},
            "snow_update_result": {"type": "object"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 9. SINGLE-SPOKE ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
def build_single_spoke():
    PFX = f"@{PROJECT_ID}: VPN - "
    tasks = {
        **start_end(50, 600, 4800, 600),

        # ── Prepare device arrays ──
        **merge_task("a0b0", [
            {"key": "hostname", "value": {"task": "job", "variable": "hub_hostname"}}
        ], "hub_hostname_wrap", x=250, y=600, summary="Wrap hub hostname"),
        **{"b0c0": {
            "name": "makeData", "canvasName": "makeData", "summary": "Create hub devices array",
            "location": "Application", "locationType": None, "app": "WorkFlowEngine",
            "type": "operation", "displayName": "WorkFlowEngine",
            "variables": {"incoming": {
                "input": '[\"<!hostname!>\"]', "outputType": "json",
                "variables": "$var.job.hub_hostname_wrap"
            }, "outgoing": {"output": "$var.job.hub_devices"}, "error": "", "decorators": []},
            "groups": [], "actor": "Pronghorn", "scheduled": False,
            "nodeLocation": {"x": 450, "y": 600}
        }},
        **merge_task("c0d0", [
            {"key": "hostname", "value": {"task": "job", "variable": "spoke_hostname"}}
        ], "spoke_hostname_wrap", x=650, y=600, summary="Wrap spoke hostname"),
        **{"d0e0": {
            "name": "makeData", "canvasName": "makeData", "summary": "Create spoke devices array",
            "location": "Application", "locationType": None, "app": "WorkFlowEngine",
            "type": "operation", "displayName": "WorkFlowEngine",
            "variables": {"incoming": {
                "input": '[\"<!hostname!>\"]', "outputType": "json",
                "variables": "$var.job.spoke_hostname_wrap"
            }, "outgoing": {"output": "$var.job.spoke_devices"}, "error": "", "decorators": []},
            "groups": [], "actor": "Pronghorn", "scheduled": False,
            "nodeLocation": {"x": 850, "y": 600}
        }},

        # ── Phase 1: Pre-Flight ──
        **childjob_task("e0f0", PFX+"Pre-Flight Check", {
            "snow_ticket_id":      {"task": "job", "value": "snow_ticket_id"},
            "hub_hostname":        {"task": "job", "value": "hub_hostname"},
            "spoke_hostname":      {"task": "job", "value": "spoke_hostname"},
            "hub_wan_interface":   {"task": "job", "value": "hub_wan_interface"},
            "spoke_wan_interface": {"task": "job", "value": "spoke_wan_interface"},
            "hub_trustpoint":      {"task": "job", "value": "hub_trustpoint"},
            "spoke_trustpoint":    {"task": "job", "value": "spoke_trustpoint"},
        }, x=1050, y=600, summary="Pre-Flight Check"),
        **query_task("f0a1", "preflight_status", "$var.e0f0.job_details", "preflight_status", x=1300, y=600),
        **eval_task("a1b1", "preflight_status", "job", "==", "success", summary="Pre-flight passed?", x=1500, y=600),

        # ── Phase 2: Tunnel Design ──
        **childjob_task("b1c1", PFX+"Tunnel Design", {
            "netbox_prefix_pool_name": {"task": "job", "value": "netbox_prefix_pool_name"},
            "spoke_site_name":  {"task": "job", "value": "spoke_site_name"},
            "spoke_as":         {"task": "job", "value": "spoke_as"},
            "hub_wan_ip":       {"task": "static", "value": ""},
            "spoke_wan_ip":     {"task": "static", "value": ""},
            "hub_trustpoint":   {"task": "job", "value": "hub_trustpoint"},
            "spoke_trustpoint": {"task": "job", "value": "spoke_trustpoint"},
            "crypto_map_name":  {"task": "job", "value": "crypto_map_name"},
        }, x=1750, y=600, summary="Tunnel Design - NetBox allocation"),
        **query_task("c1d1", "taskStatus", "$var.b1c1.job_details", "tunnel_design_status", x=2000, y=600),
        **query_task("d1e1", "allocated_prefix", "$var.b1c1.job_details", "allocated_prefix", x=2150, y=600),
        **query_task("e1f1", "hub_config_vars", "$var.b1c1.job_details", "hub_config_vars", x=2300, y=600),
        **eval_task("f1a2", "tunnel_design_status", "job", "==", "success", summary="Tunnel design ok?", x=2450, y=600),

        # ── Phase 3: Config Backup ──
        **childjob_task("a2b2", PFX+"Config Backup", {
            "hub_hostname":   {"task": "job", "value": "hub_hostname"},
            "spoke_hostname": {"task": "job", "value": "spoke_hostname"},
        }, x=2650, y=600, summary="Backup hub and spoke configs"),
        **query_task("b2c2", "taskStatus", "$var.a2b2.job_details", "backup_status", x=2900, y=600),
        **eval_task("c2d2", "backup_status", "job", "==", "success", summary="Backup ok?", x=3050, y=600),

        # ── Phase 4: Configure Hub ──
        **childjob_task("d2e2", PFX+"Configure Hub", {
            "hub_hostname":    {"task": "job", "value": "hub_hostname"},
            "hub_devices":     {"task": "d0e0", "value": "output"},
            "hub_config_vars": {"task": "job", "value": "hub_config_vars"},
        }, x=3250, y=600, summary="Configure Hub ASA"),
        **query_task("e2f2", "taskStatus", "$var.d2e2.job_details", "hub_config_status", x=3500, y=600),
        **eval_task("f2a3", "hub_config_status", "job", "==", "success", summary="Hub configured ok?", x=3650, y=600),

        # ── Phase 5: Configure Spoke ──
        **childjob_task("a3b3", PFX+"Configure Spoke", {
            "spoke_hostname":    {"task": "job", "value": "spoke_hostname"},
            "spoke_devices":     {"task": "d0e0", "value": "output"},
            "spoke_config_vars": {"task": "job", "value": "hub_config_vars"},
        }, x=3850, y=600, summary="Configure Spoke ASA"),
        **query_task("b3c3", "taskStatus", "$var.a3b3.job_details", "spoke_config_status", x=4100, y=600),
        **eval_task("c3d3", "spoke_config_status", "job", "==", "success", summary="Spoke configured ok?", x=4250, y=600),

        # ── Phase 6: Verify Tunnel ──
        **childjob_task("d3e3", PFX+"Verify Tunnel", {
            "hub_hostname":    {"task": "job", "value": "hub_hostname"},
            "spoke_hostname":  {"task": "job", "value": "spoke_hostname"},
            "hub_devices":     {"task": "d0e0", "value": "output"},
            "spoke_devices":   {"task": "d0e0", "value": "output"},
            "hub_tunnel_ip":   {"task": "static", "value": ""},
            "spoke_tunnel_ip": {"task": "static", "value": ""},
            "spoke_as":        {"task": "job", "value": "spoke_as"},
            "verify_timeout_minutes": {"task": "job", "value": "verify_timeout_minutes"},
        }, x=4450, y=600, summary="Verify IPsec + BGP"),
        **query_task("e3f3", "verify_status", "$var.d3e3.job_details", "verify_status", x=4550, y=600),

        # ── Phase 7: Close Out (success) ──
        **childjob_task("f3a4", PFX+"Close Out", {
            "snow_ticket_id":  {"task": "job", "value": "snow_ticket_id"},
            "spoke_site_name": {"task": "job", "value": "spoke_site_name"},
            "verify_status":   {"task": "job", "value": "verify_status"},
            "hub_tunnel_ip":   {"task": "static", "value": ""},
            "spoke_tunnel_ip": {"task": "static", "value": ""},
            "allocated_prefix":{"task": "job", "value": "allocated_prefix"},
        }, x=4700, y=600, summary="Close Out — update SNOW + NetBox"),

        # ── Rollback paths ──
        **childjob_task("rb01", PFX+"Rollback", {
            "hub_hostname":    {"task": "job", "value": "hub_hostname"},
            "spoke_hostname":  {"task": "job", "value": "spoke_hostname"},
            "hub_devices":     {"task": "d0e0", "value": "output"},
            "spoke_devices":   {"task": "d0e0", "value": "output"},
            "hub_config_vars": {"task": "job", "value": "hub_config_vars"},
            "spoke_config_vars": {"task": "static", "value": {}},
            "configured_hub":   {"task": "static", "value": True},
            "configured_spoke": {"task": "static", "value": False},
        }, x=3650, y=870, summary="Rollback hub only"),
        **childjob_task("rb02", PFX+"Rollback", {
            "hub_hostname":    {"task": "job", "value": "hub_hostname"},
            "spoke_hostname":  {"task": "job", "value": "spoke_hostname"},
            "hub_devices":     {"task": "d0e0", "value": "output"},
            "spoke_devices":   {"task": "d0e0", "value": "output"},
            "hub_config_vars": {"task": "job", "value": "hub_config_vars"},
            "spoke_config_vars": {"task": "static", "value": {}},
            "configured_hub":   {"task": "static", "value": True},
            "configured_spoke": {"task": "static", "value": True},
        }, x=4250, y=870, summary="Rollback hub + spoke"),
        **childjob_task("rb03", PFX+"Close Out", {
            "snow_ticket_id":  {"task": "job", "value": "snow_ticket_id"},
            "spoke_site_name": {"task": "job", "value": "spoke_site_name"},
            "verify_status":   {"task": "static", "value": "failed"},
            "hub_tunnel_ip":   {"task": "static", "value": ""},
            "spoke_tunnel_ip": {"task": "static", "value": ""},
            "allocated_prefix":{"task": "static", "value": ""},
        }, x=4550, y=870, summary="Close Out with Failed status"),
    }

    # Early fail path: pre-flight/design/backup failures go to Close Out (Failed) directly
    fail_close = "rb03"

    transitions = {
        "workflow_start": {"a0b0": {"type": "standard", "state": "success"}},
        "a0b0": {"b0c0": {"type": "standard", "state": "success"}},
        "b0c0": {"c0d0": {"type": "standard", "state": "success"}},
        "c0d0": {"d0e0": {"type": "standard", "state": "success"}},
        "d0e0": {"e0f0": {"type": "standard", "state": "success"}},
        "e0f0": {"f0a1": {"type": "standard", "state": "success"}},
        "f0a1": {"a1b1": {"type": "standard", "state": "success"}},
        "a1b1": {"b1c1": {"type": "standard", "state": "success"}, fail_close: {"type": "standard", "state": "failure"}},
        "b1c1": {"c1d1": {"type": "standard", "state": "success"}},
        "c1d1": {"d1e1": {"type": "standard", "state": "success"}},
        "d1e1": {"e1f1": {"type": "standard", "state": "success"}},
        "e1f1": {"f1a2": {"type": "standard", "state": "success"}},
        "f1a2": {"a2b2": {"type": "standard", "state": "success"}, fail_close: {"type": "standard", "state": "failure"}},
        "a2b2": {"b2c2": {"type": "standard", "state": "success"}},
        "b2c2": {"c2d2": {"type": "standard", "state": "success"}},
        "c2d2": {"d2e2": {"type": "standard", "state": "success"}, fail_close: {"type": "standard", "state": "failure"}},
        "d2e2": {"e2f2": {"type": "standard", "state": "success"}},
        "e2f2": {"f2a3": {"type": "standard", "state": "success"}},
        "f2a3": {"a3b3": {"type": "standard", "state": "success"}, "rb01": {"type": "standard", "state": "failure"}},
        "a3b3": {"b3c3": {"type": "standard", "state": "success"}},
        "b3c3": {"c3d3": {"type": "standard", "state": "success"}},
        "c3d3": {"d3e3": {"type": "standard", "state": "success"}, "rb02": {"type": "standard", "state": "failure"}},
        "d3e3": {"e3f3": {"type": "standard", "state": "success"}},
        "e3f3": {"f3a4": {"type": "standard", "state": "success"}},
        "f3a4": {"workflow_end": {"type": "standard", "state": "success"}},
        "rb01": {"rb03": {"type": "standard", "state": "success"}},
        "rb02": {"rb03": {"type": "standard", "state": "success"}},
        "rb03": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Single-Spoke Orchestrator", "single_spoke",
        "Orchestrates full IPsec tunnel provisioning lifecycle for a single hub-spoke pair",
        tasks, transitions,
        {"type": "object", "properties": {
            "snow_ticket_id":  {"title": "snow_ticket_id",  "type": "string"},
            "hub_hostname":    {"title": "hub_hostname",    "type": "string"},
            "spoke_hostname":  {"title": "spoke_hostname",  "type": "string"},
            "spoke_site_name": {"title": "spoke_site_name", "type": "string"},
            "hub_wan_interface":   {"title": "hub_wan_interface",   "type": "string"},
            "spoke_wan_interface": {"title": "spoke_wan_interface", "type": "string"},
            "hub_trustpoint":   {"title": "hub_trustpoint",   "type": "string"},
            "spoke_trustpoint": {"title": "spoke_trustpoint", "type": "string"},
            "spoke_as":         {"title": "spoke_as",         "type": "number"},
            "netbox_prefix_pool_name": {"title": "netbox_prefix_pool_name", "type": "string"},
            "crypto_map_name":  {"title": "crypto_map_name",  "type": "string"},
            "verify_timeout_minutes": {"title": "verify_timeout_minutes", "type": "number"},
        }, "required": ["snow_ticket_id", "hub_hostname", "spoke_hostname", "spoke_site_name", "spoke_as", "crypto_map_name"]},
        {"type": "object", "properties": {
            "verify_status":       {"type": "string"},
            "preflight_status":    {"type": "string"},
            "tunnel_design_status":{"type": "string"},
            "backup_status":       {"type": "string"},
            "hub_config_status":   {"type": "string"},
            "spoke_config_status": {"type": "string"},
            "allocated_prefix":    {"type": "string"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 10. BATCH ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
def build_batch():
    PFX = f"@{PROJECT_ID}: VPN - "
    tasks = {
        **start_end(50, 600, 900, 600),
        # Loop Single-Spoke Orchestrator sequentially over all spokes
        **childjob_task("a1b2", PFX+"Single-Spoke Orchestrator", {},
                        x=250, y=600, summary="Provision all spokes (sequential)",
                        loop_type="sequential", data_array="$var.job.spokes"),
        **query_task("b2c3", "loop", "$var.a1b2.job_details", "batch_results", x=550, y=600),
        **newvar("c3d4", "batch_status", "complete", "batch_status", x=750, y=600, summary="Batch complete"),
    }
    transitions = {
        "workflow_start": {"a1b2": {"type": "standard", "state": "success"}},
        "a1b2": {"b2c3": {"type": "standard", "state": "success"}},
        "b2c3": {"c3d4": {"type": "standard", "state": "success"}},
        "c3d4": {"workflow_end": {"type": "standard", "state": "success"}},
        "workflow_end": {}
    }
    return wf_base(
        "VPN - Batch Orchestrator", "batch",
        "Provisions multiple spoke tunnels sequentially (rolling execution for hub safety)",
        tasks, transitions,
        {"type": "object", "properties": {
            "spokes": {"title": "spokes", "type": "array",
                       "description": "Array of spoke definition objects, each matching Single-Spoke Orchestrator inputs"},
            "max_parallel": {"title": "max_parallel", "type": "number"},
        }, "required": ["spokes"]},
        {"type": "object", "properties": {
            "batch_results": {"type": "array"},
            "batch_status":  {"type": "string"},
        }}
    )


# ─────────────────────────────────────────────────────────────────────────────
# MOP COMMAND TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────
def mop_template(name, description, commands):
    # MOP schema: created/lastUpdated = integer (epoch ms), createdBy/lastUpdatedBy = null or string
    return {
        "name": name, "description": description, "os": "",
        "passRule": True, "ignoreWarnings": False,
        "commands": commands, "tags": [],
        "created": 1744934400000, "createdBy": None,
        "lastUpdated": 1744934400000, "lastUpdatedBy": None,
    }


def rule(text, ev="contains"):
    return {"rule": text, "eval": ev, "severity": "error", "evaluation": "pass"}


MOPS = [
    mop_template("CT-ASA-Get-WAN-IP", "Get WAN interface IP from ASA", [
        {"command": "show interface <!wan_interface!>", "passRule": True,
         "rules": [rule("Internet address is"), rule("line protocol is up")]}
    ]),
    mop_template("CT-ASA-Verify-Trustpoint", "Verify certificate trustpoint exists on ASA", [
        {"command": "show crypto ca trustpoints <!trustpoint_name!>", "passRule": True,
         "rules": [rule("<!trustpoint_name!>")]}
    ]),
    mop_template("CT-ASA-Hub-IPsec-Config", "Apply IPsec crypto map entry and BGP neighbor on hub ASA", [
        {"command": "configure terminal", "passRule": False, "rules": []},
        {"command": "crypto map <!crypto_map_name!> <!seq_num!> match address VPN-ACL-<!seq_num!>", "passRule": False, "rules": []},
        {"command": "crypto map <!crypto_map_name!> <!seq_num!> set peer <!spoke_wan_ip!>", "passRule": False, "rules": []},
        {"command": "crypto map <!crypto_map_name!> <!seq_num!> set ikev2 ipsec-proposal HIGH", "passRule": False, "rules": []},
        {"command": "crypto map <!crypto_map_name!> <!seq_num!> set trustpoint <!hub_trustpoint!>", "passRule": False, "rules": []},
        {"command": "router bgp 65000", "passRule": False, "rules": []},
        {"command": " neighbor <!spoke_tunnel_ip!> remote-as <!spoke_as!>", "passRule": False, "rules": []},
        {"command": " neighbor <!spoke_tunnel_ip!> activate", "passRule": False, "rules": []},
        {"command": "end", "passRule": True, "rules": [rule("ERROR", "!contains")]},
    ]),
    mop_template("CT-ASA-Spoke-IPsec-Config", "Apply full IPsec tunnel and BGP config on spoke ASA", [
        {"command": "configure terminal", "passRule": False, "rules": []},
        {"command": "crypto ikev2 policy 10", "passRule": False, "rules": []},
        {"command": " encryption aes-256", "passRule": False, "rules": []},
        {"command": " integrity sha256", "passRule": False, "rules": []},
        {"command": " group 14", "passRule": False, "rules": []},
        {"command": " prf sha256", "passRule": False, "rules": []},
        {"command": " lifetime seconds 86400", "passRule": False, "rules": []},
        {"command": "crypto ipsec ikev2 ipsec-proposal HIGH", "passRule": False, "rules": []},
        {"command": " protocol esp encryption aes-gcm-256", "passRule": False, "rules": []},
        {"command": " protocol esp integrity sha-256", "passRule": False, "rules": []},
        {"command": "tunnel-group <!hub_wan_ip!> type ipsec-l2l", "passRule": False, "rules": []},
        {"command": "tunnel-group <!hub_wan_ip!> ipsec-attributes", "passRule": False, "rules": []},
        {"command": " ikev2 local-authentication certificate <!spoke_trustpoint!>", "passRule": False, "rules": []},
        {"command": " ikev2 remote-authentication certificate", "passRule": False, "rules": []},
        {"command": "crypto map VPN-MAP 10 match address VPN-ACL-HUB", "passRule": False, "rules": []},
        {"command": "crypto map VPN-MAP 10 set peer <!hub_wan_ip!>", "passRule": False, "rules": []},
        {"command": "crypto map VPN-MAP 10 set ikev2 ipsec-proposal HIGH", "passRule": False, "rules": []},
        {"command": "crypto map VPN-MAP 10 set pfs group14", "passRule": False, "rules": []},
        {"command": "router bgp <!spoke_as!>", "passRule": False, "rules": []},
        {"command": " neighbor <!hub_tunnel_ip!> remote-as 65000", "passRule": False, "rules": []},
        {"command": " neighbor <!hub_tunnel_ip!> activate", "passRule": False, "rules": []},
        {"command": "end", "passRule": True, "rules": [rule("ERROR", "!contains")]},
    ]),
    mop_template("CT-ASA-Verify-IKEv2-SA", "Verify IKEv2 SA is established on ASA", [
        {"command": "show crypto ikev2 sa", "passRule": True,
         "rules": [rule("MM_ACTIVE"), rule("Child SA:")]}
    ]),
    mop_template("CT-ASA-Verify-BGP", "Verify BGP neighbor adjacency on ASA", [
        {"command": "show bgp neighbors <!neighbor_ip!> | include BGP state", "passRule": True,
         "rules": [rule("BGP state = Established")]}
    ]),
    mop_template("CT-ASA-Ping-Tunnel", "Ping across tunnel interface on ASA", [
        {"command": "ping <!target_ip!> source <!source_ip!> repeat 5", "passRule": True,
         "rules": [rule("Success rate is 100 percent"), rule("!!!!")]}
    ]),
    mop_template("CT-ASA-Hub-Rollback", "Remove tunnel crypto map entry and BGP neighbor from hub ASA", [
        {"command": "configure terminal", "passRule": False, "rules": []},
        {"command": "router bgp 65000", "passRule": False, "rules": []},
        {"command": " no neighbor <!spoke_tunnel_ip!>", "passRule": False, "rules": []},
        {"command": "no crypto map <!crypto_map_name!> <!seq_num!>", "passRule": False, "rules": []},
        {"command": "end", "passRule": True, "rules": [rule("ERROR", "!contains")]},
    ]),
    mop_template("CT-ASA-Spoke-Rollback", "Remove full tunnel config from spoke ASA", [
        {"command": "configure terminal", "passRule": False, "rules": []},
        {"command": "no crypto map VPN-MAP 10", "passRule": False, "rules": []},
        {"command": "no tunnel-group <!hub_wan_ip!>", "passRule": False, "rules": []},
        {"command": "no crypto ikev2 policy 10", "passRule": False, "rules": []},
        {"command": "router bgp <!spoke_as!>", "passRule": False, "rules": []},
        {"command": " no neighbor <!hub_tunnel_ip!>", "passRule": False, "rules": []},
        {"command": "end", "passRule": True, "rules": [rule("ERROR", "!contains")]},
    ]),
]


# ─────────────────────────────────────────────────────────────────────────────
# BUILD PROJECT
# ─────────────────────────────────────────────────────────────────────────────
def build_project():
    workflows = [
        ("preflight",      build_preflight()),
        ("tunnel_design",  build_tunnel_design()),
        ("config_backup",  build_config_backup()),
        ("configure_hub",  build_configure_hub()),
        ("configure_spoke",build_configure_spoke()),
        ("verify_tunnel",  build_verify_tunnel()),
        ("rollback",       build_rollback()),
        ("close_out",      build_close_out()),
        ("single_spoke",   build_single_spoke()),
        ("batch",          build_batch()),
    ]

    components = []
    iid = 1

    for key, wf in workflows:
        components.append({
            "iid": iid, "type": "workflow",
            "reference": WF_REF[key],  # component reference != doc uuid (matches export format)
            "folder": "/",
            "document": wf
        })
        iid += 1

    for mop in MOPS:
        components.append({
            "iid": iid, "type": "mopCommandTemplate",
            "reference": f"@{PROJECT_ID}: {mop['name']}", "folder": "/",
            "document": mop
        })
        iid += 1

    return {
        "project": {
            "_id": PROJECT_ID,
            "iid": 1,
            "name": "VPN Tunnel Provisioning",
            "description": "IPsec VPN hub-and-spoke provisioning on Cisco ASA with NetBox IPAM and ServiceNow integration",
            "thumbnail": "", "backgroundColor": "#FFFFFF",
            "components": components,
            "created": TODAY,
            "createdBy": CREATED_BY_PRJ,
            "lastUpdated": TODAY,
            "lastUpdatedBy": CREATED_BY_PRJ,
        }
    }


if __name__ == "__main__":
    project = build_project()
    with open("/Users/ankitrbhansali/use-cases/vpn-tunnel/project-import.json", "w") as f:
        json.dump(project, f, indent=2)
    print(f"Generated project-import.json")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Components: {len(project['project']['components'])}")
