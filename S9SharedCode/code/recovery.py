"""Failure classification and recovery decisions for the orchestrator.

Two surfaces:

  - `classify_failure(error_text)` buckets a failure into one of
    {transient, validation_error, upstream_failure} so the orchestrator
    can tell apart a gateway 503 from a malformed plan from a genuine
    upstream miss (NOTES_RUNS round-2 review P0 #3).

  - `plan_recovery(...)` is the predicate the Executor consults to
    decide WHAT to do with a failure: "skip", "replan", or "critic_fail".
    Concentrating the if/elif tree here keeps `flow.Executor.run`
    focused on graph mechanics and lets the recovery policy be unit-
    tested in isolation.

The orchestrator imports `plan_recovery` and acts on the returned
`RecoveryDecision` — it does not branch on classifier output itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RecoveryReason = Literal["transient", "validation_error", "upstream_failure"]
RecoveryAction = Literal["skip", "replan", "critic_fail"]


def _critic_recovery_key(graph, target_nid: str | None) -> str:
    """Stable key for critic-fail cap — same browser upstream → same key."""
    if target_nid and target_nid in graph.g.nodes:
        for uinp in graph.g.nodes[target_nid].get("inputs") or []:
            if uinp.startswith("n:") and uinp in graph.g.nodes:
                return f"critic_branch:{uinp}"
    return target_nid or "unknown"


def classify_failure(error_text: str) -> RecoveryReason:
    e = (error_text or "").lower()
    if not e:
        return "upstream_failure"
    if "malformed" in e or "validationerror" in e or "validation error" in e:
        return "validation_error"
    transient_markers = (
        "503", "502", "504",
        "timeout", "timed out",
        "connection", "connectionerror", "httpstatuserror",
        "service unavailable", "bad gateway", "gateway timeout",
    )
    if any(m in e for m in transient_markers):
        return "transient"
    return "upstream_failure"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: RecoveryReason
    note: str
    failure_report: str | None = None  # populated when action == "replan"


def plan_recovery(
    *,
    failed_skill: str,
    error_text: str,
    failed_node_id: str,
) -> RecoveryDecision:
    """Decide what to do with a node failure that is NOT a critic-verdict
    failure. The critic-fail path is handled separately in the Executor
    because it needs access to the critic node's metadata (target, child)
    and a per-target cap that is run-scoped state — this function is the
    purely-local predicate.

    Decision table (all coverage):
      reason=transient                          → skip (gateway already retried)
      reason=validation_error                   → skip (prompt bug, not runtime)
      reason=upstream_failure, failed=planner   → skip (would loop on Planner errors)
      reason=upstream_failure, failed=other     → replan
    """
    reason = classify_failure(error_text)
    if reason == "transient":
        return RecoveryDecision(
            action="skip", reason=reason,
            note="transient gateway error; gateway retry exhausted, not re-planning",
        )
    if reason == "validation_error":
        return RecoveryDecision(
            action="skip", reason=reason,
            note="validation error (malformed NodeSpec); fix the prompt, not the run",
        )
    if failed_skill == "planner":
        return RecoveryDecision(
            action="skip", reason=reason,
            note="planner-itself failure; not re-planning a planner",
        )
    fr = (f"node={failed_node_id} skill={failed_skill} reason={reason} "
          f"error={error_text}")
    return RecoveryDecision(
        action="replan", reason=reason,
        note="upstream failure; queueing planner recovery",
        failure_report=fr,
    )


def handle_critic_verdict(nid: str, result, graph, recovered_branches: dict,
                          cap_hit: list) -> bool:
    """Critic-fail policy (P1 #5). Returns True when the caller should skip
    the normal `extend_from` (because the Critic emitted `fail` and we
    handled it by splicing a recovery Planner). False on `pass`.

    Two shapes of Critic appear in S8: auto-inserted Critics (Graph.extend_from
    inserts one whenever a `critic:true` skill has outgoing edges) which
    carry `target` + `child` in metadata, and Planner-emitted Critics
    which do not — for the latter we derive both from graph structure.
    """
    if (result.output or {}).get("verdict", "pass") != "fail":
        return False
    md = graph.g.nodes[nid].get("metadata") or {}
    target_nid = md.get("target")
    child_nid = md.get("child")
    if not target_nid:
        for inp in graph.g.nodes[nid]["inputs"]:
            if inp.startswith("n:") and inp in graph.g.nodes:
                target_nid = inp; break
    if not child_nid:
        succs = list(graph.g.successors(nid))
        child_nid = succs[0] if succs else None
    if child_nid and child_nid in graph.g.nodes:
        graph.mark(child_nid, "skipped")
    if target_nid and not recovered_branches.get(_critic_recovery_key(graph, target_nid)):
        recovered_branches[_critic_recovery_key(graph, target_nid)] = True
        rationale = (result.output or {}).get("rationale", "(no rationale)")
        fr = f"critic failed target={target_nid} child={child_nid} rationale={rationale}"
        recovery_inputs = ["USER_QUERY", target_nid]
        if target_nid in graph.g.nodes:
            for uinp in graph.g.nodes[target_nid].get("inputs") or []:
                if (uinp.startswith("n:") and uinp in graph.g.nodes
                        and graph.g.nodes[uinp].get("status") == "complete"
                        and uinp not in recovery_inputs):
                    recovery_inputs.append(uinp)
        rec_nid = graph.add_node("planner", inputs=recovery_inputs,
                                 metadata={"failure_report": fr,
                                           "recovers": target_nid,
                                           "recovery_reason": "critic_fail"})
        print(f"  ↪ critic-fail recovery: planner node {rec_nid} for {target_nid}")
    elif target_nid:
        rkey = _critic_recovery_key(graph, target_nid)
        cap_hit.append(rkey)
        print(f"  ↪ critic-fail on {target_nid} already recovered once; "
              f"CAP HIT — forcing formatter with distiller {target_nid}")
        if child_nid and child_nid in graph.g.nodes:
            if graph.g.nodes[child_nid].get("skill") == "formatter":
                graph.g.nodes[child_nid]["status"] = "pending"
                graph.g.nodes[child_nid]["inputs"] = ["USER_QUERY", target_nid]
                print(f"  ↪ unblocked formatter {child_nid} ← {target_nid}", flush=True)
    return True
