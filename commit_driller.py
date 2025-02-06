from pydriller import Repository
import re
import pandas as pd


df = pd.read_csv('package/pull-request-classification.csv', sep=';', on_bad_lines='warn')
repos = set()
for index, row in df.iterrows():
    repos.add(row['Project'])
for repo in repos:
    path = f'https://github.com/{repo}.git'
    repo = Repository(path)

    commits = []
    for commit in repo.traverse_commits():
        hash = commit.hash

        files = []
        pattern = re.compile(r".*(Dockerfile|\.dockerignore|docker[-_.\w]*)", re.IGNORECASE)
        try:
            matches = [file for file in commit.modified_files if pattern.search(file.new_path or "")]
            # print(f"Files changed in PR #{pr_number}: {changed_files}")
            if matches:
                print(f"Commit with container-related file changes: {path[:-4]}/commit/{commit.hash}")
        except Exception:
            print('Could not read files for commit ' + hash)
            continue



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

# ACCESS_TOKEN = ""
# g = Github(ACCESS_TOKEN)
# for index, row in df.iterrows():
#     if row['Is Merged?']:  
#         try:
#             repo_name = row['Project']  
#             pr_number = int(row['Pull Number'])
#             pr_link = row['Pull Request Link']

#             repo = g.get_repo(repo_name)
#             pr = repo.get_pull(pr_number)

#             changed_files = [f.filename for f in pr.get_files()]

#             matches = [file for file in changed_files if pattern.search(file)]
#             # print(f"Files changed in PR #{pr_number}: {changed_files}")
#             if matches:
#                 print(f"PR with container-related file changes: {pr_link}")
#                 prlist.append(pr_link)

#         except Exception as e:
#             print(f"Error processing PR #{row['Pull Number']} in {row['Project']}: {e}")

# if prlist:
#     with open("docker_related_prs.txt", "w") as f:
#         f.writelines("\n".join(prlist))