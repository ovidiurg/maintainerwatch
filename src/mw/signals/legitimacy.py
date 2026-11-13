from __future__ import annotations

import sqlite3

from .. import db
from ..resolve import canonical
from .base import days_since

DISCOUNT_OLD_STILL_PRESENT = 0.5
DISCOUNT_SHARED_PACKAGES = 0.6
DISCOUNT_YOUNG_PACKAGE = 0.8
DISCOUNT_PUBLISHER_SEEN_BEFORE = 0.6
DISCOUNT_SAME_EMAIL_DOMAIN = 0.6
YOUNG_PACKAGE_DAYS = 365
PUBLIC_EMAIL_DOMAINS = {
    "aol.com", "gmail.com", "googlemail.com", "gmx.com", "hotmail.com",
    "example.com", "example.net", "example.org", "icloud.com", "live.com",
    "mail.com", "msn.com", "outlook.com",
    "proton.me", "protonmail.com", "yahoo.com", "yandex.com",
}


def _packages_for(conn: sqlite3.Connection, identity: str) -> set[str]:
    key = identity.strip().lower()
    rows = conn.execute(
        """SELECT DISTINCT system || ':' || name AS pkg
           FROM maintainers WHERE LOWER(identity) = ?
           UNION
           SELECT DISTINCT system || ':' || name
           FROM versions
           WHERE LOWER(publisher_email) = ? OR LOWER(publisher_name) = ?""",
        (key, key, key),
    ).fetchall()
    return {row["pkg"] for row in rows if row["pkg"]}


def assess_change(
    conn: sqlite3.Connection,
    system: str,
    name: str,
    old_identity: str,
    new_identity: str,
    old_raw: str | None = None,
    new_raw: str | None = None,
    at: str | None = None,
    identity_mapping: dict[str, str] | None = None,
) -> dict:
    """Assess whether a maintainer change looks like a legitimate handover."""
    current = {
        row["identity"].strip().lower()
        for row in db.get_maintainers(conn, system, name)
        if row["identity"]
    }
    if identity_mapping:
        current |= {
            canonical(row["identity"], identity_mapping).strip().lower()
            for row in db.get_maintainers(conn, system, name)
            if row["identity"]
        }
    old_keys = {old_identity.strip().lower()}
    new_keys = {new_identity.strip().lower()}
    if old_raw:
        old_keys.add(old_raw.strip().lower())
    if new_raw:
        new_keys.add(new_raw.strip().lower())

    old_still_present = bool(current & old_keys)
    old_packages: set[str] = set()
    for key in old_keys:
        old_packages |= _packages_for(conn, key)
    new_packages: set[str] = set()
    for key in new_keys:
        new_packages |= _packages_for(conn, key)

    package_key = f"{system}:{name}"
    shared_packages = sorted((old_packages & new_packages) - {package_key})

    previous_publishers: set[str] = set()
    if at:
        rows = conn.execute(
            """SELECT publisher_email, publisher_name FROM versions
               WHERE system=? AND name=? AND published_at < ?""",
            (system, name, at),
        ).fetchall()
        for row in rows:
            if row["publisher_email"]:
                previous_publishers.add(row["publisher_email"].strip().lower())
            if row["publisher_name"]:
                previous_publishers.add(row["publisher_name"].strip().lower())
    new_publisher_seen_before = bool(new_keys & previous_publishers)
    same_email_domain = False
    old_domains = {
        key.rsplit("@", 1)[1]
        for key in old_keys
        if "@" in key
    }
    new_domains = {
        key.rsplit("@", 1)[1]
        for key in new_keys
        if "@" in key
    }
    shared_domains = (old_domains & new_domains) - PUBLIC_EMAIL_DOMAINS
    if shared_domains:
        same_email_domain = True

    package = db.get_package(conn, system, name)
    age_days = days_since(package["first_seen"]) if package and package["first_seen"] else None

    discounts: dict[str, float] = {}
    reasons: list[str] = []
    if old_still_present:
        discounts["old_still_present"] = DISCOUNT_OLD_STILL_PRESENT
        reasons.append("old maintainer still has maintainer access")
    if shared_packages:
        discounts["shared_packages"] = DISCOUNT_SHARED_PACKAGES
        reasons.append("old and new maintainers share other packages")
    if new_publisher_seen_before:
        discounts["publisher_seen_before"] = DISCOUNT_PUBLISHER_SEEN_BEFORE
        reasons.append("new publisher already published this package")
    if same_email_domain:
        discounts["same_email_domain"] = DISCOUNT_SAME_EMAIL_DOMAIN
        reasons.append("old and new publishers share an email domain")
    if age_days is not None and age_days < YOUNG_PACKAGE_DAYS:
        discounts["young_package"] = DISCOUNT_YOUNG_PACKAGE
        reasons.append("package is younger than one year")

    discount = min(discounts.values()) if discounts else 1.0
    return {
        "old_still_present": old_still_present,
        "shared_packages": shared_packages[:10],
        "shared_package_count": len(shared_packages),
        "old_package_count": len(old_packages),
        "new_package_count": len(new_packages),
        "new_publisher_seen_before": new_publisher_seen_before,
        "same_email_domain": same_email_domain,
        "previous_publisher_count": len(previous_publishers),
        "package_age_days": round(age_days, 1) if age_days is not None else None,
        "discount": discount,
        "reasons": reasons,
    }
