#! /usr/bin/local/python3

import sys
import requests


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text


def extractChangedFilesNames(project, pr_number):
    list_files_modified = list()
    url_to_access = "https://patch-diff.githubusercontent.com/raw/" + project + "/pull/" + pr_number + ".diff"
    page = requests.get(url_to_access)
    if page.status_code == 200:
        lines = page.content.decode('utf8', 'ignore').split("\n")
        for diff_line in lines:
            if diff_line.startswith("diff --git "):
                elements = diff_line.split()
                if len(elements) == 4:
                    elements[2] = remove_prefix(elements[2], "a/")
                    elements[3] = remove_prefix(elements[3], "b/")
                    if elements[2] == elements[3]:
                        list_files_modified.append(elements[2])
                    else:
                        list_files_modified.append(elements[3])
    return list_files_modified


def checkPatterns(files):

    for file in files:
        if not (file.endswith(".txt") or file.endswith(".md") or file.endswith(".png") or file.endswith("jpeg") or file.endswith(".in") or "/docs/" in file or "/doc/" in file or "/Documentation/" in file):
            # satisfy the set of patterns being identified for the project
            for pt in list_patterns:
                if pt in file:
                    return True
            # shell files
            if file.endswith(".sh") or file.endswith(".bash"):
                return True
            # Ci files
            if file.endswith(".yml") or file.endswith(".yaml") or file.endswith(".cmake") or file.endswith(".config") or "Jenkinsfile" in file or "Makefile" in file or "Dockerfile" in file or "Vagrantfile" in file:
                return True
    return False


# aimed at removing duplicated PRs for some restarted projects
pr_numbers = list()

# list of patterns to check
pattern_path = sys.argv[1]
list_patterns = list()

with open(pattern_path) as f:
    lines = f.readlines()
    for line in lines:
        line = line.strip()
        list_patterns.append(line)

for place, line in enumerate(sys.stdin):
    if place:
        line = line.rstrip()
        fields = line.split(",")

        if fields[1] not in pr_numbers:
            # skip PRs with no changed files and no commits
            if fields[8] != '0' and fields[7] != '0':
                commit_list = fields[9].split(' ')
                changed_files = extractChangedFilesNames(fields[0], fields[1])
                if 0 < len(changed_files) == int(fields[7]):
                    if checkPatterns(changed_files):
                        print(line)
            pr_numbers.append(fields[1])
    else:
        print(line.rstrip())

