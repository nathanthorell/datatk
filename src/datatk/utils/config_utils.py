import os
import tomllib
from typing import Any, Dict, Optional


def get_config(tool_name: str, config_path: Optional[str] = None) -> Dict[str, Any]:
    """Helper function to process the config.toml file"""
    if config_path is None:
        config_path = os.environ.get("DATATK_CONFIG_PATH") or os.path.join(
            os.getcwd(), "config.toml"
        )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    if tool_name not in config:
        raise KeyError(f"Configuration for '{tool_name}' not found in config file")

    tool_config: Dict[str, Any] = dict(config[tool_name])

    if "datatk" in config:
        global_config = config["datatk"]

        # Apply global logging_level if not set in tool-specific config section
        if "logging_level" in global_config and "logging_level" not in tool_config:
            tool_config["logging_level"] = global_config["logging_level"]

    return tool_config
