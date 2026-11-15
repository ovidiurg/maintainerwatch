#!/usr/bin/env python3
"""Write missing GitHub repositories with release timelines."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "maintainerwatch.sqlite"
OUT = ROOT / "data" / "mvp" / "seeds" / "github-priority.txt"
REPOS = [
    "tukaani-project/xz", "kubernetes/kubernetes", "facebook/react",
    "pytorch/pytorch", "rust-lang/rust", "expressjs/express",
    "reviewdog/action-setup", "tj-actions/changed-files",
    "AstrOOnauta/react-native-country-select",
    "AstrOOnauta/react-native-international-phone-number",
    "torvalds/linux", "openssl/openssl", "curl/curl", "git/git",
    "nodejs/node", "python/cpython", "golang/go", "apache/httpd",
    "nginx/nginx", "redis/redis", "postgres/postgres", "mongodb/mongo",
    "grafana/grafana", "prometheus/prometheus", "etcd-io/etcd",
    "hashicorp/terraform", "moby/moby", "containerd/containerd",
    "coredns/coredns", "envoyproxy/envoy", "istio/istio", "helm/helm",
    "argoproj/argo-cd", "jenkinsci/jenkins", "sonatype/nexus-public",
    "apache/kafka", "apache/zookeeper", "apache/spark", "apache/flink",
    "elastic/elasticsearch", "opensearch-project/OpenSearch",
    "ClickHouse/ClickHouse", "spring-projects/spring-boot",
    "spring-projects/spring-framework", "quarkusio/quarkus",
    "micrometer-metrics/micrometer", "netty/netty", "google/guava",
    "google/protobuf", "grpc/grpc-java", "FasterXML/jackson-databind",
    "apache/logging-log4j2", "junit-team/junit5", "mockito/mockito",
    "checkstyle/checkstyle", "pmd/pmd", "spotbugs/spotbugs",
    "sonarsource/sonarqube", "jhy/jsoup", "square/okhttp",
    "square/retrofit", "nodejs/undici", "npm/cli", "vitejs/vite",
    "webpack/webpack", "babel/babel", "eslint/eslint", "docker/compose",
    "cli/cli", "microsoft/vscode", "electron/electron",
]


def main() -> None:
    conn = sqlite3.connect(DB)
    existing = {row[0] for row in conn.execute("SELECT name FROM packages WHERE system='github'")}
    conn.close()
    missing = [name for name in REPOS if name not in existing]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
    print(f"{len(REPOS)} repos; {len(missing)} missing -> {OUT}")


if __name__ == "__main__":
    main()
