This package contains the datasets related to the manuscript:

"Problems and Solutions in Applying Continuous Integration and Delivery to 20 Open-Source Cyber-Physical Systems"

In the following we describe the content of each file:

* pull-request-classification.csv -> list all 670 classified pull requests. It contains the following columns:
	- ID -> containing a progressive number for each pull request. Note that we found into 18 pull requests more than one bad practice/challenge, so we duplicate the line and the corresponding ID. 
	- Project -> containing the the name of the project and the owner in the following style: OWNER/PROJECT-NAME
	- Pull Number -> corresponding number of pull request
	- Pull Request Link -> link of pull request
	- Pull Request Title -> the title of the pull request
	- Is Merged? -> containing YES if the pull request is merged, NO otherwise
	- Has a Challenge/BadPractice? -> containing YES if the pull request has a bad practice or a challenge, NO otherwise
	- Is CPS-Specific? -> containing YES if the problem is specific for the CPS domain, NO otherwise
	- Bad Practice -> containing the LABEL of the identified bad practice
	- Challenge/Barrier -> containing the LABEL of the identified challenge
	- Mitigation -> containing the LABEL of the identified mitigation
	- Restructuring -> containing the LABEL of the identified restructuring

* bad-bractices.csv	-> containing the list of bad practices identified in this study, their occurrences	and whether it is new or not
* challenges.csv -> containing the list of challenges identified in this study, their occurrences and whether it is new or not			
* mitigation.csv -> containing the list of mitigation identified in this study, their occurrences and whether it is new or not
* restructuring-actions.csv -> containing the list of restructuring actions identified in this study, their occurrences and whether it is new or not

* relations-bad-res.csv -> containing the identified relations between bad practices and the corresponding restructuring actions, with their occurrences
* relations-chal-mit.csv -> containing the identified relations between challenges and the corresponding mitigation, with their occurrences

* data/ is a folder contains for each project, the whole set of closed PRs, the patterns used to identify the candidate commits, and the PRs obtained after the filtering, from which we have sampled the 670 PRs. 

* selectPRs.py is the script used to identified the candidate PRs considered for the sampling procedure. It requires two input arguments, the file path of the csv files containing all the closed PRs for a project, and a csv file containing the patterns to use for matching among the changed files whether the PR is a candidate one. 
For instance, considering the ompl project in the data/ folder to obtain the ompl_Filtered.csv file you must run:
python3 selectPRs.py < data/projects_data/ompl.csv ompl_Patterns.csv > ompl_Filtered.csv

* FirstRound_Agreements.csv and SecondRound_Agreements.csv contain the result of the independent annotation being done by two annotators used for computing the interrater reliability coefficients. The columns are similar to the ones in pull-request-classification.csv, however the last six columns are doubles, one for each annotator. 
