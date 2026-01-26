import json
import os
from pathlib import Path

class MapsManager:
    def __init__(self, maps_dir="maps"):
        self.maps_dir = Path(maps_dir)
        self.maps_dir.mkdir(parents=True, exist_ok=True)
        
        self.make_map_path = self.maps_dir / "make_map.json"
        self.model_map_path = self.maps_dir / "model_map.json"
        self.year_map_path = self.maps_dir / "year_map.json"
        self.generations_path = self.maps_dir / "generations.json"
        
        self.make_map = self._load_json(self.make_map_path)
        self.model_map = self._load_json(self.model_map_path)
        self.year_map = self._load_json(self.year_map_path)
        self.generations = self._load_json(self.generations_path)
        
    def _load_json(self, path):
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}
        
    def _save_json(self, data, path):
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
            
    def save_all(self):
        self._save_json(self.make_map, self.make_map_path)
        self._save_json(self.model_map, self.model_map_path)
        self._save_json(self.year_map, self.year_map_path)
        self._save_json(self.generations, self.generations_path)

    def get_make_id(self, make_name):
        make_name = make_name.strip()
        if make_name not in self.make_map:
            # Assign new ID. Max ID + 1, or 1 if empty
            current_ids = self.make_map.values()
            new_id = max(current_ids) + 1 if current_ids else 1
            self.make_map[make_name] = new_id
            self._save_json(self.make_map, self.make_map_path)
        return self.make_map[make_name]

    def get_model_id(self, make_name, model_name):
        key = f"{make_name}_{model_name}"
        if key not in self.model_map:
            current_ids = self.model_map.values()
            new_id = max(current_ids) + 1 if current_ids else 1
            self.model_map[key] = new_id
            self._save_json(self.model_map, self.model_map_path)
        return self.model_map[key]
        
    def resolve_generation(self, make, model, year):
        """
        Returns the range string (e.g., '2010-2015') for a specific year.
        If no range is found in generations.json, returns the single year as string.
        """
        try:
            year_int = int(year)
        except ValueError:
            return str(year) # Return as is if not a number
            
        if make in self.generations and model in self.generations[make]:
            ranges = self.generations[make][model]
            for r in ranges:
                if r.get('start') <= year_int <= r.get('end'):
                    return r['range']
        
        return str(year)

    def get_year_id(self, make, model, year):
        """
        Gets ID for the resolved generation range.
        Input 'year' can be a single year (which will be resolved) or a range string.
        """
        # First, try to resolve to a range if it looks like a single year
        final_range = self.resolve_generation(make, model, year)
        
        key = f"{make}_{model}_{final_range}"
        if key not in self.year_map:
            current_ids = self.year_map.values()
            new_id = max(current_ids) + 1 if current_ids else 1
            self.year_map[key] = new_id
            self._save_json(self.year_map, self.year_map_path)
            
        return self.year_map[key], final_range

if __name__ == "__main__":
    # Test
    mm = MapsManager("maps")
    print(f"Make ID: {mm.get_make_id('Toyota')}")
    print(f"Model ID: {mm.get_model_id('Toyota', 'Camry')}")
    lid, rng = mm.get_year_id('Toyota', 'Camry', '2012') # Should map to 2011-2014
    print(f"Year ID: {lid} for range {rng}")
