from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from ..models import Maintainer, Package, Version
from .http import CachedClient

SEARCH = "https://search.maven.org/solrsearch/select"
REPO = "https://repo1.maven.org/maven2"

SEED_MAVEN = [
    "com.google.guava:guava",
    "org.apache.commons:commons-lang3",
    "org.apache.commons:commons-text",
    "org.apache.commons:commons-collections4",
    "commons-io:commons-io",
    "commons-codec:commons-codec",
    "org.slf4j:slf4j-api",
    "ch.qos.logback:logback-classic",
    "com.fasterxml.jackson.core:jackson-databind",
    "com.fasterxml.jackson.core:jackson-core",
    "com.fasterxml.jackson.core:jackson-annotations",
    "com.google.code.gson:gson",
    "org.springframework:spring-core",
    "org.springframework:spring-web",
    "org.springframework:spring-webmvc",
    "org.springframework.boot:spring-boot",
    "org.springframework.boot:spring-boot-starter-web",
    "org.apache.httpcomponents:httpclient",
    "org.apache.httpcomponents.client5:httpclient5",
    "io.netty:netty-handler",
    "io.netty:netty-codec-http",
    "io.projectreactor:reactor-core",
    "org.jetbrains.kotlin:kotlin-stdlib",
    "org.jetbrains.kotlinx:kotlinx-coroutines-core",
    "org.scala-lang:scala-library",
    "junit:junit",
    "org.junit.jupiter:junit-jupiter",
    "org.mockito:mockito-core",
    "org.hamcrest:hamcrest",
    "org.testng:testng",
    "org.apache.logging.log4j:log4j-core",
    "org.apache.logging.log4j:log4j-api",
    "org.yaml:snakeyaml",
    "com.google.protobuf:protobuf-java",
    "io.grpc:grpc-core",
    "io.grpc:grpc-netty",
    "org.eclipse.jetty:jetty-server",
    "org.apache.tomcat.embed:tomcat-embed-core",
    "jakarta.servlet:jakarta.servlet-api",
    "org.hibernate:hibernate-core",
    "org.postgresql:postgresql",
    "com.h2database:h2",
    "org.apache.kafka:kafka-clients",
    "com.amazonaws:aws-java-sdk-s3",
    "software.amazon.awssdk:s3",
    "io.micrometer:micrometer-core",
    "io.quarkus:quarkus-core",
    "org.apache.maven:maven-core",
    "org.apache.maven:maven-plugin-api",
    "org.codehaus.plexus:plexus-utils",
    "org.ow2.asm:asm",
    "net.bytebuddy:byte-buddy",
    "com.squareup.okhttp3:okhttp",
    "com.squareup.retrofit2:retrofit",
    "io.reactivex.rxjava3:rxjava",
    "org.jooq:jooq",
    "org.flywaydb:flyway-core",
    "com.zaxxer:HikariCP",
    "com.github.ben-manes.caffeine:caffeine",
    "org.springframework.security:spring-security-core",
    "org.springframework.data:spring-data-jpa",
    "org.hibernate.validator:hibernate-validator",
    "jakarta.validation:jakarta.validation-api",
    "com.auth0:java-jwt",
    "io.jsonwebtoken:jjwt-api",
    "org.bouncycastle:bcprov-jdk18on",
    "com.nimbusds:nimbus-jose-jwt",
    "org.apache.commons:commons-compress",
    "org.apache.poi:poi",
    "org.apache.poi:poi-ooxml",
    "org.jsoup:jsoup",
    "org.apache.lucene:lucene-core",
    "org.apache.solr:solr-core",
    "org.apache.zookeeper:zookeeper",
    "org.apache.avro:avro",
    "org.apache.parquet:parquet-hadoop",
    "org.mongodb:mongodb-driver-sync",
    "redis.clients:jedis",
    "io.lettuce:lettuce-core",
    "com.datastax.oss:java-driver-core",
    "org.elasticsearch:elasticsearch",
    "org.opensearch:opensearch",
    "org.apache.camel:camel-core",
    "org.quartz-scheduler:quartz",
    "org.glassfish.jaxb:jaxb-runtime",
    "jakarta.xml.bind:jakarta.xml.bind-api",
    "org.apache.cxf:cxf-core",
    "org.apache.tika:tika-core",
    "org.apache.pdfbox:pdfbox",
    "com.itextpdf:itext7-core",
    "org.apache.groovy:groovy",
    "org.clojure:clojure",
    "com.google.code.findbugs:jsr305",
    "com.google.errorprone:error_prone_annotations",
    "org.checkerframework:checker-qual",
    "org.eclipse.aether:aether-api",
    "org.apache.maven.shared:maven-shared-utils",
    "org.apache.maven:maven-model",
    "org.apache.maven:maven-artifact",
    "org.apache.maven:maven-settings",
    "org.apache.maven:maven-repository-metadata",
    "org.apache.maven:maven-resolver-provider",
    "org.apache.maven:maven-compat",
    "org.apache.maven:maven-embedder",
    "org.apache.maven:maven-builder-support",
    "org.apache.maven:maven-model-builder",
    "org.apache.maven:maven-settings-builder",
]


def normalize_name(name: str) -> str:
    return name.strip().lower()


def _split(name: str) -> tuple[str, str] | None:
    if ":" not in name:
        return None
    group, artifact = name.split(":", 1)
    group, artifact = group.strip(), artifact.strip()
    if not group or not artifact:
        return None
    return group, artifact


def _ms_to_iso(value: int | float | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc).isoformat()
    except (OSError, ValueError, TypeError):
        return None


def _pom_url(group: str, artifact: str, version: str) -> str:
    return (
        f"{REPO}/{group.replace('.', '/')}/{artifact}/{version}/"
        f"{artifact}-{version}.pom"
    )


def _parse_pom(text: str) -> tuple[str | None, str | None, list[str], list[str]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, None, [], []

    ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    license_name = None
    for lic in root.findall(f".//{tag('licenses')}/{tag('license')}"):
        name = (lic.findtext(tag("name")) or "").strip()
        if name:
            license_name = name
            break

    scm = (
        root.findtext(f".//{tag('scm')}/{tag('url')}")
        or root.findtext(f".//{tag('scm')}/{tag('connection')}")
    )
    if scm:
        scm = scm.strip()
        for prefix in ("scm:git:", "scm:git@", "git+"):
            if scm.startswith(prefix):
                scm = scm[len(prefix):]
        scm = scm.replace("git@github.com:", "https://github.com/").replace(".git", "")
        if not scm.startswith("http"):
            scm = None

    deps: list[str] = []
    for dep in root.findall(f".//{tag('dependencies')}/{tag('dependency')}"):
        group = (dep.findtext(tag("groupId")) or "").strip()
        artifact = (dep.findtext(tag("artifactId")) or "").strip()
        scope = (dep.findtext(tag("scope")) or "compile").strip().lower()
        optional = (dep.findtext(tag("optional")) or "").strip().lower() == "true"
        if group and artifact and scope in ("compile", "runtime") and not optional:
            deps.append(f"{group}:{artifact}")

    developers: list[str] = []
    for dev in root.findall(f".//{tag('developers')}/{tag('developer')}"):
        ident = (
            dev.findtext(tag("id"))
            or dev.findtext(tag("name"))
            or dev.findtext(tag("email"))
        )
        if ident and ident.strip():
            developers.append(ident.strip())

    return license_name, scm, sorted(set(deps)), developers


def fetch_top(client: CachedClient, top_n: int, seed_file: str | None = None) -> list[str]:
    if seed_file:
        names = [
            line.strip()
            for line in Path(seed_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        names = list(SEED_MAVEN)
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:top_n]


def _parent_coords(text: str) -> tuple[str, str, str] | None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    parent = root.find(tag("parent"))
    if parent is None:
        return None
    group = (parent.findtext(tag("groupId")) or "").strip()
    artifact = (parent.findtext(tag("artifactId")) or "").strip()
    version = (parent.findtext(tag("version")) or "").strip()
    if group and artifact and version:
        return group, artifact, version
    return None


def _pom_metadata(
    client: CachedClient, group: str, artifact: str, version: str, depth: int = 0
) -> tuple[str | None, str | None, list[str], list[str]]:
    text = client.get_text(_pom_url(group, artifact, version))
    if not text:
        return None, None, [], []
    license_name, scm, deps, developers = _parse_pom(text)

    if (not license_name or not scm) and depth < 3:
        parent = _parent_coords(text)
        if parent:
            p_license, p_scm, _, p_developers = _pom_metadata(
                client, *parent, depth=depth + 1
            )
            license_name = license_name or p_license
            scm = scm or p_scm
            developers = developers or p_developers

    return license_name, scm, deps, developers


def _search(client: CachedClient, query: str, core: str | None = None) -> list[dict]:
    url = f"{SEARCH}?q={quote(query)}&rows=200&wt=json"
    if core:
        url += f"&core={core}"
    doc = client.get_json(url)
    return ((doc or {}).get("response") or {}).get("docs") or []


def fetch_package(client: CachedClient, name: str) -> tuple[Package, list[Version], list[Maintainer]] | None:
    parts = _split(name)
    if not parts:
        return None
    group, artifact = parts
    query = f'g:"{group}" AND a:"{artifact}"'

    latest_docs = _search(client, query)
    if not latest_docs:
        return None
    latest = latest_docs[0].get("latestVersion")
    if not latest:
        return None

    gav_docs = _search(client, query, core="gav")
    versions = [
        Version(
            system="maven",
            name=name,
            version=d["v"],
            published_at=_ms_to_iso(d.get("timestamp")),
            has_sig=False,
            has_provenance=False,
            is_yanked=False,
        )
        for d in gav_docs
        if d.get("v")
    ]
    if not versions:
        versions = [Version(system="maven", name=name, version=latest)]

    license_name = None
    repo_url = None
    developers: list[str] = []
    license_name, repo_url, _, developers = _pom_metadata(
        client, group, artifact, latest
    )

    maintainers = [
        Maintainer(system="maven", name=name, identity=ident,
                   role="developer", source="maven")
        for ident in developers
    ]

    first_seen = min(
        (v.published_at for v in versions if v.published_at), default=None
    )
    pkg = Package(
        system="maven",
        name=name,
        normalized=normalize_name(name),
        downloads_weekly=0,
        repo_url=repo_url,
        license=license_name,
        first_seen=first_seen,
    )
    return pkg, versions, maintainers


def fetch_dependencies(client: CachedClient, name: str) -> list[str]:
    parts = _split(name)
    if not parts:
        return []
    group, artifact = parts
    docs = _search(client, f'g:"{group}" AND a:"{artifact}"')
    if not docs or not docs[0].get("latestVersion"):
        return []
    _, _, deps, _ = _pom_metadata(client, group, artifact, docs[0]["latestVersion"])
    return deps
