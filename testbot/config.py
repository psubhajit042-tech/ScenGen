import os
import json
from typing import Any, Dict, Tuple


def _index_by_id(items) -> Dict[str, Any]:
    indexed: Dict[str, Any] = {}
    for item in items:
        indexed[item["id"]] = item
    return indexed


def _load_json(path: str) -> Any:
    with open(path, mode="r", encoding="utf-8") as f:
        return json.load(f)


def load_conf() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    base_dir = os.path.dirname(__file__)
    apps_path = os.path.join(base_dir, "apps.json")
    scenarios_path = os.path.join(base_dir, "scenarios.json")

    if os.path.exists(apps_path) and os.path.exists(scenarios_path):
        apps_data = _load_json(apps_path)
        scenarios_data = _load_json(scenarios_path)
        app_list = apps_data["apps"] if isinstance(apps_data, dict) else apps_data
        scenario_list = (
            scenarios_data["scenarios"]
            if isinstance(scenarios_data, dict)
            else scenarios_data
        )
        return _index_by_id(app_list), _index_by_id(scenario_list)

    conf_data = _load_json(os.path.join(base_dir, "conf.json"))
    return _index_by_id(conf_data["apps"]), _index_by_id(conf_data["scenarios"])


APPS, SCENARIOS = load_conf()
