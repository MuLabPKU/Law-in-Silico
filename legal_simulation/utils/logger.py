"""
改进的日志系统 - 精简、结构化，方便观测每轮状态
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


class SimulationLogger:
    """模拟日志记录器 - 结构化记录每轮状态"""
    
    def __init__(self, log_dir: str = "logs", verbose: bool = True):
        """
        Args:
            log_dir: 日志目录
            verbose: 是否输出详细日志到控制台
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.verbose = verbose
        
        # 结构化数据存储
        self.turn_logs: List[Dict[str, Any]] = []
        self.month_logs: List[Dict[str, Any]] = []
        
        # 设置Python logging
        self.logger = logging.getLogger("SimulationLogger")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO if verbose else logging.WARNING)
    
    def log_turn(self, 
                  turn: int,
                  month: int,
                  date: str,
                  company_action: Dict[str, Any],
                  laborer_actions: Dict[str, Dict[str, Any]],
                  company_status: Dict[str, Any],
                  laborer_statuses: Dict[str, Dict[str, Any]],
                  legal_system_status: Dict[str, Any],
                  observations: Optional[Dict[str, Any]] = None,
                  lawsuits: Optional[List[Dict[str, Any]]] = None):
        """记录一轮的状态"""
        turn_log = {
            "turn": turn,
            "month": month,
            "date": date,
            "company": {
                "action": company_action,
                "status": company_status
            },
            "laborers": {
                "actions": laborer_actions,
                "statuses": laborer_statuses
            },
            "legal_system": legal_system_status,
            "observations": observations or {},
            "lawsuits": lawsuits or []
        }
        
        self.turn_logs.append(turn_log)
        
        # 输出摘要到控制台
        if self.verbose:
            self._print_turn_summary(turn_log)
    
    def log_month_end(self, month: int, legal_changes: Optional[List[Dict[str, Any]]] = None):
        """记录月末状态"""
        month_log = {
            "month": month,
            "legal_changes": legal_changes or [],
            "summary": self._generate_month_summary(month)
        }
        
        self.month_logs.append(month_log)
        
        if self.verbose:
            self._print_month_summary(month_log)
    
    def _print_turn_summary(self, turn_log: Dict[str, Any]):
        """打印轮次摘要"""
        print(f"\n{'='*60}")
        print(f"Turn {turn_log['turn']} | Month {turn_log['month']} | {turn_log['date']}")
        print(f"{'='*60}")
        
        # 公司动作
        company_action = turn_log['company']['action'].get('action', 'None')
        print(f"Company Action: {company_action}")
        
        # 劳工动作
        print("\nLaborer Actions:")
        for laborer_id, action_data in turn_log['laborers']['actions'].items():
            action = action_data.get('action', 'None')
            print(f"  {laborer_id}: {action}")
        
        # 状态摘要
        company_status = turn_log['company']['status']
        print(f"\nCompany Status:")
        print(f"  Capital: ${company_status.get('capital', 0):.2f}")
        print(f"  Employees: {company_status.get('num_employees', 0)}")
        
        print(f"\nLaborer Status:")
        for laborer_id, status in turn_log['laborers']['statuses'].items():
            cash = status.get('cash', 0)
            welfare = status.get('welfare', 0)
            hired = status.get('isHired', False)
            print(f"  {laborer_id}: Cash=${cash:.2f}, Welfare={welfare:.2f}, Hired={hired}")
        
        # 法律系统
        legal_status = turn_log['legal_system']
        law_count = len(legal_status.get('law_codes', {}))
        print(f"\nLegal System: {law_count} law(s) in effect")
        
        # 诉讼
        lawsuits = turn_log.get('lawsuits', [])
        if lawsuits:
            print(f"\nLawsuits ({len(lawsuits)}):")
            for lawsuit in lawsuits:
                print(f"  {lawsuit.get('plaintiff')} vs {lawsuit.get('defendant')}: {lawsuit.get('reason')}")
    
    def _print_month_summary(self, month_log: Dict[str, Any]):
        """打印月末摘要"""
        print(f"\n{'#'*60}")
        print(f"End of Month {month_log['month']}")
        print(f"{'#'*60}")
        
        legal_changes = month_log.get('legal_changes', [])
        if legal_changes:
            print(f"New Laws Enacted: {len(legal_changes)}")
            for change in legal_changes:
                print(f"  - {change.get('law_id', 'Unknown')}: {change.get('description', '')[:50]}...")
        else:
            print("No new laws enacted this month")
        
        summary = month_log.get('summary', {})
        if summary:
            print(f"\nMonth Summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
    
    def _generate_month_summary(self, month: int) -> Dict[str, Any]:
        """生成月末摘要统计"""
        # 获取该月的所有轮次
        month_turns = [t for t in self.turn_logs if t['month'] == month]
        
        if not month_turns:
            return {}
        
        # 统计信息
        total_lawsuits = sum(len(t.get('lawsuits', [])) for t in month_turns)
        
        # 平均福利
        all_welfares = []
        for turn in month_turns:
            for status in turn['laborers']['statuses'].values():
                welfare = status.get('welfare', 0)
                if welfare > 0:
                    all_welfares.append(welfare)
        
        avg_welfare = sum(all_welfares) / len(all_welfares) if all_welfares else 0
        
        # 公司资本变化
        if len(month_turns) > 0:
            first_capital = month_turns[0]['company']['status'].get('capital', 0)
            last_capital = month_turns[-1]['company']['status'].get('capital', 0)
            capital_change = last_capital - first_capital
        else:
            capital_change = 0
        
        return {
            "total_turns": len(month_turns),
            "total_lawsuits": total_lawsuits,
            "average_welfare": round(avg_welfare, 2),
            "capital_change": round(capital_change, 2)
        }
    
    def save_logs(self, filepath: Optional[str] = None):
        """保存日志到JSON文件"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.log_dir / f"simulation_log_{timestamp}.json"
        
        log_data = {
            "turns": self.turn_logs,
            "months": self.month_logs,
            "summary": {
                "total_turns": len(self.turn_logs),
                "total_months": len(self.month_logs)
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Logs saved to {filepath}")
        return filepath
    
    def export_for_macro(self, output_path: str):
        """导出用于宏观模拟的数据"""
        # 提取法律系统演化历史
        legal_evolution = []
        for turn_log in self.turn_logs:
            legal_system = turn_log.get('legal_system', {})
            law_codes = legal_system.get('law_codes', {})
            if law_codes:
                legal_evolution.append({
                    "date": turn_log['date'],
                    "month": turn_log['month'],
                    "turn": turn_log['turn'],
                    "law_codes": law_codes
                })
        
        # 提取场景信息（从背景配置）
        # 这里需要从Simulation类获取背景信息
        
        export_data = {
            "legal_evolution": legal_evolution,
            "final_law_codes": self.turn_logs[-1].get('legal_system', {}).get('law_codes', {}) if self.turn_logs else {},
            "simulation_summary": {
                "total_turns": len(self.turn_logs),
                "total_months": len(self.month_logs)
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Macro simulation data exported to {output_path}")
        return output_path

