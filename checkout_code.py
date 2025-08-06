import csv
import os
import git
import shutil
from pydriller import Repository, ModificationType
from sortedcontainers import SortedSet

# File paths
csv_file = "RQ1_Manual_Analysis_Repo_List.csv"
output_file = "docker_repos.txt"
clone_dir = "cloned_repos"

os.makedirs(clone_dir, exist_ok=True)

urls = SortedSet()
with open(csv_file, "r", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    for row in reader:
        if row["Uses Docker ?"] == "Yes" and row["Is CPS related/specific"] == "Yes":
            urls.add(row["Repo"])
for url in urls:
    repo_name = url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(clone_dir, repo_name)

    if not os.path.exists(repo_path):
        try:
            git.Repo.clone_from(url, repo_path)
        except Exception as e:
            print(f"Failed to clone {url}: {e}")
            continue
