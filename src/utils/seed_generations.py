import json
import os
from collections import defaultdict

def seed_generations():
    if not os.path.exists('data/all_models.json'):
        print("all_models.json missing.")
        return
        
    with open('data/all_models.json', 'r') as f:
        data = json.load(f)
        
    mapped_cars = data.get('mapped', [])
    
    # Organize by Make -> Model (set) to deduplicate
    temp_structure = defaultdict(set)
    
    for car in mapped_cars:
        make = car['make']
        model = car['model'].strip()
        if not model: continue
        temp_structure[make].add(model)
        
    # Convert to final structure
    # { "Make": { "Model": [] } }
    
    final_generations = {}
    
    # Load existing if any
    if os.path.exists('maps/generations.json'):
        with open('maps/generations.json', 'r') as f:
            final_generations = json.load(f)
            
    count_new = 0
    for make, models in temp_structure.items():
        if make not in final_generations:
            final_generations[make] = {}
        for model in models:
            if model not in final_generations[make]:
                # Initialize empty
                final_generations[make][model] = []
                count_new += 1
                
    with open('maps/generations.json', 'w') as f:
        json.dump(final_generations, f, indent=2)
        
    print(f"Seeded generations.json with {count_new} new unique models.")
    print(f"Total Makes: {len(final_generations)}")
    
if __name__ == "__main__":
    seed_generations()
