import argparse
import os

def process_data(input_path, output_path):
    print(f"Processing data from: {input_path}")
    print(f"Saving processed data to: {output_path}")

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Simulate processing: read input, write to output
    try:
        with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
            for line in infile:
                processed_line = line.strip().upper() # Example processing
                outfile.write(processed_line + '\n')
        print("Data processing complete.")
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_path}")
    except Exception as e:
        print(f"An error occurred during processing: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process raw data files.")
    parser.add_argument("--input", required=True, help="Path to the input data file.")
    parser.add_argument("--output", required=True, help="Path for the output processed data file.")
    args = parser.parse_args()

    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Construct dynamic paths ---
    # Example: If input data is in a 'data' folder one level up from 'src'
    input_file_path = os.path.join(script_dir, '..', 'data', args.input)

    # Example: If output should go into an 'output' folder within the 'src' directory
    output_file_path = os.path.join(script_dir, 'output', args.output)

    print(f"Resolved input path: {input_file_path}")
    print(f"Resolved output path: {output_file_path}")

    process_data(input_file_path, output_file_path)