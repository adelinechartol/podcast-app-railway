import os
import subprocess

port = os.environ.get('PORT', '8000')
print(f"PORT environment variable: '{port}'")
print(f"All env vars with PORT: {[k for k in os.environ.keys() if 'PORT' in k]}")

if not port:
    print("WARNING: PORT is empty, using 8000")
    port = '8000'

cmd = ["gunicorn", "app:app", "--bind", f"0.0.0.0:{port}", "--timeout", "120", "--workers", "1"]
print(f"Running command: {' '.join(cmd)}")

subprocess.run(cmd)
