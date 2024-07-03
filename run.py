import subprocess
import os

# Get the current working directory
current_directory = os.getcwd()

# Specify the paths to the Flask apps
app1_path = os.path.join(current_directory, 'website.py')
app2_path = os.path.join(current_directory, 'editor', 'editor.py')

# Run each Flask app in a separate process
subprocess.Popen(['python3', app1_path])
subprocess.Popen(['python3', app2_path])
