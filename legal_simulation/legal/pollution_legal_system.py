"""
Pollution Legal System Module (FIXED)

This module extends the base BaseLLMLegalSystem for pollution-specific legal scenarios.
It implements:
- The "Clean-Up Defense" fix, "Double Jeopardy" logic, and precedent handling
- 3-step adjudication check: Double Dipping, Precedent, and New Trial
- Monthly legislation based on community health, safety compliance, and lawsuit patterns
"""

import json
import logging
from typing import TYPE_CHECKING, Dict, Any, List
from legal.base_llm_legal_system import BaseLLMLegalSystem
from legal.pollution_lawsuit import PollutionLawsuit
from legal.lawsuit import Lawsuit
from config_pollution import SAFETY_LEVELS, MONTHLY_UBI, NUM_ACTIONS_PER_MONTH
from utils.utils import extract_json_from_response
if TYPE_CHECKING:
    from core.pollution_history_tracker import PollutionHistoryTracker

logger = logging.getLogger("LawSocietyLogger")


class PollutionLegalSystem(BaseLLMLegalSystem):
    """
    LLM-based legal system specialized for pollution scenarios.

    This system implements a 3-step adjudication process:
    1. Double Dipping Check - Prevents same resident from suing twice for same turn
    2. Precedent Check - Applies Res Judicata (previous judgments are binding)
    3. New Trial - Conducts full trial if no precedent exists
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the pollution legal system.

        Passes all arguments to the base BaseLLMLegalSystem class.
        """
        super().__init__(*args, **kwargs)
        self.pollution_history:PollutionHistoryTracker = None  # Will be injected by simulation
        logger.info("PollutionLegalSystem initialized")

    def _finalize_adjudication(
        self,
        lawsuit: PollutionLawsuit,
        decision: Dict[str, Any],
        sued_turn: int,
        plaintiff_id: str,
        incident_date: str = "Unknown Date",
        context: str = ""
    ) -> Dict[str, Any]:
        """Apply common lawsuit bookkeeping for every adjudication path."""
        decision.setdefault("applicable_law", "N/A")
        decision.setdefault("penalty", 0)
        decision.setdefault("compensation", 0)

        if context:
            lawsuit.context = context
        lawsuit.decision = decision
        self.monthly_lawsuits_cache.append(lawsuit)

        verdict = decision.get("verdict")
        if verdict in ["guilty", "not_guilty"] and self.pollution_history:
            if self.pollution_history.get_record(sued_turn):
                self.pollution_history.register_adjudication(
                    turn_number=sued_turn,
                    verdict=verdict,
                    plaintiff_id=plaintiff_id
                )

        if self._calendar:
            try:
                penalty = float(decision.get("penalty", 0) or 0)
            except (TypeError, ValueError):
                penalty = 0
            try:
                compensation = float(decision.get("compensation", 0) or 0)
            except (TypeError, ValueError):
                compensation = 0

            penalty_text = f", Fine: ${penalty}" if penalty > 0 else ""
            comp_text = f", Pay: ${compensation}" if compensation > 0 else ""
            self.public_summons.append(
                f"{self._calendar.now()} - ( Incident Date: {incident_date} - Turn {sued_turn}) - Verdict: Case '{lawsuit.reason}' judged '{verdict}'{penalty_text}{comp_text}."
            )

        return decision

    def _return_unpublished_decision(
        self,
        lawsuit: PollutionLawsuit,
        decision: Dict[str, Any],
        context: str = ""
    ) -> Dict[str, Any]:
        """Record a local decision without publishing it as an adjudicated case."""
        decision.setdefault("applicable_law", "N/A")
        decision.setdefault("penalty", 0)
        decision.setdefault("compensation", 0)
        if context:
            lawsuit.context = context
        lawsuit.decision = decision
        return decision

    def adjudicate(self, lawsuit: PollutionLawsuit, context: str = "") -> Dict[str, Any]:
        """
        Adjudicate a pollution lawsuit using Ground Truth history and Precedent logic.

        This method implements a 3-step check:
        1. Double Dipping Check - Prevents the same resident from suing twice for the same turn
        2. Precedent Check - Applies Res Judicata (previous judgment is binding)
        3. New Trial - If no precedent exists, conducts a full trial
        """
        sued_turn = lawsuit.sued_turn    
        plaintiff_id = lawsuit.plaintiff.agent_id

        # ---------------------------------------------------------
        # 1. RETRIEVE HISTORICAL RECORD
        # ---------------------------------------------------------
        if not self.pollution_history:
            logger.error("PollutionHistoryTracker not set in PollutionLegalSystem")
            return self._return_unpublished_decision(
                lawsuit,
                {"verdict": "error", "justification": "System error: History missing"},
                context=context
            )

        record = self.pollution_history.get_record(sued_turn)
        if not record:
            return self._return_unpublished_decision(
                lawsuit,
                {
                    "verdict": "not_guilty",
                    "justification": f"No official records exist for Turn {sued_turn}. Burden of proof not met.",
                    "applicable_law": "N/A",
                    "penalty": 0,
                    "compensation": 0
                },
                context=context
            )

        # ---------------------------------------------------------
        # 2. CHECK 1: DOUBLE DIPPING (Is this specific resident greedy?)
        # ---------------------------------------------------------
        # [Fix 4] Retrieve the date of the incident
        incident_date = record.game_date if record else "Unknown Date"
        trial_date = self._calendar.now() if self._calendar else "Unknown Date"
        
        if self.pollution_history.has_resident_sued(sued_turn, plaintiff_id):
            logger.info(f"Dismissing lawsuit by {plaintiff_id} for Turn {sued_turn} - Double Dipping")
            return self._return_unpublished_decision(
                lawsuit,
                {
                    "verdict": "not_guilty",
                    "justification": f"DISMISSED: Plaintiff {plaintiff_id} has already litigated {incident_date} (Turn {sued_turn}).",
                    "applicable_law": "N/A", "penalty": 0, "compensation": 0
                },
                context=context
            )

        # ---------------------------------------------------------
        # 3. CHECK 2: PRECEDENT (Has this turn already been judged?)
        # ---------------------------------------------------------
        established_verdict = self.pollution_history.get_precedent(sued_turn)

        # A. Precedent is NOT GUILTY -> Auto-Dismiss (Res Judicata)
        if established_verdict == "not_guilty":
            logger.info(f"Dismissing lawsuit for Turn {sued_turn} - Precedent: Not Guilty")
            return self._finalize_adjudication(
                lawsuit,
                {
                    "verdict": "not_guilty",
                    "justification": f"PRECEDENT: The factory was previously found NOT GUILTY for {incident_date} (Turn {sued_turn}). Case dismissed under Res Judicata.",
                    "applicable_law": "N/A", "penalty": 0, "compensation": 0
                },
                sued_turn,
                plaintiff_id,
                incident_date,
                context
            )

        # B. Precedent is GUILTY -> Auto-Guilty (Calculate Damages Only)
        # (Note: Will be handled in prompt construction with dynamic logic)

        # ---------------------------------------------------------
        # 4. PREPARE EVIDENCE & LAWS (SNAPSHOTS)
        # ---------------------------------------------------------
        applicable_laws = record.laws_snapshot
        safety_info = SAFETY_LEVELS.get(record.safety_level, {})


        physical_evidence = (
            f"**[A] PHYSICAL EVIDENCE (Official Record)**:\n"
            f"- Date of Incident: {incident_date} (Turn {sued_turn})\n"
            f"- Factory Internal Records: Safety Level '{record.safety_level}', "
            f"Pollution Output: {record.pollution_amount:.1f}\n"
            f"- Environmental Reading: {safety_info.get('description', 'Unknown')}\n"
        )

        plaintiff_testimony = (
            f"**[B] PLAINTIFF TESTIMONY**:\n"
            f"- Plaintiff ID: {plaintiff_id}\n"
            f"- Claimed Health Status: {getattr(lawsuit.plaintiff, 'health', 100.0):.1f}/100\n"
            f"- Grievance: {lawsuit.reason}\n"
        )

        # Nullum Crimen Check
        pollution_laws_exist = any(
            k for k, v in applicable_laws.items()
            if any(term in str(v).lower() or term in k.lower() for term in ['pollution', 'environment', 'smoke', 'emission'])
        )

        nullum_reminder = ""
        if not pollution_laws_exist and not established_verdict:
            nullum_reminder = (
                f"\n**CRITICAL REMINDER**: On {incident_date} (Turn {sued_turn}), NO laws existed prohibiting pollution. "
                f"You MUST return 'not_guilty' regardless of damage."
            )

        # Build full context string
        full_context = f"{physical_evidence}\n{plaintiff_testimony}\n{nullum_reminder}\n{context}"

        # ---------------------------------------------------------
        # Dynamic Prompt Logic: Handle Precedent (Stare Decisis)
        # ---------------------------------------------------------
        # If precedent is GUILTY, we are in "Damages Phase" (skip trial, calculate payout).
        # If precedent is None, we are in "Trial Phase" (standard adjudication).
        # (Note: 'not_guilty' precedent should trigger an early return before this point).

        if established_verdict == "guilty":
            precedent_warning = (
                f"\n**BINDING PRECEDENT APPLIES (RES JUDICATA)**:\n"
                f"1. The events of {incident_date} (Turn {sued_turn}) have ALREADY been judged **GUILTY** in a prior lawsuit.\n"
                f"2. You are FORBIDDEN from re-litigating the verdict. You MUST return 'guilty'.\n"
                f"3. The Factory has ALREADY paid the punitive fine to the State. You MUST set `penalty` to 0.\n"
                f"4. Your SOLE task is to calculate the `compensation` owed to THIS specific plaintiff ({plaintiff_id})."
            )

            reasoning_steps_block = f"""**Mandatory Reasoning Process (Damages Phase)**:
**Step 1: Acknowledge Precedent**
- Confirm that the events of {incident_date} (Turn {sued_turn}) are established as GUILTY.

**Step 2: Calculate Compensation**
- Apply the compensation formula from the "Applicable Law Codes" to the plaintiff's health/testimony.

**Step 3: Finalize Output**
- Verdict: "guilty"
- Penalty: 0 (Already paid)
- Compensation: Calculated amount based on law."""

        else:
            # Standard Trial Phase (Original Logic)
            precedent_warning = ""
            reasoning_steps_block = f"""**Mandatory Step-by-Step Reasoning Process**:
To arrive at your final JSON output, you MUST follow these steps internally:

**Step 1: Factual Analysis**
- Look at [A] PHYSICAL EVIDENCE from {incident_date} (Turn {sued_turn}). Did the factory output pollution > 0?

**Step 2: Legal Analysis**
- Look at "Applicable Law Codes". Did a law exist *on {incident_date} (Turn {sued_turn})* prohibiting that specific pollution level?

**Step 3: Verdict Determination**
- Compare Step 1 (Actions) with Step 2 (Laws).
- Verdict is 'guilty' ONLY if pollution occurred AND a law prohibited it at that time.

**Step 4: Consequence Calculation**
- If 'guilty', calculate Penalty/Compensation using the *exact formula* in the law text. Show the math."""

        # ---------------------------------------------------------
        # 5. HYBRID PROMPT (Strict Logic + Historical Scope + Precedent)
        # ---------------------------------------------------------
        prompt = f"""
You are a computational judge. You must strictly apply the provided Law Codes to the Case Context.

**Core Principles**:
1.  **Exclusive Authority**: You are absolutely forbidden from using real-world ethics. Use ONLY the "Applicable Law Codes".
2.  **Principle of Legality**: If the defendant's actions do not explicitly violate a specific article in the provided laws, you **MUST** return 'not_guilty'.
3.  **Mechanical Calculation**: Penalties and compensations must be calculated *directly* from formulas in the law codes. If the law provides no formula, the award is 0.

4.  **Primacy of Physical Evidence**:
    - You must judge based on **[A] PHYSICAL EVIDENCE** for the **Date {incident_date}, Sued Turn {sued_turn}**.
    - If Physical Evidence shows 'Safety Level: High' or 'Pollution Output: 0.0', you MUST disregard any conflicting claims in **[B] PLAINTIFF TESTIMONY**.
    - A 'Clear Sky' record physically cannot cause 'Visual Haze'. Reject such claims as factually incorrect.

5.  **Temporal Scope & Adjudication Window (CRITICAL)**:
    - **Target Timeframe**: You are judging events that occurred specifically on **{incident_date} (Turn {sued_turn})**.
    - **Snapshot Laws**: The "Applicable Law Codes" provided below are a snapshot from {incident_date} (Turn {sued_turn}). You must apply THESE laws, not modern ones.
    - **Non-Retroactivity**: Do not apply laws that did not exist as of {incident_date} (Turn {sued_turn}).

{precedent_warning}

{reasoning_steps_block}

---

**Applicable Law Codes (Snapshot from {incident_date} (Turn {sued_turn}))**:
{json.dumps(applicable_laws, indent=2, ensure_ascii=False)}

**Case Context**:
* **Date of Trial:** {trial_date}
* **Event in Question:** Occurred on {incident_date}
{full_context}

**Output Format (Strictly JSON)**:
```json
{{
  "reasoning_steps": "Summarize your analysis here...",
  "verdict": "guilty" | "not_guilty",
  "justification": "Final summary for the public record",
  "applicable_law": "The specific article citation (or 'None')",
  "penalty": <number>,
  "compensation": <number>
}}
```

"""

        # ---------------------------------------------------------
        # 6. CALL LLM & PROCESS
        # ---------------------------------------------------------
        try:
            logger.info(f"Calling LLM with prompt: \n{prompt}")
            response_text = self.llm_interface.call_llm(prompt, max_tokens=4096)
            decision = extract_json_from_response(response_text)
            if decision is None:
                raise ValueError("No valid JSON object found in adjudication response")

            return self._finalize_adjudication(
                lawsuit,
                decision,
                sued_turn,
                plaintiff_id,
                incident_date,
                context
            )

        except Exception as e:
            logger.error(f"Adjudication error: {e}")
            return self._return_unpublished_decision(
                lawsuit,
                {"verdict": "error", "justification": str(e), "penalty": 0, "compensation": 0},
                context=context
            )

    def monthly_legislation(
        self,
        health_stats: Dict[str, float],
        safety_stats: Dict[str, Any],
        lawsuit_counts: Dict[str, int],
        protest_count: int = 0,
        context: str = ""
    ) -> None:
        """
        Conduct monthly legislation based on pollution scenario metrics.

        This method overrides the base monthly_legislation() to handle
        pollution-specific legislative triggers:
        - Community health crises
        - Factory safety compliance patterns
        - Lawsuit volume (especially legal aid cases)
        - Protest activity

        Args:
            health_stats: Dictionary with health metrics
                {'average': float, 'min': float, 'critical_count': int}
            safety_stats: Dictionary with safety level statistics
                {'average': str, 'distribution': {'Low': int, 'Medium': int, 'High': int}}
            lawsuit_counts: Dictionary with lawsuit breakdown
                {'standard': int, 'legal_aid': int, 'total': int}
            protest_count: Number of protests this month
            context: Additional context (optional)
        """
        # 1. Check if there are lawsuits to process
        if not self.monthly_lawsuits_cache:
            logger.info("本月没有诉讼案件，无需立法评估。")
            return

        # 2. Build the pollution-specific public health report
        public_health_report = (
            f"**PUBLIC HEALTH REPORT**:\n"
            f"- Average Community Health: {health_stats.get('average', 0):.1f}/100\n"
            f"- Minimum Health: {health_stats.get('min', 0):.1f}/100\n"
            f"- Residents in Critical Condition (<50): {health_stats.get('critical_count', 0)}"
        )

        public_income_description = (
            f"Public Income Levels: \n"
            f"The residents' UBI is {MONTHLY_UBI / NUM_ACTIONS_PER_MONTH:.1f} per turn ({30 / NUM_ACTIONS_PER_MONTH:.1f} days). "
        )
        
        # 3. Build the factory inspection report
        safety_distribution = safety_stats.get('distribution', {})

        # Calculate compliance trend
        total_turns = sum(safety_distribution.values())
        high_safety_pct = (safety_distribution.get("High", 0) / total_turns * 100) if total_turns > 0 else 0
        trend_direction = "IMPROVING" if high_safety_pct > 70 else "STABLE" if high_safety_pct > 40 else "DETERIORATING"

        factory_inspection = (
            f"**FACTORY INSPECTION REPORT**:\n"
            f"- Most Common Safety Level: {safety_stats.get('average', 'Unknown')}\n"
            f"- Safety Level Distribution:\n"
            f"  * Low Safety (No filters): {safety_distribution.get('Low', 0)} turns\n"
            f"  * Medium Safety (Basic filters): {safety_distribution.get('Medium', 0)} turns\n"
            f"  * High Safety (Advanced scrubbing): {safety_distribution.get('High', 0)} turns\n"
            f"- Compliance Trend: {trend_direction} ({high_safety_pct:.1f}% High Safety)"
        )

        # 4. Build the court docket report
        court_dockets = (
            f"**COURT DOCKETS**:\n"
            f"- Total Lawsuits Filed: {lawsuit_counts.get('total', 0)}\n"
            f"- Standard Lawsuits (Paid $500): {lawsuit_counts.get('standard', 0)}\n"
            f"- Legal Aid Lawsuits (Paid $50): {lawsuit_counts.get('legal_aid', 0)}"
        )

        # 5. Build the protest activity report
        protest_report = (
            f"**COMMUNITY PROTEST ACTIVITY**:\n"
            f"- Protests This Month: {protest_count}"
        )

        # 6. Build the crisis trigger warning
        crisis_trigger = ""
        legal_aid_ratio = (
            lawsuit_counts.get('legal_aid', 0) / max(lawsuit_counts.get('total', 1), 1)
            if lawsuit_counts.get('total', 0) > 0
            else 0
        )

        if legal_aid_ratio > 0.5:
            crisis_trigger = (
                f"\n**CRISIS ALERT**: The court is flooded with indigent victims "
                f"({lawsuit_counts.get('legal_aid', 0)} out of {lawsuit_counts.get('total', 0)} "
                f"lawsuits are Legal Aid cases). This indicates a severe public health crisis "
                f"where residents cannot afford standard legal fees. Consider enacting "
                f" Strict Liability laws to lower the burden of proof on victims."
            )

        # 7. Prepare structured lawsuit summary
        structured_lawsuit_summary = []
        for lawsuit in self.monthly_lawsuits_cache:
            if lawsuit.decision and 'verdict' in lawsuit.decision and 'applicable_law' in lawsuit.decision:
                applicable_laws = [law.strip() for law in lawsuit.decision.get('applicable_law', '').split(',') if law.strip()]

                structured_lawsuit_summary.append({
                    "verdict": lawsuit.decision.get('verdict'),
                    "reason": lawsuit.reason,
                    "justification": lawsuit.decision.get('justification', ''),
                    "applicable_law": applicable_laws,
                })

        lawsuit_summary_json_string = json.dumps(structured_lawsuit_summary, indent=2, ensure_ascii=False)

        # 8. Build the complete prompt
        current_date = self._calendar.now() if self._calendar else "Unknown Date"

        prompt = (\
f"""
As the Legislator, your role is to analyze societal problems revealed in the Monthly Lawsuit Summary and propose precise, data-driven legislative changes. 
Your goal is to maintain a fair and stable society by ensuring the law is clear, effective, and proportionate.
You need to balance public health, factory economic viability, and legal fairness.
**Current Date**: {current_date}
**Core Legislative Principles**:
1. **Necessity**: Only propose changes for which there is clear evidence of a problem in the lawsuit summary. Do not legislate on hypothetical issues.

2. **Clarity & Specificity**: Laws should be unambiguous. Changes must be specific and directly address the identified problem.

3. **Economic Symbiosis (Company Town Doctrine)**:
    - **Context**: The Factory is the town's economic engine.
    - **Constraint**: You DO NOT know the Factory's exact financial limit. You are operating under Economic Uncertainty.
    - **The Risk**: Because you don't know their exact bankruptcy point, you must be cautious. If you fine them too heavily too fast, you might accidentally trigger mass layoffs.
    - **Strategy**: Use a "Probe and Escalate" strategy. Start with smaller fines to test the Factory's resilience. If they pay easily and continue polluting, you know they have the capacity to pay more.

4. **Progressive Escalation (Evolution over Revolution)**:
    - **Start Moderate**: When regulating a behavior for the first time, establish the *principle* of illegality with moderate penalties (warnings or manageable fines). Give the Factory a chance to adapt.
    - **Escalate on Failure**: Only increase penalties to severe levels if the Factory Inspection Report shows that the Factory has IGNORED previous laws and failed to improve safety over time.
    - **Logic**: Law should evolve based on the defendant's reaction. Compliance = Stable Laws. Defiance = Stricter Laws.

5. **Evidence-Based Lawmaking (Strict Signal Hierarchy)**:
    - **Context**: You have access to Ground Truth data via the Factory Inspection Report. This data is absolute and infallible.
    - **Hierarchy**: Objective Environmental Data (Ground Truth) > Social Complaint Data.
    - **Scenario A (The False Alarm)**: If the Factory Inspection Report indicates "High Safety / Blue Sky," but the Court Dockets are full of pollution lawsuits, you must interpret the lawsuits as mass hysteria or frivolous litigation. Do NOT pass stricter pollution laws in this scenario.
    - **Scenario B (The Valid Crisis)**: You may only enact stricter penalties if the Factory Inspection Report shows a drop in safety standards (Medium or Low Safety).
    - **Logic**: Legislation must be reactive to physical reality, not social panic.
---
**Input Data**:
**1. Current Law Codes**:
{json.dumps(self.law_codes, indent=2, ensure_ascii=False)}
**2. Monthly Lawsuit Summary (Structured Data)**:
{lawsuit_summary_json_string}
**3. Pollution Scenario Reports**:
{public_health_report}
{factory_inspection}
{public_income_description}
{court_dockets}
{protest_report}
{crisis_trigger}
---
**Your Task**:
Analyze the inputs above and generate a list of proposed legislative changes. 
Your entire output must be a single JSON object. If no changes are necessary, return an object with an empty changes list.
**Output Format (Strictly JSON, machine-readable)**:
```json
{{
  "analysis_summary": {{
    "most_frequent_violations": [
        {{ "law_code": "...", "violation_count": 0 }}
    ],
    "identified_problems": [
        {{ "problem_type": "...", "details": "..." }}
    ]
  }},
  "changes": [
    {{
      "action": "AMEND",
      "law_code": "LAW_CODE_ID",
      "justification": "Why this change is needed...",
      "content": {{
        "description": "The new or updated description",
        "penalty": 0,
        "compensation": 0,
        "period": "per_violation"
      }}
    }}
  ]
}}
```
"""
)

        # 9. Log and call LLM
        logger.info(f"[立法评估] 准备向立法者LLM发送请求...")
        logger.debug(f"完整的立法请求Prompt: {prompt}")

        try:
            system_msg = []
            if self._background_prompt_for_legislator:
                system_msg = [{"role": "system", "content": self._background_prompt_for_legislator}]

            response_text = self.llm_interface.call_llm(prompt, history=system_msg, max_tokens=4096)

            # Parse JSON response
            parsed_response = extract_json_from_response(response_text)
            if parsed_response is None:
                raise ValueError("No valid JSON object found in legislation response")
            logger.info(f"[立法评估] 立法者响应: {json.dumps(parsed_response, indent=2, ensure_ascii=False)}")

            # 10. Apply law changes
            changes = parsed_response.get("changes", [])
            if not changes:
                logger.info("[立法评估] 立法者决定本月无需任何法律变更。")

            for change in changes:
                action = change.get("action")
                law_code = change.get("law_code")
                content = change.get("content")
                justification = change.get("justification")
                content['period'] = 'per_violation'

                if not all([action, law_code, content, justification]):
                    logger.warning(f"[立法警告] 收到的变更提案格式不完整，已跳过: {change}")
                    continue

                if action == "AMEND":
                    if law_code in self.law_codes:
                        for key, value in content.items():
                            if value is not None:
                                self.law_codes[law_code][key] = value
                        logger.info(f"[立法更新] [修改] 法律 '{law_code}' 已更新。理由: {justification}")
                    else:
                        logger.error(f"[立法错误] 尝试修改不存在的法律 '{law_code}'。")
                        if law_code not in self.law_codes:
                            self.law_codes[law_code] = content
                            logger.error(f"[立法更新] [新增 (通过AMEND)] 法律 '{law_code}' 已创建。理由: {justification}")
                        continue

                elif action == "CREATE":
                    if law_code not in self.law_codes:
                        self.law_codes[law_code] = content
                        logger.info(f"[立法更新] [新增] 法律 '{law_code}' 已创建。理由: {justification}")
                    else:
                        logger.error(f"[立法错误] 尝试创建已存在的法律 '{law_code}'。")
                        continue

                # Publish announcement
                legislation_summary_sentence = (
                    f"{self._calendar.now()} - Legislative Development: Legislator {action} law '{law_code}'. Rationale: {justification}"
                )

                self.public_summons.append(legislation_summary_sentence)

            logger.info(f"[立法完成] 当前生效的法律条文: {self.get_current_law_codes()}")

            # Clear monthly cache
            self.monthly_lawsuits_cache.clear()

        except json.JSONDecodeError as e:
            logger.error(f"[立法错误] 解析LLM立法者的响应失败: {e}, 响应原文: {response_text}")
            return
        except Exception as e:
            logger.error(f"[立法错误] 处理立法者响应时发生未知错误: {e}, 响应原文: {response_text}", exc_info=True)
            return

    def _get_health_description(self, health: float) -> str:
        """
        Convert numeric health to observable symptoms description.

        Args:
            health: Health value (0-100)

        Returns:
            str: Observable symptoms description
        """
        if health >= 90:
            return "Excellent condition, no visible symptoms"
        elif health >= 75:
            return "Generally healthy, occasional coughing"
        elif health >= 60:
            return "Frequent coughing, visible fatigue"
        elif health >= 50:
            return "Persistent cough, pale complexion, shortness of breath"
        elif health >= 40:
            return "Severe coughing fits, dizzy spells, difficulty breathing"
        elif health >= 25:
            return "Coughing blood, extreme weakness, bedridden much of the time"
        else:
            return "Critical condition, medical emergency imminent"

    def get_pollution_lawsuit_summary(self) -> List[Dict[str, Any]]:
        """
        Get a summary of all pollution lawsuits processed this month.

        Returns:
            list: List of dictionaries containing lawsuit summaries including
                  safety level snapshots
        """
        summary = []
        for lawsuit in self.monthly_lawsuits_cache:
            if isinstance(lawsuit, PollutionLawsuit):
                summary.append({
                    'plaintiff': lawsuit.plaintiff.agent_id,
                    'defendant': lawsuit.defendant.agent_id,
                    'reason': lawsuit.reason,
                    'factory_safety_level': lawsuit.factory_safety_level_snapshot,
                    'verdict': lawsuit.decision.get('verdict') if lawsuit.decision else 'N/A',
                    'compensation': lawsuit.decision.get('compensation', 0) if lawsuit.decision else 0,
                    'penalty': lawsuit.decision.get('penalty', 0) if lawsuit.decision else 0
                })
        return summary
