import scipy.io
import json
import os

def extract_and_pair():
    try:
        mat = scipy.io.loadmat('make_model_name.mat')
        makes_raw = mat['make_names']
        models_raw = mat['model_names']
        
        makes_list = []
        for i in range(makes_raw.shape[0]):
            try:
                if len(makes_raw[i][0]) > 0:
                     makes_list.append(str(makes_raw[i][0][0]).strip())
            except:
                pass
                
        models_list = []
        for i in range(models_raw.shape[0]):
            try:
                # Some might be empty
                if len(models_raw[i][0]) > 0:
                    models_list.append(str(models_raw[i][0][0]).strip())
            except:
                pass
                
        # Now pair them
        # Sort makes by length descending so we match "Land Rover" before "Land" (if distinct)
        makes_list.sort(key=len, reverse=True)
        
        final_cars = []
        unmatched = []
        
        for model_full in models_list:
            matched_make = None
            model_name_clean = model_full
            
            for make in makes_list:
                # Check if model starts with make (case insensitive?)
                # Usually it's "Audi A4", so starts with "Audi"
                if model_full.lower().startswith(make.lower()):
                    matched_make = make
                    # logical model name is the rest
                    # "Audi A4" -> "A4"
                    model_name_clean = model_full[len(make):].strip()
                    break
            
            if matched_make:
                # Clean the model name
                # 1. Remove common body types/trims
                # Note: This is a heuristic.
                ignore_words = ["hatchback", "sedan", "coupe", "convertible", "estate", "hybrid", "tourer", "touring", "sportback", "cabriolet", "roadster", "suv", "mpv", "gt", "limousine", "saloon"]
                
                # Special handle for "Class" in Benz
                # Don't remove "Class" blindly if it's "C Class", but maybe remove "AMG"?
                if "amg" in model_name_clean.lower():
                     # If "C Class AMG", we probably want "C Class"
                     pass
                     
                words = model_name_clean.split()
                clean_words = []
                for w in words:
                    if w.lower() not in ignore_words:
                        clean_words.append(w)
                
                # Reconstruct
                cleaned_name = " ".join(clean_words)
                
                # Special rules
                if "amg" in cleaned_name.lower():
                     cleaned_name = cleaned_name.replace("AMG", "").replace("amg", "").strip()
                     
                # Deduplicate? If we have "A3 hatchback" and "A3 sedan" -> both become "A3"
                # We should add logic to avoid adding duplicates if they resolve to same basic model
                
                final_cars.append({
                    "make": matched_make,
                    "model": cleaned_name,
                    "original": model_full
                })
            else:
                unmatched.append(model_full)
                # Fallback: Use the first word as make?
                # parts = model_full.split(' ', 1)
                # if len(parts) > 1:
                #    final_cars.append({"make": parts[0], "model": parts[1], "original": model_full})
                
        output_data = {
            "mapped": final_cars,
            "unmatched": unmatched,
            "stats": {
                "total_models_raw": len(models_list),
                "mapped_count": len(final_cars),
                "unmatched_count": len(unmatched)
            }
        }
        
        with open('data/all_models.json', 'w') as f:
            json.dump(output_data, f, indent=2)
            
        print(f"Mapped {len(final_cars)} models. Unmatched: {len(unmatched)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_and_pair()
