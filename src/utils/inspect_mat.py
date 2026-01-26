import scipy.io
import scipy.io

def inspect_mat():
    mat = scipy.io.loadmat('make_model_name.mat')
    makes = mat['make_names']
    models = mat['model_names']
    
    print("--- MAKES SAMPLE ---")
    for i in range(min(5, len(makes))):
        print(makes[i][0][0])
        
    print("\n--- MODELS SAMPLE ---")
    for i in range(min(10, len(models))):
        print(models[i][0][0])

if __name__ == "__main__":
    inspect_mat()
