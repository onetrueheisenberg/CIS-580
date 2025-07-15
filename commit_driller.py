# from pydriller import Repository
# import re
# import pandas as pd


# df = pd.read_csv('package/pull-request-classification.csv', sep=';', on_bad_lines='warn')
# repos = set()
# for index, row in df.iterrows():
#     repos.add(row['Project'])
# for repo in repos:
#     path = f'https://github.com/{repo}.git'
#     repo = Repository(path)

#     commits = []
#     for commit in repo.traverse_commits():
#         hash = commit.hash

#         files = []
#         pattern = re.compile(r".*(Dockerfile|\.dockerignore|docker[-_.\w]*)", re.IGNORECASE)
#         try:
#             matches = [file for file in commit.modified_files if pattern.search(file.new_path or "")]
#             # print(f"Files changed in PR #{pr_number}: {changed_files}")
#             if matches:
#                 print(f"Commit with container-related file changes: {path[:-4]}/commit/{commit.hash}")
#         except Exception:
#             print('Could not read files for commit ' + hash)
#             continue



    # record = {
    #     'hash': hash,
    #     'message': commit.msg,
    #     'author_name': commit.author.name,
    #     'author_email': commit.author.email,
    #     'author_date': commit.author_date,
    #     'author_tz': commit.author_timezone,
    #     'committer_name': commit.committer.name,
    #     'committer_email': commit.committer.email,
    #     'committer_date': commit.committer_date,
    #     'committer_tz': commit.committer_timezone,
    #     'in_main': commit.in_main_branch,
    #     'is_merge': commit.merge,
    #     'num_deletes': commit.deletions,
    #     'num_inserts': commit.insertions,
    #     'net_lines': commit.insertions - commit.deletions,
    #     'num_files': commit.files,
    #     'branches': ', '.join(commit.branches), # Comma separated list of branches the commit is found in
    #     'files': ', '.join(files), # Comma separated list of files the commit modifies
    #     'parents': ', '.join(commit.parents), # Comma separated list of parents
    #     # PyDriller Open Source Delta Maintainability Model (OS-DMM) stat. See https://pydriller.readthedocs.io/en/latest/deltamaintainability.html for metric definitions
    #     'dmm_unit_size': commit.dmm_unit_size,
    #     'dmm_unit_complexity': commit.dmm_unit_complexity,
    #     'dmm_unit_interfacing': commit.dmm_unit_interfacing,
    # }
    # # Omitted: modified_files (list), project_path, project_name
    # commits.append(record)
    # print(commits)

# import pandas as pd
# import re
# from github import Github


# df = pd.read_csv('package/pull-request-classification.csv', sep=';', on_bad_lines='warn')
# prlist = []
# pattern = re.compile(r"(Dockerfile|docker-compose\.yml|\.ya?ml$|\.helm$)", re.IGNORECASE)

# ACCESS_TOKEN = "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"
# g = Github(ACCESS_TOKEN)
# repos = set()
# for index, row in df.iterrows():
#     repos.add(row['Project'])
# for repo_name in repos:
#         try:
#             repo = g.get_repo(repo_name)

#             files = [file.path for file in repo.get_contents("")]
#             dockerfiles = [f for f in files if "Dockerfile" in f or "docker" in f.lower()]
#             # print(f"Files changed in PR #{pr_number}: {changed_files}")
#             if dockerfiles:
#                 print(f"PR with container-related file changes: https://github.com/{repo_name}")

#         except Exception as e:
#             print(f"Error processing PR #{row['Pull Number']} in {row['Project']}: {e}")

from github import Github
import requests

ACCESS_TOKEN = "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"

urltemp = "https://api.github.com/search/code?q=topic:"
# Headers
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {ACCESS_TOKEN}",  # Replace with your GitHub token
    "X-GitHub-Api-Version": "2022-11-28"
}
g = Github(ACCESS_TOKEN)
repos = set()

topics = ['automotive', 'autonomous-driving',  'embedded-systems', 'robot', 'robotics', 'ros', 'autonomous-vehicles', 'cyber-physical-systems', 'drone', 'drones', 'embedded', 'self-driving-car', 'self-driving cars'];
unique_set = set()
for topic in topics:
    url = urltemp + topic + '+filename:Dockerfile'
    print(url)
    response = requests.get(url, headers=headers).json()
    # response = requests.get(url + topic + '+topic:docker' + '&fork=False', headers=headers).json()
    print(response.items())
    if "items" in response:  # Ensure 'items' key exists
        for i in response["items"]:
            # print(isinstance(i, dict))
            if isinstance(i, dict) and "html_url" in i and i['stargazers_count'] >= 10 and i['fork'] is False:  # Use 'html_url' instead of 'url'
                unique_set.add(i["html_url"])
                print(i["html_url"])

# print(unique_set)
# 1. checkout
# 2. local pydriller commit analysis -> list of commit ids
# 3. delete