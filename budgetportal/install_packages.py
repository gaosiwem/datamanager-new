import subprocess

with open('requirements.txt') as f:
    packages = f.readlines()

for package in packages:
    package = package.strip()
    try:
        subprocess.run(['pip', 'install', package], check=True)
    except subprocess.CalledProcessError:
        print(f"Failed to install {package}")
