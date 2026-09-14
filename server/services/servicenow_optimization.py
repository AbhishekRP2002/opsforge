"""Source example recommendations: three metric families are explicitly synthetic."""

import json
import random

from . import servicenow_store as store

TYPES = {
    "inactive_items": (
        "Inactive Catalog Items",
        "Items that are currently inactive in the catalog",
        "medium",
        "low",
        "Review and either update or remove these items",
    ),
    "low_usage": (
        "Low Usage Catalog Items",
        "Items that have very few orders",
        "medium",
        "medium",
        "Consider promoting these items or removing them if no longer needed",
    ),
    "high_abandonment": (
        "High Abandonment Rate Items",
        "Items that are frequently added to cart but not ordered",
        "high",
        "medium",
        "Simplify the request process or improve the item description",
    ),
    "slow_fulfillment": (
        "Slow Fulfillment Items",
        "Items that take longer than average to fulfill",
        "high",
        "high",
        "Review the fulfillment process and identify bottlenecks",
    ),
    "description_quality": (
        "Poor Description Quality",
        "Items with missing, short, or low-quality descriptions",
        "medium",
        "low",
        "Improve the descriptions to better explain the item's purpose and benefits",
    ),
}


def _quality(item):
    description = item.get("short_description", "")
    issues, score = [], 100
    if not description:
        issues, score = ["Missing description"], 0
    else:
        if len(description) < 30:
            issues.extend(["Description too short", "Lacks detail"])
            score -= 70
        if any(term in description.lower() for term in ("click here", "request this")):
            issues.append("Uses instructional language instead of descriptive")
            score -= 50
        if any(
            term in description.lower()
            for term in ("etc", "and more", "and so on", "stuff", "things")
        ):
            issues.append("Contains vague terms")
            score -= 30
    return item | {
        "description_quality": max(0, min(100, score)),
        "quality_issues": issues,
    }


def get_optimization_recommendations(db, arguments, step, clock):
    category = arguments["category_id"]
    if category and store.get(db, "sc_category", category) is None:
        return store.failure(
            "simulation_profile: catalog category not found", recommendations=[]
        )
    seed = json.loads(
        db.connection.execute("SELECT value FROM metadata WHERE key='seed'").fetchone()[
            0
        ]
    )
    rng = random.Random(f"{seed}:{step}:{clock}:catalog-optimization")
    recommendations = []
    for kind in arguments["recommendation_types"]:
        if kind not in TYPES:
            continue
        active = "false" if kind == "inactive_items" else "true"
        rows = [
            row
            for row in store.all_rows(db, "sc_cat_item")
            if str(row.get("active")).lower() == active
            and (not category or row.get("category") == category)
        ][:50]
        items = [
            {
                key: row.get(key, "")
                for key in ("sys_id", "name", "short_description", "category")
            }
            for row in rows
        ]
        if kind == "description_quality":
            items = [
                value
                for item in items
                if (value := _quality(item))["description_quality"] < 80
            ]
        elif kind in {"low_usage", "high_abandonment", "slow_fulfillment"}:
            items = rng.sample(items, min(len(items), 5))
            for item in items:
                if kind == "low_usage":
                    item["order_count"] = rng.randint(1, 5)
                elif kind == "high_abandonment":
                    rate, adds = rng.randint(40, 80), rng.randint(20, 100)
                    item.update(
                        abandonment_rate=rate,
                        cart_adds=adds,
                        orders=int(adds * (1 - rate / 100)),
                    )
                else:
                    duration = rng.uniform(5.0, 10.0)
                    item.update(
                        avg_fulfillment_time=duration,
                        avg_fulfillment_time_vs_catalog=round(duration / 2.5, 1),
                    )
        if items:
            title, description, impact, effort, action = TYPES[kind]
            recommendations.append(
                {
                    "type": kind,
                    "title": title,
                    "description": description,
                    "items": items,
                    "impact": impact,
                    "effort": effort,
                    "action": action,
                }
            )
    return {"success": True, "recommendations": recommendations}, False


HANDLERS = {"get_optimization_recommendations": get_optimization_recommendations}
