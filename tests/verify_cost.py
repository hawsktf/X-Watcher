
import sys
import os
sys.path.append(os.getcwd())
from quantifier import estimate_cost

def test_cost():
    model = "gemini-2.5-flash"
    input_tokens = 1000
    output_tokens = 1000
    
    cost = estimate_cost(model, input_tokens, output_tokens)
    print(f"Cost for {model} (1k/1k): ${cost}")
    
    if cost > 0:
        print("✅ SUCCESS: Cost is correctly calculated.")
        sys.exit(0)
    else:
        print("❌ FAILURE: Cost is still 0.")
        sys.exit(1)

if __name__ == "__main__":
    test_cost()
