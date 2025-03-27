import csv
import os
import git
import shutil
from pydriller import Repository

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

docker_commits = []
with open(output_file, "w", encoding="utf-8") as f:
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
                if "Dockerfile" in modified_file.filename.lower() or "docker" in modified_file.filename.lower():
                    commit_url = f"https://github.com/{'/'.join(url.split('/')[-2:])}/commit/{commit.hash}"
                    docker_commits.append(commit_url)
                    f.write(commit_url + "\n")
        shutil.rmtree(repo_path, ignore_errors=True)

print(f"Saved {len(docker_commits)} commit URLs to {output_file}")