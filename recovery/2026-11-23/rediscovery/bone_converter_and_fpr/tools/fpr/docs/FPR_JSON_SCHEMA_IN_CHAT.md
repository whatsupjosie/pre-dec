{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://rearviewforesight.local/schemas/functional-purpose-report.schema.json",
  "title": "Functional Purpose Report",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "fpr_summary",
    "feature_system",
    "date",
    "desired_purpose",
    "stated_purpose",
    "functional_purpose",
    "evidence",
    "impact",
    "alignment_status",
    "confidence_level",
    "drift_type",
    "gaps",
    "failure_cost",
    "signal_role",
    "cost_vs_benefit",
    "required_actions",
    "final_decision",
    "final_test"
  ],
  "properties": {
    "fpr_summary": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "status",
        "confidence",
        "primary_issue",
        "recommended_action"
      ],
      "properties": {
        "status": {
          "type": "string",
          "enum": [
            "Aligned",
            "Partial",
            "Misaligned"
          ]
        },
        "confidence": {
          "type": "string",
          "enum": [
            "High",
            "Medium",
            "Low"
          ]
        },
        "primary_issue": {
          "type": "string",
          "minLength": 1
        },
        "recommended_action": {
          "type": "string",
          "minLength": 1
        }
      }
    },
    "feature_system": {
      "type": "string",
      "minLength": 1
    },
    "date": {
      "type": "string",
      "format": "date-time"
    },
    "desired_purpose": {
      "type": "string",
      "minLength": 1
    },
    "stated_purpose": {
      "type": "string",
      "minLength": 1
    },
    "functional_purpose": {
      "type": "string",
      "minLength": 1
    },
    "evidence": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "type",
          "description"
        ],
        "properties": {
          "type": {
            "type": "string",
            "enum": [
              "test",
              "observable_behavior",
              "output",
              "metric",
              "reasoned_inference",
              "user_report",
              "code_inspection",
              "log_trace",
              "other"
            ]
          },
          "description": {
            "type": "string",
            "minLength": 1
          },
          "artifact": {
            "type": "string"
          },
          "confidence": {
            "type": "string",
            "enum": [
              "High",
              "Medium",
              "Low"
            ]
          }
        }
      }
    },
    "impact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "easier",
        "faster",
        "safer",
        "newly_possible"
      ],
      "properties": {
        "easier": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "faster": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "safer": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "newly_possible": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    },
    "alignment_status": {
      "type": "string",
      "enum": [
        "Fully aligned",
        "Partially aligned",
        "Misaligned"
      ]
    },
    "confidence_level": {
      "type": "string",
      "enum": [
        "High",
        "Medium",
        "Low"
      ]
    },
    "drift_type": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "enum": [
          "None",
          "Design Drift",
          "Implementation Drift",
          "False Success",
          "Mixed"
        ]
      }
    },
    "gaps": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "missing_behavior",
        "missing_signals",
        "missing_integration",
        "missing_constraints"
      ],
      "properties": {
        "missing_behavior": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "missing_signals": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "missing_integration": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "missing_constraints": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    },
    "failure_cost": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "breaks",
        "degrades",
        "propagates_to"
      ],
      "properties": {
        "breaks": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "degrades": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "propagates_to": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    },
    "signal_role": {
      "type": "string",
      "enum": [
        "Primary",
        "Secondary",
        "Fallback",
        "Not a signal"
      ]
    },
    "cost_vs_benefit": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "complexity_added",
        "benefit_gained",
        "worth_it"
      ],
      "properties": {
        "complexity_added": {
          "type": "string",
          "minLength": 1
        },
        "benefit_gained": {
          "type": "string",
          "minLength": 1
        },
        "worth_it": {
          "type": "boolean"
        }
      }
    },
    "required_actions": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "final_decision": {
      "type": "string",
      "enum": [
        "Continue",
        "Reinforce",
        "Recalibrate",
        "Combine",
        "Remove"
      ]
    },
    "final_test": {
      "type": "string",
      "minLength": 1
    },
    "notes": {
      "type": "string"
    }
  }
}