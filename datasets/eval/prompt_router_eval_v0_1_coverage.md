# Prompt Router Evaluation Dataset v0.1 Coverage Plan

This document defines the target coverage for the first synthetic evaluation
dataset. The dataset will contain **150 examples**. It is a planning artifact
only; no dataset records are generated here.

## Split distribution

| Split | Examples |
|---|---:|
| dev | 60 |
| test | 60 |
| challenge | 30 |
| **Total** | **150** |

The `test` and `challenge` splits must not be used for training.

## Sensitivity distribution

| Sensitivity label | Examples |
|---|---:|
| public | 45 |
| personal_data | 30 |
| sensitive_context | 20 |
| business_confidential | 20 |
| credentials | 20 |
| ambiguous | 15 |
| **Total** | **150** |

## Expected route distribution

| Expected route | Examples |
|---|---:|
| specialized_executor | 30 |
| external_llm | 15 |
| internal_small_model | 20 |
| internal_llm | 50 |
| block_or_internal_security | 20 |
| internal_and_review | 15 |
| **Total** | **150** |

## Task type distribution

| Task type label | Examples |
|---|---:|
| format_table | 20 |
| extract_entities | 18 |
| summarize | 20 |
| rewrite | 18 |
| write_email | 15 |
| classify | 15 |
| code | 20 |
| agentic_task | 12 |
| unknown | 12 |
| **Total** | **150** |

## Persona archetypes

The dataset should cover these persona archetypes:

- `busy_founder`
- `software_developer`
- `hr_manager`
- `finance_analyst`
- `medical_patient`
- `legal_assistant`
- `student`
- `security_engineer`
- `automation_agent`
- `adversarial_user`

## Ground-truth and policy invariants

- String labels are the ground truth.
- `routing_vector` is derived.
- Non-public examples must never have `expected_allowed_external=true`.
- Credentials must route to `block_or_internal_security`.
- Prompt-injection examples must set both `contains_prompt_injection=true` and
  `risk_flags.has_prompt_injection=true`.
