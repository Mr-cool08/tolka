import subprocess
import sys
from pip._internal.operations.freeze import freeze

def generate_requirements_txt(output_file="requirements.txt"):
    try:
        # Get the list of installed packages and versions using pip freeze
        packages = freeze()
        
        # Write the packages to requirements.txt
        with open(output_file, 'w') as f:
            for package in packages:
                f.write(package + '\n')
        
        print(f"Successfully created {output_file} with {len(packages)} packages.")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    generate_requirements_txt()
