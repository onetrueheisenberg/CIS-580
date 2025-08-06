# import os
# import subprocess

# base_dir = os.getcwd()

# for name in os.listdir(base_dir):
#     print(name)
#     path = os.path.join(base_dir, name)
#     if os.path.isdir(path) and "Dockerfile" in os.listdir(path):
#         tag = name.lower().replace(" ", "_")
#         print(f"📦 Building Docker image for: {name}")
#         try:
#             subprocess.run(["docker", "build", "-t", tag, "."], cwd=path, check=True)
#         except subprocess.CalledProcessError as e:
#             print(f"Failed to build in {path}: {e}")
import os
import subprocess
import sys

base_dir = os.getcwd()
failed_repos = []

for root, dirs, files in os.walk(base_dir):
    if "Dockerfile" in files:
        tag = os.path.basename(root).lower().replace(" ", "_")
        print(f"📦 Building Docker image for: {root}")
        try:
            subprocess.run(["docker", "build", "-t", tag, "."], cwd=root, check=True)
        except subprocess.CalledProcessError as e:
            failed_repos.append(root)
print(failed_repos)
# import os
# import shutil

# base_dir = os.getcwd()
# output_dir = os.path.join(base_dir, "dockerfiles")

# os.makedirs(output_dir, exist_ok=True)

# for root, dirs, files in os.walk(base_dir):
#     if "Dockerfile" in files:
#         relative_path = os.path.relpath(root, base_dir)
#         tag_name = relative_path.replace(os.sep, "_") or "root"
#         dest_path = os.path.join(output_dir, f"Dockerfile_{tag_name}")
        
#         src_path = os.path.join(root, "Dockerfile")
#         print(f"📄 Copying: {src_path} → {dest_path}")
        
#         try:
#             shutil.copy(src_path, dest_path)
#         except Exception as e:
#             print(f"❌ Failed to copy from {src_path}: {e}")