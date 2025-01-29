# We need PyDriller to pull git repository information
from pydriller import Repository, ModificationType, Commit,ModifiedFile

# Replace this path with your own repository of interest
path = 'https://github.com/onetrueheisenberg/cps-ci-cd-analysis.git'
repo = Repository(path)
mod = ModificationType

commits = []
for commit in repo.traverse_commits():
    print('kasdm', commit.files)
    hash = commit.hash

    # Gather a list of files modified in the commit
    files = []
    try:
        for f in commit.modified_files:
            if f.new_path is not None:
                files.append(f.new_path) 
    except Exception:
        print('Could not read files for commit ' + hash)
        continue

    # Capture information about the commit in object format so I can reference it later
    record = {
        'hash': hash,
        'message': commit.msg,
        'author_name': commit.author.name,
        'author_email': commit.author.email,
        'author_date': commit.author_date,
        'author_tz': commit.author_timezone,
        'committer_name': commit.committer.name,
        'committer_email': commit.committer.email,
        'committer_date': commit.committer_date,
        'committer_tz': commit.committer_timezone,
        'in_main': commit.in_main_branch,
        'is_merge': commit.merge,
        'num_deletes': commit.deletions,
        'num_inserts': commit.insertions,
        'net_lines': commit.insertions - commit.deletions,
        'num_files': commit.files,
        'branches': ', '.join(commit.branches), # Comma separated list of branches the commit is found in
        'files': ', '.join(files), # Comma separated list of files the commit modifies
        'parents': ', '.join(commit.parents), # Comma separated list of parents
        # PyDriller Open Source Delta Maintainability Model (OS-DMM) stat. See https://pydriller.readthedocs.io/en/latest/deltamaintainability.html for metric definitions
        'dmm_unit_size': commit.dmm_unit_size,
        'dmm_unit_complexity': commit.dmm_unit_complexity,
        'dmm_unit_interfacing': commit.dmm_unit_interfacing,
    }
    # Omitted: modified_files (list), project_path, project_name
    commits.append(record)
    print(commits)

from github import Github

# Replace with your personal access token
ACCESS_TOKEN = "TOKEN"

# Repository and PR details
REPO_NAME = "nasa/fprime"  # Format: "owner/repo"
PR_NUMBER = 18  # Replace with the actual PR number

# Authenticate and fetch PR details
g = Github(ACCESS_TOKEN)
repo = g.get_repo(REPO_NAME)
pr = repo.get_pull(PR_NUMBER)

# Extract changed files
changed_files = [f.filename for f in pr.get_files()]

# Print the list of files
print("Files changed in PR #{}:".format(PR_NUMBER))
for file in changed_files:
    print(file)