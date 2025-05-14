import git
import shutil
# from pydriller import Git, Repository, ModificationType
from pydriller.git import Git
import random
import os
import subprocess

file_path = "docker_commits.txt"
output_file = "new_docker_commits.txt"
# Target directory to clone repos
base_dir = "cloned_repos"
os.makedirs(base_dir, exist_ok=True)

with open(file_path, 'r') as file:
    commits = [line.strip() for line in file if line.strip()]
full_list = list(commits)
sampled_list = sorted(random.sample(full_list, 333))

for url in sampled_list:
    parts = url.strip().split('/')
    owner, repo, sha = parts[3], parts[4], parts[-1]
    repo_url = f"https://github.com/{owner}/{repo}.git"

    # Create a unique folder for this commit
    local_path = os.path.join(base_dir, f"{owner}__{repo}__{sha}")
    if os.path.exists(local_path):
        print(f"Already exists: {local_path}, skipping.")
        continue

    try:
        print(f"\nFetching {repo_url}@{sha} into {local_path}")

        # Set large buffer to avoid clone failures
        subprocess.run(["git", "config", "--global", "http.postBuffer", "524288000"], check=True)

        # Init and fetch just the target commit
        subprocess.run(["git", "init", local_path], check=True)
        subprocess.run(["git", "-C", local_path, "remote", "add", "origin", repo_url], check=True)
        subprocess.run(["git", "-C", local_path, "fetch", "--depth", "1", "origin", sha], check=True)
        subprocess.run(["git", "-C", local_path, "checkout", sha], check=True)

        print(f"✔ Checked out {sha} at {local_path}")

    except subprocess.CalledProcessError as e:
        print(f"Failed to fetch {repo_url}@{sha}: {e}")



