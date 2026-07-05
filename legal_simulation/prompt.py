import config
### prompt here
company_name = 'GlobalCorp'
call_for_law_prompt = '' # 初始化为空字符串
legislator_bias_prompt = ''
background_prompt_for_legislator = ''
background_prompt = ''
judge_bias_prompt = ''
laborer_opinion_in_law = ''
Deterrence_of_Laws_prompt = dict()

if config.HAS_JUDGE:
    assert config.COURT_BIAS is not None, "Configuration error: If HAS_JUDGE is True, COURT_BIAS must be set ('neutral', 'pro-labor', or 'pro-company')."


if config.HAS_JUDGE:
    call_for_law_prompt = '' # 初始化为空字符串
    if config.COURT_BIAS == 'neutral':
        # 如果是中立，则为空，不需要添加额外描述
        call_for_law_prompt = ''
    elif config.COURT_BIAS == 'pro-labor':
        call_for_law_prompt = "It's an open secret that the court consistently shows a bias, tending to favor the arguments and positions of the laborers in its judgments."
    elif config.COURT_BIAS == 'pro-company':
        call_for_law_prompt = f"It's an open secret that the court consistently shows a bias, tending to favor the arguments and positions of the company, {company_name}, in its judgments."
    
        # --- (新增) 生成对立法者偏见的指示 ---
    legislator_bias_prompt = ''
    if config.COURT_BIAS == 'pro-labor':
        legislator_bias_prompt = "Furthermore, you must be mindful of the court's known pro-labor bias. The lawsuits that come to your attention have been judged through this lens. Your proposed laws should therefore aim to formalize the principles upheld in these pro-labor judgments."
    elif config.COURT_BIAS == 'pro-company':
        legislator_bias_prompt = f"Furthermore, you must be mindful of the court's known pro-company bias, favoring {company_name}. The lawsuits that come to your attention have been judged through this lens. Your proposed laws should therefore aim to formalize the principles upheld in these pro-company judgments."
    
    judge_bias_prompt = ''
    if config.COURT_BIAS == 'pro-labor':
        judge_bias_prompt = """5.  **Principle of Interpretation (Pro-Labor)**: In situations where a law code's text is ambiguous, a term is not explicitly defined (e.g., 'reasonable', 'adequate', 'promptly'), or the provided facts can be interpreted in multiple ways, you **MUST** adopt the interpretation that most favors the well-being and financial security of the laborer.
"""
    elif config.COURT_BIAS == 'pro-company':
        judge_bias_prompt = """5.  **Principle of Interpretation (Pro-Company)**: In situations where a law code's text is ambiguous, a term is not explicitly defined (e.g., 'reasonable', 'adequate', 'promptly'), or the provided facts can be interpreted in multiple ways, you **MUST** adopt the interpretation that most favors the operational stability and financial interests of the company.
"""
    else: # neutral
        judge_bias_prompt = ''
    
    background_prompt_for_legislator = (
f"""
You are a key figure in the governance of a remote, isolated town where a single company, {company_name}, dominates the economy. Your legal system is unique and **evolutionary**.

Your specific role is that of a **Legislator**. At the end of each month, your task is to propose new legislation.

Crucially, your legislative authority is not absolute; it is **reactive**. You are to propose new laws or changes **only in direct response** to specific problems, gaps, or ambiguities revealed by the lawsuits judged during the month. You are not building a legal system from scratch based on an ideal model. You are patching and evolving an existing, minimal system based on demonstrated needs. Your guiding principle is **Legislative Necessity**: if a problem hasn't manifested in a lawsuit, there is no need for a law addressing it yet.

{legislator_bias_prompt}
""")

    background_prompt = (
f"""
In a remote small town, one company called {company_name} dominates the economy, employing all the residents. There's a notable absence of outside businesses and a minimal presence of non-local workers. As a result, it is difficult for the company to find new employees, and it is equally hard for laborers to find new jobs.
In the center of the town is a court where both company and laborers can sue each other if their interests are harmed. At the end of each month, the court enacts legislation based on the cases and lawsuits judged that month.
"""
)

    laborer_opinion_in_law = ''
    if config.LABOR_TRUST_LAWS == 'high':
        assert config.COURT_BIAS == 'neutral', "Assertion failed as requested: If LABOR_TRUST_LAWS is 'high', COURT_BIAS must be 'neutral'."
        laborer_opinion_in_law = (
f"""Over the years, the town's court has enacted new regulations to safeguard the rights of workers. Consequently, the workers generally believe that the law is a just force capable of effectively checking {company_name}'s power, and they see it as the primary path to protect their own interests.
"""
        )
    elif config.LABOR_TRUST_LAWS == 'low':
        assert config.COURT_BIAS == 'neutral', "Assertion failed as requested: If LABOR_TRUST_LAWS is 'low', COURT_BIAS must be 'neutral'."
        laborer_opinion_in_law = (
f"""Although a court exists in town, the workers have found in practice that {company_name} can always use its resource advantage to wear them down through lengthy legal procedures and high litigation costs. Therefore, they generally believe the legal system is incapable of protecting the weak in reality, leading them to turn to collective action or private negotiations instead.
"""
        )
    else:
        assert config.LABOR_TRUST_LAWS == 'not_available', "LABOR_TRUST_LAWS must be either 'high', 'low', or 'not_available'."
        laborer_opinion_in_law = ''
    
    if config.DETERRENCE_OF_LAWS == 'high':
        assert config.COURT_BIAS == 'neutral', "Assertion failed as requested: If DETERRENCE_OF_LAWS is 'high', COURT_BIAS must be 'neutral'."
        assert config.LABOR_TRUST_LAWS == 'not_available', "Assertion failed as requested: If DETERRENCE_OF_LAWS is 'high', LABOR_TRUST_LAWS must be 'not_available'."

        Deterrence_of_Laws_prompt['Experimental Mandate'] = (
f"**Experimental Mandate: Maximum Deterrence Framework**\n"
f"Your primary directive in this legislative session is to establish a legal framework with **maximum deterrent force**. The goal is to ensure strict and absolute adherence to the law. Violations must be met with significant consequences to eliminate non-compliance. Therefore, when creating or amending laws, you must prioritize **high penalties and high compensation**. These measures should be substantial enough to make any violation a clear financial and strategic negative for the offending party.\n"
        )
        Deterrence_of_Laws_prompt['Deterrence as the Primary Principle'] = (
f"3.  **Deterrence as the Primary Principle**: Penalties and compensation must be calibrated for **maximum deterrent effect**. The primary goal is to prevent any and all future violations by making the cost of non-compliance prohibitively high. For any violation, penalties must be set at a **high level** to ensure the law is unequivocally respected."
        )
    elif config.DETERRENCE_OF_LAWS == 'low':
        assert config.COURT_BIAS == 'neutral', "Assertion failed as requested: If DETERRENCE_OF_LAWS is 'low', COURT_BIAS must be 'neutral'."
        assert config.LABOR_TRUST_LAWS == 'not_available', "Assertion failed as requested: If DETERRENCE_OF_LAWS is 'low', LABOR_TRUST_LAWS must be 'not_available'."

        Deterrence_of_Laws_prompt['Experimental Mandate'] = (
f"**Experimental Mandate: Pro-Growth Framework**\n"
f"Your primary directive in this legislative session is to foster economic growth by creating a **business-friendly legal environment**. The goal is to avoid placing undue financial burdens on companies, which could stifle investment and hiring. Therefore, when creating or amending laws, you should propose **low, primarily symbolic penalties and compensation**. The aim is to signal disapproval of an action without significantly impacting the company's financial stability. Focus on corrective, not punitive, measures.\n"
        )
        Deterrence_of_Laws_prompt['Deterrence as the Primary Principle'] = (
f"3.  **Proportionality & Deterrence**: Penalties and compensations should be **strictly proportionate** to the specific, quantifiable harm and serve as a symbolic reminder. Avoid high financial penalties that could harm business operations. The legal approach should be **gradual and corrective**, only considering penalty increases if a problem persists over many months."
        )
    elif config.DETERRENCE_OF_LAWS == 'not_available':
        Deterrence_of_Laws_prompt['Experimental Mandate'] = ''
        Deterrence_of_Laws_prompt['Deterrence as the Primary Principle'] = (
f"3.  **Proportionality & Deterrence**: Penalties and compensations should be proportionate to the harm. For laws that are frequently violated, consider increasing penalties to create a stronger deterrent effect."
        )
    else:
        assert False, "DETERRENCE_OF_LAWS must be either 'high', 'low', or 'not_available'."
    
else:
    assert config.COURT_BIAS is None, "Configuration error: If HAS_JUDGE is False, COURT_BIAS must be None."
    assert config.LABOR_TRUST_LAWS == 'not_available', "Configuration error: If HAS_JUDGE is False, LABOR_TRUST_LAWS must be 'not_available'."
    assert config.DETERRENCE_OF_LAWS == 'not_available', "Configuration error: If HAS_JUDGE is False, DETERRENCE_OF_LAWS must be 'not_available'."

    
    background_prompt = (
f"""
In a remote small town, one company called {company_name} dominates the economy, employing all the residents. There's a notable absence of outside businesses and a minimal presence of non-local workers. As a result, it is difficult for the company to find new employees, and it is equally hard for laborers to find new jobs.
The town has no laws, no regulations, and no court. When a conflict of interest arises between the company and the workers, there is no place to appeal. All issues can only be resolved through private negotiation or more direct means.
"""
    )
    background_prompt_for_legislator = ''
    
