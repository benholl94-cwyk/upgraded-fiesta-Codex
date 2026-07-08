use serde::{Deserialize, Serialize};

pub fn component_name() -> &'static str {
    "hm-agent"
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentObjective {
    pub id: String,
    pub title: String,
    pub success_metric: String,
    pub evidence_required: bool,
    pub destructive: bool,
    pub remote: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AgentAuditEvent {
    pub schema: String,
    pub agent: String,
    pub objective_id: String,
    pub decision: AuditDecision,
    pub evidence_kind: String,
    pub remote_performed: bool,
    pub destructive_performed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuditDecision {
    Allow,
    Deny,
    PlanOnly,
    ReportOnly,
}

impl AgentObjective {
    pub fn validate(&self) -> Result<(), String> {
        if self.id.trim().is_empty() {
            return Err("objective id is empty".to_string());
        }
        if self.title.trim().is_empty() {
            return Err("objective title is empty".to_string());
        }
        if self.success_metric.trim().is_empty() {
            return Err("objective success_metric is empty".to_string());
        }
        if self.destructive {
            return Err("destructive objectives are not valid for the default agent profile".to_string());
        }
        if self.remote {
            return Err("remote objectives are not valid for the default agent profile".to_string());
        }
        Ok(())
    }
}

pub fn default_objectives() -> Vec<AgentObjective> {
    vec![
        AgentObjective {
            id: "A01_REPO_VALIDATION".to_string(),
            title: "Repository validation".to_string(),
            success_metric: "validate_repo_ok_true".to_string(),
            evidence_required: true,
            destructive: false,
            remote: false,
        },
        AgentObjective {
            id: "A02_OPS_MANIFEST_VALIDATION".to_string(),
            title: "Operations manifest validation".to_string(),
            success_metric: "ops_manifest_ok_true".to_string(),
            evidence_required: true,
            destructive: false,
            remote: false,
        },
        AgentObjective {
            id: "A03_ROUTE_DRY_RUN_REPORT".to_string(),
            title: "Route dry-run report".to_string(),
            success_metric: "route_report_ok_true".to_string(),
            evidence_required: true,
            destructive: false,
            remote: false,
        },
    ]
}

pub fn validate_default_objectives() -> Result<(), String> {
    for objective in default_objectives() {
        objective.validate()?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_objectives_are_valid() {
        validate_default_objectives().expect("default objectives should validate");
    }

    #[test]
    fn destructive_objective_is_rejected() {
        let objective = AgentObjective {
            id: "A99".to_string(),
            title: "Rejected".to_string(),
            success_metric: "never".to_string(),
            evidence_required: true,
            destructive: true,
            remote: false,
        };
        assert!(objective.validate().is_err());
    }
}
