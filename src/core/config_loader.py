import json
from pathlib import Path

class ConfigLoader:
    def __init__(self, config_dir="configs"):
        self.config_dir = Path(config_dir)
        
    def load_config(self, site_name):
        path = self.config_dir / f"{site_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Config for {site_name} not found at {path}")
            
        with open(path, 'r') as f:
            return json.load(f)

    def list_configs(self):
        return [f.stem for f in self.config_dir.glob("*.json")]
