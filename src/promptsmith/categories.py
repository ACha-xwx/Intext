from __future__ import annotations


CATEGORY_LABELS = {
    "writing": "写作",
    "presentation": "PPT / 汇报",
    "learning": "学习",
    "planning_research": "策划 / 研究",
    "data_analysis": "数据分析",
    "coding": "编程",
    "general": "通用",
}

CATEGORY_CONFIG = {
    "version": "categories.proposed.v0.1",
    "common_fields": [
        "goal",
        "audience",
        "context",
        "materials",
        "constraints",
        "deliverable",
        "success_criteria",
        "preferences",
        "other",
    ],
    "category_fields": {
        "writing": ["purpose", "length", "evidence_policy", "style"],
        "presentation": ["duration", "slide_count", "core_message", "structure"],
        "learning": ["baseline", "learning_goal", "available_time", "practice"],
        "planning_research": ["decision_purpose", "scope_boundary", "resources", "evidence_policy"],
        "data_analysis": [
            "analysis_question",
            "data_schema",
            "metric_definition",
            "chart_use",
            "analysis_scope",
        ],
        "coding": ["use_context", "features", "runtime", "existing_code", "io_behavior"],
        "general": [],
    },
}
