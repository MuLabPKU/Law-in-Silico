"""
微观和宏观模拟的桥梁 - 将微观模拟的场景和法律系统导出给宏观模拟使用
"""
import json
from typing import Dict, Any, List, Optional
from pathlib import Path


class MicroMacroBridge:
    """连接微观和宏观模拟的桥梁类"""
    
    @staticmethod
    def export_micro_simulation(micro_sim,
                                output_path: str,
                                include_scenario: bool = True,
                                include_laws: bool = True,
                                include_profile_distribution: bool = True) -> Dict[str, Any]:
        """
        从微观模拟导出数据供宏观模拟使用
        
        Args:
            micro_sim: 微观模拟实例（Simulation对象）
            output_path: 输出文件路径
            include_scenario: 是否包含场景信息
            include_laws: 是否包含法律系统
            include_profile_distribution: 是否包含profile分布
        
        Returns:
            导出的数据字典
        """
        export_data = {}
        
        # 1. 导出场景信息
        if include_scenario:
            export_data['scenario'] = {
                'background': micro_sim.private_context_variable.get('background_prompt', ''),
                'company_name': micro_sim.company.agent_id,
                'setting_description': 'Labor-management conflict simulation in a company town'
            }
        
        # 2. 导出法律系统
        if include_laws and hasattr(micro_sim, 'legal_system'):
            legal_system = micro_sim.legal_system
            export_data['legal_system'] = {
                'current_law_codes': legal_system.get_current_law_codes() if hasattr(legal_system, 'get_current_law_codes') else str(legal_system.law_codes),
                'law_codes_dict': legal_system.law_codes if hasattr(legal_system, 'law_codes') else {},
                'public_summons': legal_system.public_summons if hasattr(legal_system, 'public_summons') else []
            }
        
        # 3. 导出profile分布（从微观模拟的劳工profile）
        if include_profile_distribution:
            profile_distribution = {}
            for laborer in micro_sim.laborers.values():
                profile = laborer.get_profile() if hasattr(laborer, 'get_profile') else {}
                # 统计各属性的分布
                for key, value in profile.items():
                    if key not in profile_distribution:
                        profile_distribution[key] = {}
                    if isinstance(value, (str, int, float, bool)):
                        if value not in profile_distribution[key]:
                            profile_distribution[key][value] = 0
                        profile_distribution[key][value] += 1
            
            # 转换为概率分布
            total_laborers = len(micro_sim.laborers)
            for key in profile_distribution:
                for value in profile_distribution[key]:
                    profile_distribution[key][value] = profile_distribution[key][value] / total_laborers
            
            export_data['profile_distribution'] = profile_distribution
        
        # 4. 导出其他元数据
        export_data['metadata'] = {
            'simulation_type': 'micro',
            'num_laborers': len(micro_sim.laborers),
            'company_name': micro_sim.company.agent_id
        }
        
        # 保存到文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return export_data
    
    @staticmethod
    def create_macro_scene_from_micro(micro_export_path: str, 
                                      scene_type: str = "labor_dispute",
                                      output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        从微观模拟导出数据创建宏观模拟场景
        
        Args:
            micro_export_path: 微观模拟导出文件路径
            scene_type: 场景类型（如 "labor_dispute", "wage_negotiation"等）
            output_path: 输出场景文件路径（可选）
        
        Returns:
            宏观模拟场景字典
        """
        with open(micro_export_path, 'r', encoding='utf-8') as f:
            micro_data = json.load(f)
        
        # 提取法律信息
        legal_system = micro_data.get('legal_system', {})
        law_codes = legal_system.get('law_codes_dict', {})
        
        # 构建法律描述
        law_description = ""
        if law_codes:
            law_description = "**Current Laws:**\n"
            for law_id, law_content in law_codes.items():
                if isinstance(law_content, dict):
                    desc = law_content.get('description', '')
                    law_description += f"- {law_id}: {desc}\n"
                else:
                    law_description += f"- {law_id}: {law_content}\n"
        else:
            law_description = "No laws currently in effect."
        
        # 根据场景类型创建不同的场景描述
        scenario = micro_data.get('scenario', {})
        company_name = scenario.get('company_name', 'the company')
        
        if scene_type == "labor_dispute":
            # 检查法律中是否有关于工作时长和安全的规定
            has_work_hours_law = any("work hours" in str(law).lower() or "overtime" in str(law).lower() 
                                     for law in law_codes.values())
            has_safety_law = any("safety" in str(law).lower() or "safe" in str(law).lower() 
                                 for law in law_codes.values())
            
            # 构建包含违法因素的场景描述
            violation_description = []
            if has_work_hours_law:
                violation_description.append(
                    f"{company_name} is requiring you to work more than the legally mandated maximum hours per week, "
                    "which violates labor protection laws."
                )
            if has_safety_law:
                violation_description.append(
                    f"{company_name} has significantly reduced safety investments below the legal minimum, "
                    "creating unsafe working conditions that violate workplace safety regulations."
                )
            
            if violation_description:
                violation_text = " ".join(violation_description)
                scene_description = (
                    f"You are an employee at {company_name}. "
                    f"{violation_text} "
                    f"{law_description}\n\n"
                    "You need to decide how to respond to these illegal practices."
                )
            else:
                scene_description = (
                    f"You are an employee at {company_name}. "
                    f"The company has recently made policy changes that affect your working conditions. "
                    f"{law_description}\n\n"
                    "You need to decide how to respond to these changes."
                )
            
            options = [
                "Continue working normally and accept the changes (even if illegal)",
                "File a formal complaint or lawsuit against the company for violations",
                "Organize or join a strike/protest against illegal practices",
                "Request a private negotiation to address the violations",
                "Look for alternative employment to avoid the illegal conditions"
            ]
        elif scene_type == "wage_negotiation":
            # 检查法律中是否有关于工资的规定
            has_wage_law = any("wage" in str(law).lower() or "salary" in str(law).lower() 
                              for law in law_codes.values())
            
            if has_wage_law:
                scene_description = (
                    f"You are negotiating your contract with {company_name}. "
                    f"The company is offering wages that may be below the legal minimum wage standard. "
                    f"{law_description}\n\n"
                    "You need to decide your negotiation strategy, considering the legal requirements."
                )
            else:
                scene_description = (
                    f"You are negotiating your contract with {company_name}. "
                    f"{law_description}\n\n"
                    "You need to decide your negotiation strategy."
                )
            
            options = [
                "Accept the company's offer (even if it violates minimum wage laws)",
                "Request wages that meet or exceed legal minimum standards",
                "Request better safety conditions (if legally required)",
                "Request reduced work hours (if current hours exceed legal limits)",
                "File a lawsuit if the company refuses to comply with legal requirements"
            ]
        elif scene_type == "company_violation":
            # 专门针对公司违法行为的场景
            scene_description = (
                f"You are an employee at {company_name}. "
                f"The company is engaging in illegal practices: requiring excessive overtime beyond legal limits, "
                f"providing insufficient safety protections below legal standards, and/or paying wages below the legal minimum. "
                f"{law_description}\n\n"
                "You need to decide how to respond to these clear violations of labor laws."
            )
            options = [
                "Continue working and ignore the violations (risking your own safety/rights)",
                "File a formal complaint or lawsuit against the company for multiple violations",
                "Organize or join a strike/protest to demand legal compliance",
                "Report the violations to labor authorities",
                "Quit and seek employment elsewhere"
            ]
        else:
            # 默认场景
            scene_description = (
                f"You are interacting with {company_name} regarding your employment. "
                f"{law_description}\n\n"
                "You need to make a decision."
            )
            options = [
                "Accept the current situation",
                "Take legal action",
                "Organize collective action",
                "Negotiate privately"
            ]
        
        scene = {
            "description": scene_description,
            "options": options,
            "prompt_template": (
                "You are a character simulation system. Simulate the final decision of a person "
                "based on the profile below.\n\n{profile}\n\nScene:\n{scene}\n\n"
                "Choose the most likely behavior:\n\n{options}\n\n"
                "Answer by outputting ONLY the letter of the selected option (e.g., A, B, C, D, or E). "
                "Do NOT write any explanation.\n\nExample:\nAnswer: B\n\nYour answer:\nAnswer:"
            ),
            "metadata": {
                "source": "micro_simulation",
                "scene_type": scene_type,
                "law_codes": law_codes,
                "company_name": company_name
            }
        }
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(scene, f, indent=2, ensure_ascii=False)
        
        return scene
    
    @staticmethod
    def load_micro_export(export_path: str) -> Dict[str, Any]:
        """加载微观模拟导出数据"""
        with open(export_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def apply_micro_laws_to_macro(macro_sim_config: Dict[str, Any],
                                   micro_export_path: str) -> Dict[str, Any]:
        """
        将微观模拟的法律系统应用到宏观模拟配置
        
        Args:
            macro_sim_config: 宏观模拟配置字典
            micro_export_path: 微观模拟导出文件路径
        
        Returns:
            更新后的宏观模拟配置
        """
        micro_data = MicroMacroBridge.load_micro_export(micro_export_path)
        
        legal_system = micro_data.get('legal_system', {})
        law_codes = legal_system.get('law_codes_dict', {})
        
        # 更新宏观配置，添加法律信息
        if 'scenes' not in macro_sim_config:
            macro_sim_config['scenes'] = []
        
        # 为每个场景添加法律上下文
        for scene in macro_sim_config['scenes']:
            if 'legal_context' not in scene:
                scene['legal_context'] = {}
            scene['legal_context']['law_codes'] = law_codes
            scene['legal_context']['source'] = 'micro_simulation'
        
        return macro_sim_config

