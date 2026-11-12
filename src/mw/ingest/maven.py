from __future__ import annotations

import re
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


def _resolve(value: str | None, props: dict[str, str]) -> str | None:
    if not value:
        return value
    text = value
    for _ in range(5):
        replaced = re.sub(
            r"\$\{([^}]+)\}",
            lambda m: props.get(m.group(1).strip(), m.group(0)),
            text,
        )
        if replaced == text:
            break
        text = replaced
    return text


def _collect_properties(text: str) -> dict[str, str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    props: dict[str, str] = {}
    properties = root.find(tag("properties"))
    if properties is not None:
        for child in properties:
            key = child.tag.split("}")[-1]
            props[key] = (child.text or "").strip()

    group = (root.findtext(tag("groupId")) or "").strip()
    artifact = (root.findtext(tag("artifactId")) or "").strip()
    version = (root.findtext(tag("version")) or "").strip()
    parent = root.find(tag("parent"))
    parent_group = (parent.findtext(tag("groupId")) if parent is not None else "") or ""
    parent_artifact = (parent.findtext(tag("artifactId")) if parent is not None else "") or ""
    parent_version = (parent.findtext(tag("version")) if parent is not None else "") or ""

    props.update(
        {
            "project.groupId": group,
            "project.artifactId": artifact,
            "project.version": version,
            "project.parent.groupId": parent_group.strip(),
            "project.parent.artifactId": parent_artifact.strip(),
            "project.parent.version": parent_version.strip(),
            "pom.groupId": group,
            "pom.artifactId": artifact,
            "pom.version": version,
        }
    )

    resolved = dict(props)
    for _ in range(5):
        resolved = {key: _resolve(value, resolved) or "" for key, value in resolved.items()}
    return resolved


def _parse_pom(
    text: str, props: dict[str, str] | None = None
) -> tuple[str | None, str | None, list[str], list[str]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, None, [], []

    ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
    props = props if props is not None else _collect_properties(text)

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    def resolved(value: str | None) -> str:
        return (_resolve(value, props) or "").strip()

    license_name = None
    for lic in root.findall(f".//{tag('licenses')}/{tag('license')}"):
        name = resolved(lic.findtext(tag("name")))
        if name:
            license_name = name
            break

    scm = resolved(
        root.findtext(f".//{tag('scm')}/{tag('url')}")
        or root.findtext(f".//{tag('scm')}/{tag('connection')}")
    )
    if scm:
        for prefix in ("scm:git:", "scm:git@", "git+"):
            if scm.startswith(prefix):
                scm = scm[len(prefix):]
        scm = scm.replace("git@github.com:", "https://github.com/").replace(".git", "")
        if not scm.startswith("http"):
            scm = None

    deps: list[str] = []
    for dep in root.findall(f".//{tag('dependencies')}/{tag('dependency')}"):
        group = resolved(dep.findtext(tag("groupId")))
        artifact = resolved(dep.findtext(tag("artifactId")))
        scope = (dep.findtext(tag("scope")) or "compile").strip().lower()
        optional = (dep.findtext(tag("optional")) or "").strip().lower() == "true"
        if group and artifact and scope in ("compile", "runtime") and not optional:
            deps.append(f"{group}:{artifact}")

    developers: list[str] = []
    for dev in root.findall(f".//{tag('developers')}/{tag('developer')}"):
        ident = (
            resolved(dev.findtext(tag("id")))
            or resolved(dev.findtext(tag("name")))
            or resolved(dev.findtext(tag("email")))
        )
        if ident:
            developers.append(ident)

    return license_name, scm, sorted(set(deps)), developers


def _bom_imports(
    text: str, props: dict[str, str] | None = None
) -> list[tuple[str, str, str]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
    props = props if props is not None else _collect_properties(text)

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    imports: list[tuple[str, str, str]] = []
    for dep in root.findall(
        f".//{tag('dependencyManagement')}/{tag('dependencies')}/{tag('dependency')}"
    ):
        scope = (dep.findtext(tag("scope")) or "").strip().lower()
        if scope != "import":
            continue
        group = (_resolve(dep.findtext(tag("groupId")), props) or "").strip()
        artifact = (_resolve(dep.findtext(tag("artifactId")), props) or "").strip()
        version = (_resolve(dep.findtext(tag("version")), props) or "").strip()
        if group and artifact and version:
            imports.append((group, artifact, version))
    return imports


def _parent_coords(
    text: str, props: dict[str, str] | None = None
) -> tuple[str, str, str] | None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
    props = props if props is not None else _collect_properties(text)

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    parent = root.find(tag("parent"))
    if parent is None:
        return None
    group = (_resolve(parent.findtext(tag("groupId")), props) or "").strip()
    artifact = (_resolve(parent.findtext(tag("artifactId")), props) or "").strip()
    version = (_resolve(parent.findtext(tag("version")), props) or "").strip()
    if group and artifact and version:
        return group, artifact, version
    return None


def _pom_metadata(
    client: CachedClient, group: str, artifact: str, version: str, depth: int = 0
) -> tuple[str | None, str | None, list[str], list[str], dict[str, str]]:
    text = client.get_text(_pom_url(group, artifact, version))
    if not text:
        return None, None, [], [], {}

    own_props = _collect_properties(text)
    parent_props: dict[str, str] = {}
    parent_license = None
    parent_scm = None
    parent_developers: list[str] = []

    if depth < 6:
        parent = _parent_coords(text, own_props)
        if parent:
            (
                parent_license,
                parent_scm,
                _,
                parent_developers,
                parent_props,
            ) = _pom_metadata(client, *parent, depth=depth + 1)

    props = {**parent_props, **own_props}
    license_name, scm, deps, developers = _parse_pom(text, props=props)

    # BOM imports are detected for completeness. Managed dependencies are not
    # direct dependencies, so they are intentionally not added to the edge list.
    _bom_imports(text, props)

    return (
        license_name or parent_license,
        scm or parent_scm,
        deps,
        developers or parent_developers,
        props,
    )


def _metadata_url(group: str, artifact: str) -> str:
    return f"{REPO}/{group.replace('.', '/')}/{artifact}/maven-metadata.xml"


def _metadata_latest(text: str | None) -> str | None:
    if not text:
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    ns = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""

    def tag(name: str) -> str:
        return f"{{{ns}}}{name}" if ns else name

    versioning = root.find(tag("versioning"))
    if versioning is None:
        return None
    for key in ("release", "latest"):
        value = (versioning.findtext(tag(key)) or "").strip()
        if value:
            return value
    versions = [
        v.text.strip()
        for v in versioning.findall(f"{tag('versions')}/{tag('version')}")
        if v.text
    ]
    return versions[-1] if versions else None


def _search(client: CachedClient, query: str, core: str | None = None) -> list[dict]:
    url = f"{SEARCH}?q={quote(query)}&rows=200&wt=json"
    if core:
        url += f"&core={core}"
    doc = client.get_json(url)
    return ((doc or {}).get("response") or {}).get("docs") or []


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


def fetch_package(client: CachedClient, name: str) -> tuple[Package, list[Version], list[Maintainer]] | None:
    parts = _split(name)
    if not parts:
        return None
    group, artifact = parts
    query = f'g:"{group}" AND a:"{artifact}"'

    latest = _metadata_latest(client.get_text(_metadata_url(group, artifact)))
    if not latest:
        latest_docs = _search(client, query)
        latest = latest_docs[0].get("latestVersion") if latest_docs else None
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
    license_name, repo_url, _, developers, _ = _pom_metadata(
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
    latest = _metadata_latest(client.get_text(_metadata_url(group, artifact)))
    if not latest:
        docs = _search(client, f'g:"{group}" AND a:"{artifact}"')
        latest = docs[0].get("latestVersion") if docs else None
    if not latest:
        return []
    _, _, deps, _, _ = _pom_metadata(client, group, artifact, latest)
    return deps
