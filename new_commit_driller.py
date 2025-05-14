import csv
import os
import git
import shutil
from pydriller import Repository, ModificationType

# File paths
csv_file = "RQ1_Manual_Analysis_Repo_List.csv"  # Replace with your actual CSV file
output_file = "docker_commits.txt"
clone_dir = "cloned_repos"

os.makedirs(clone_dir, exist_ok=True)

urls = []
with open(csv_file, "r", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    for row in reader:
        if row["Uses Docker ?"] == "Yes" and row["Is CPS related/specific"] == "Yes":
            urls.append(row["Repo"])

docker_commits = SortedSet()
for url in urls:
    repo_name = url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(clone_dir, repo_name)

    if not os.path.exists(repo_path):
        try:
            git.Repo.clone_from(url, repo_path)
        except Exception as e:
            print(f"Failed to clone {url}: {e}")
            continue

    for commit in Repository(repo_path).traverse_commits():
        for modified_file in commit.modified_files:
            if ("Dockerfile" in modified_file.filename.lower() or "docker" in modified_file.filename.lower()) and modified_file.change_type is not ModificationType.ADD:
                commit_url = f"https://github.com/{'/'.join(url.split('/')[-2:])}/commit/{commit.hash}"
                docker_commits.add(commit_url)
    shutil.rmtree(repo_path, ignore_errors=True)
with open(output_file, "w", encoding="utf-8") as f:
    for commit_url in sorted(docker_commits):
        f.write(commit_url + "\n")



print(f"Saved {len(docker_commits)} commit URLs to {output_file}")