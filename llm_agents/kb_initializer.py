from .knowledge_base import KnowledgeBase, BaseImageInfo, FixPattern, BestPractice, SecurityAdvisory, Severity, Category


def initialize_knowledge_base(kb: KnowledgeBase):    
    kb.base_images["golang"] = BaseImageInfo(
        name="golang",
        latest_stable="golang:1.22-alpine",
        recommended="golang:1.22-alpine",
        eol_versions=["1.12", "1.13", "1.14", "1.15", "1.16", "1.17", "1.18", "1.19", "1.20"],
        security_issues={
            "1.12-alpine3.9": "EOL, multiple CVEs, no security patches",
            "1.13": "EOL, security vulnerabilities",
            "1.14": "EOL, security vulnerabilities"
        },
        notes="Use alpine variants for smaller images"
    )
    
    kb.base_images["alpine"] = BaseImageInfo(
        name="alpine",
        latest_stable="alpine:3.20",
        recommended="alpine:3.20",
        eol_versions=["3.9", "3.10", "3.11", "3.12", "3.13", "3.14", "3.15", "3.16", "3.17", "3.18"],
        security_issues={
            "3.9": "EOL, multiple CVEs",
            "3.10": "EOL, security vulnerabilities",
            "3.11": "EOL, security vulnerabilities"
        },
        notes="Alpine Linux - minimal base image"
    )
    
    kb.base_images["ubuntu"] = BaseImageInfo(
        name="ubuntu",
        latest_stable="ubuntu:24.04",
        recommended="ubuntu:22.04",
        eol_versions=["18.04", "20.04"],
        security_issues={
            "18.04": "EOL, no security updates",
            "20.04": "EOL soon"
        },
        notes="Ubuntu LTS versions recommended"
    )
    
    kb.base_images["node"] = BaseImageInfo(
        name="node",
        latest_stable="node:20-alpine",
        recommended="node:20-alpine",
        eol_versions=["10", "12", "14", "16", "18"],
        security_issues={},
        notes="Use alpine variants for smaller images"
    )
    
    kb.base_images["python"] = BaseImageInfo(
        name="python",
        latest_stable="python:3.12-alpine",
        recommended="python:3.12-alpine",
        eol_versions=["3.6", "3.7", "3.8", "3.9"],
        security_issues={},
        notes="Use alpine variants for smaller images"
    )
    
    kb.fix_patterns["http_to_https"] = FixPattern(
        id="http_to_https",
        name="Convert HTTP to HTTPS",
        category=Category.SECURITY,
        severity=Severity.HIGH,
        description="Change HTTP URLs to HTTPS for secure downloads",
        pattern="http://",
        replacement="https://",
        template=None,
        conditions={"when": "downloading files"},
        examples=[
            "http://storage.googleapis.com → https://storage.googleapis.com"
        ]
    )
    
    kb.fix_patterns["add_checksum_verification"] = FixPattern(
        id="add_checksum_verification",
        name="Add Checksum Verification",
        category=Category.SECURITY,
        severity=Severity.CRITICAL,
        description="Add SHA256 checksum verification for downloaded files",
        pattern="curl.*-o.*\\$\\{.*\\}",
        replacement="",
        template="RUN curl -fsSL -o /tmp/${FILENAME} ${URL} \\\n  && echo '${SHA256} /tmp/${FILENAME}' | sha256sum -c -",
        conditions={"when": "downloading binaries"},
        examples=[
            "Add SHA256 verification after curl downloads"
        ]
    )
    
    kb.fix_patterns["combine_apk_commands"] = FixPattern(
        id="combine_apk_commands",
        name="Combine APK Commands",
        category=Category.PERFORMANCE,
        severity=Severity.MEDIUM,
        description="Combine apk update and apk add into single RUN command",
        pattern="RUN apk update\\s*\\n\\s*RUN apk add",
        replacement="RUN apk update && apk add --no-cache",
        template="RUN apk update && apk add --no-cache <packages> && rm -rf /var/cache/apk/*",
        conditions={"when": "multiple apk commands"},
        examples=[
            "RUN apk update\nRUN apk add curl → RUN apk update && apk add --no-cache curl"
        ]
    )
    
    kb.fix_patterns["add_non_root_user"] = FixPattern(
        id="add_non_root_user",
        name="Add Non-Root User",
        category=Category.SECURITY,
        severity=Severity.HIGH,
        description="Add non-root user and switch to it",
        pattern="",
        replacement="",
        template="RUN addgroup -g 1000 appuser && adduser -D -u 1000 -G appuser appuser\nUSER appuser",
        conditions={"when": "running as root"},
        examples=[
            "Add USER directive after installing packages"
        ]
    )
    
    kb.fix_patterns["update_base_image"] = FixPattern(
        id="update_base_image",
        name="Update Base Image",
        category=Category.SECURITY,
        severity=Severity.HIGH,
        description="Update to latest stable base image version",
        pattern="FROM.*:.*",
        replacement="FROM ${RECOMMENDED_VERSION}",
        template=None,
        conditions={"when": "base image is EOL or outdated"},
        examples=[
            "FROM golang:1.12-alpine → FROM golang:1.22-alpine"
        ]
    )
    
    kb.fix_patterns["use_usr_local_bin"] = FixPattern(
        id="use_usr_local_bin",
        name="Use /usr/local/bin Instead of /bin",
        category=Category.BEST_PRACTICE,
        severity=Severity.LOW,
        description="Use /usr/local/bin for user-installed binaries",
        pattern="/bin/",
        replacement="/usr/local/bin/",
        template=None,
        conditions={"when": "copying user binaries"},
        examples=[
            "COPY binary /bin/ → COPY binary /usr/local/bin/"
        ]
    )
    
    kb.fix_patterns["migrate_dep_to_go_modules"] = FixPattern(
        id="migrate_dep_to_go_modules",
        name="Migrate from dep to Go Modules",
        category=Category.BEST_PRACTICE,
        severity=Severity.MEDIUM,
        description="Replace dep with Go modules",
        pattern="RUN dep ensure",
        replacement="",
        template="COPY go.mod go.sum ./\nRUN go mod download\nCOPY . .\nRUN go build",
        conditions={"when": "using dep"},
        examples=[
            "Remove dep ensure, use go mod download"
        ]
    )
    
    kb.fix_patterns["fix_goarch_mismatch"] = FixPattern(
        id="fix_goarch_mismatch",
        name="Fix GOARCH Mismatch",
        category=Category.COMPATIBILITY,
        severity=Severity.HIGH,
        description="Fix architecture mismatch between Go binary and downloaded binaries",
        pattern="ENV GOARCH=386",
        replacement="ENV GOARCH=amd64",
        template=None,
        conditions={"when": "GOARCH=386 but downloading amd64 binaries"},
        examples=[
            "ENV GOARCH=386 → ENV GOARCH=amd64"
        ]
    )
    
    kb.fix_patterns["replace_maintainer"] = FixPattern(
        id="replace_maintainer",
        name="Replace MAINTAINER with LABEL",
        category=Category.BEST_PRACTICE,
        severity=Severity.LOW,
        description="Replace deprecated MAINTAINER with LABEL maintainer",
        pattern="MAINTAINER",
        replacement="LABEL maintainer",
        template="LABEL maintainer=\"Name <email>\"",
        conditions={"when": "MAINTAINER instruction present"},
        examples=[
            "MAINTAINER name → LABEL maintainer=\"name\""
        ]
    )
    
    # Best Practices
    kb.best_practices["multi_stage_builds"] = BestPractice(
        id="multi_stage_builds",
        name="Use Multi-Stage Builds",
        category=Category.OPTIMIZATION,
        description="Use multi-stage builds to reduce final image size",
        implementation="Use separate FROM statements for build and runtime stages",
        example="FROM builder AS build\n...\nFROM alpine AS final\nCOPY --from=build /app /app",
        priority=9
    )
    
    kb.best_practices["specific_version_tags"] = BestPractice(
        id="specific_version_tags",
        name="Use Specific Version Tags",
        category=Category.SECURITY,
        description="Use specific version tags instead of 'latest'",
        implementation="FROM image:version instead of FROM image:latest",
        example="FROM ubuntu:22.04 instead of FROM ubuntu:latest",
        priority=10
    )
    
    kb.best_practices["non_root_user"] = BestPractice(
        id="non_root_user",
        name="Run as Non-Root User",
        category=Category.SECURITY,
        description="Create and use non-root user",
        implementation="Add USER directive after creating user",
        example="RUN adduser -D appuser\nUSER appuser",
        priority=9
    )
    
    kb.best_practices["layer_caching"] = BestPractice(
        id="layer_caching",
        name="Optimize Layer Caching",
        category=Category.PERFORMANCE,
        description="Order instructions to maximize cache hits",
        implementation="Copy dependency files first, then source code",
        example="COPY go.mod go.sum ./\nRUN go mod download\nCOPY . .",
        priority=8
    )
    
    kb.best_practices["clean_package_cache"] = BestPractice(
        id="clean_package_cache",
        name="Clean Package Cache",
        category=Category.OPTIMIZATION,
        description="Remove package cache to reduce image size",
        implementation="Add cleanup commands in same RUN as install",
        example="RUN apk add --no-cache curl && rm -rf /var/cache/apk/*",
        priority=7
    )
    
    kb.security_advisories["golang_1_12_eol"] = SecurityAdvisory(
        id="golang_1_12_eol",
        base_image="golang:1.12",
        package=None,
        cve=None,
        severity=Severity.CRITICAL,
        description="Golang 1.12 is end-of-life and receives no security updates",
        affected_versions=["1.12", "1.12-alpine"],
        fixed_version="1.22-alpine",
        published_date="2020-02-01"
    )
    
    kb.security_advisories["alpine_3_9_eol"] = SecurityAdvisory(
        id="alpine_3_9_eol",
        base_image="alpine:3.9",
        package=None,
        cve=None,
        severity=Severity.CRITICAL,
        description="Alpine 3.9 is end-of-life and receives no security updates",
        affected_versions=["3.9"],
        fixed_version="3.20",
        published_date="2021-11-01"
    )
    
    kb.save()
    print(f"Knowledge base initialized with {len(kb.base_images)} base images, "
          f"{len(kb.fix_patterns)} fix patterns, {len(kb.best_practices)} best practices, "
          f"and {len(kb.security_advisories)} security advisories")


if __name__ == "__main__":
    kb = KnowledgeBase()
    initialize_knowledge_base(kb)
    print("Knowledge base initialization complete!")

