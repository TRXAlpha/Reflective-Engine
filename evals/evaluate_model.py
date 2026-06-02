import argparse
import os

def evaluate(model_name, config_path):
    print(f"Evaluating model: {model_name} with config: {config_path}")
    # In a real scenario, you would load the config from config_path here
    # For demonstration, we'll just print it.
    try:
        with open(config_path, 'r') as f:
            print("Config file content:")
            print(f.read())
    except FileNotFoundError:
        print(f"Configuration file not found at: {config_path}")
    except Exception as e:
        print(f"Error reading config file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a model with a given configuration.")
    parser.add_argument("--model", required=True, help="Name of the model to evaluate.")
    parser.add_argument("--config", required=True, help="Base name of the configuration file (e.g., 'prod' for 'prod_config.yaml').")
    args = parser.parse_args()

    # Get the directory of the current script
    # This makes paths relative to the script's location, not the working directory
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the dynamic path to the configuration file
    # Assumes config files are in a 'data' subdirectory relative to this script.
    # Example: if args.config is 'prod', it looks for 'data/prod_config.yaml'
    # Adjust 'data' or the filename if your structure is different.
    config_filename = f"{args.config}_config.yaml"
    config_file_path = os.path.join(script_dir, 'data', config_filename)

    # You can also dynamically resolve model paths if they are stored relative to the script
    # Example: model_checkpoint_path = os.path.join(script_dir, '..', 'models', f"{args.model}.ckpt")

    print(f"Attempting to load config from: {config_file_path}")
    evaluate(args.model, config_file_path)