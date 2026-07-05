import math
import random
import json
import os
from typing import Dict, Any, Union

class AttributeSampler:
    _data: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load(cls, path: str):
        if not cls._data:
            with open(path, 'r', encoding='utf-8') as f:
                cls._data = json.load(f)

    @classmethod
    def sample(cls, country: str, attribute: str) -> Any:
        """通用采样：支持分布型、标量、比率属性"""
        if country not in cls._data:
            raise ValueError(f"国家 {country} 不在属性分布数据中。")
        if attribute not in cls._data[country]:
            raise ValueError(f"国家 {country} 缺少属性 {attribute} 的分布。")

        val = cls._data[country][attribute]

        if isinstance(val, dict):
            # 如果是嵌套字典且包含 "monthly" 键（如 unemployment_benefit），返回其数值
            if 'monthly' in val:
                return val['monthly']
            else:
                # 否则按权重随机采样键名（如 education、religion）
                return random.choices(list(val.keys()), weights=list(val.values()), k=1)[0]
        else:
            return val  # 比率/连续型属性

    @classmethod
    def sample_income_from_gini(cls, country: str) -> float:
        """根据 gini 系数和中位收入采样个体年收入（单位：PPP 美元）"""
        info = cls._data.get(country)
        gini = info.get("gini")
        median = info.get("income_absolute_ppp", {}).get("median")
        if gini is None or median is None:
            raise ValueError(f"{country} 缺少 gini 或 median 收入数据")

        sigma = math.sqrt(math.log(1 + (math.pi**2 / 3) * gini**2))
        mu = math.log(median)
        return random.lognormvariate(mu, sigma)

    @classmethod
    def sample_boolean(cls, country: str, attribute: str) -> bool:
        """根据某属性比率进行布尔采样（如毒品使用、帮派影响、就业状态）"""
        rate = cls.sample(country, attribute)
        if not isinstance(rate, (float, int)):
            raise TypeError(f"{attribute} 必须是数值型比率")
        return random.random() < rate

    @classmethod
    def sample_income_by_education(cls, country: str, education_level: str) -> float:
        """根据教育水平采样收入（单位：PPP 美元）"""
        info = cls._data.get(country)
        if not info:
            raise ValueError(f"国家 {country} 不在属性分布数据中。")

        education_income_data = info.get("income_median_by_education_ppp")
        if not education_income_data:
            raise ValueError(f"{country} 缺少按教育水平分类的收入数据")

        education_mapping = {
            "below_upper_secondary": "below_upper_secondary",
            "upper_secondary": "upper_secondary",
            "tertiary_bachelor": "tertiary_total",
            "tertiary_master_or_above": "tertiary_total",
            "tertiary_other": "tertiary_total"
        }

        income_key = education_mapping.get(education_level)
        if not income_key or income_key not in education_income_data:
            median_income = info.get("income_absolute_ppp", {}).get("median", 5000)
        else:
            median_income = education_income_data[income_key]

        sigma = 0.5
        mu = math.log(median_income)
        return random.lognormvariate(mu, sigma)

    @classmethod
    def sample_income_by_education_and_gender(cls, country: str, education_level: str, gender: str) -> float:
        """根据教育水平和性别采样收入（单位：PPP 美元）

        约束：
        - 给定教育水平下，男性收入是女性的 1.2 倍
        - 保持该教育水平的平均收入不变
        """
        info = cls._data.get(country)
        if not info:
            raise ValueError(f"国家 {country} 不在属性分布数据中。")

        education_income_data = info.get("income_median_by_education_ppp")
        if not education_income_data:
            raise ValueError(f"{country} 缺少按教育水平分类的收入数据")

        education_mapping = {
            "below_upper_secondary": "below_upper_secondary",
            "upper_secondary": "upper_secondary",
            "tertiary_bachelor": "tertiary_total",
            "tertiary_master_or_above": "tertiary_total",
            "tertiary_other": "tertiary_total"
        }

        income_key = education_mapping.get(education_level)
        if not income_key or income_key not in education_income_data:
            base_median_income = info.get("income_absolute_ppp", {}).get("median", 5000)
        else:
            base_median_income = education_income_data[income_key]

        # 男女比例约为 51:49
        # 设女性中位收入为 f，男性为 1.2f
        # 平均 = 0.49f + 0.51 * 1.2f = 1.102f → f = base / 1.102
        female_median = base_median_income / 1.102
        male_median = female_median * 1.2

        adjusted_median = female_median if gender == "female" else male_median

        sigma = 0.5
        mu = math.log(adjusted_median)
        return random.lognormvariate(mu, sigma)

    @classmethod
    def sample_drug_use_by_demographics(cls, country: str, gender: str, age: int) -> bool:
        """根据性别和年龄采样吸毒率

        约束：
        - 男性吸毒率是女性的 1.3 倍
        - 18-25 岁吸毒率是 26 岁以上的 1.75 倍
        - 保持宏观吸毒率不变
        """
        base_rate = cls.sample(country, "drug_use_rate")

        # 宏观率 = 1.3225 * base_female_26plus_rate → base_female_26plus_rate = base_rate / 1.3225
        base_female_26plus_rate = base_rate / 1.3225

        if gender == "female":
            individual_rate = base_female_26plus_rate * 1.75 if age <= 25 else base_female_26plus_rate
        else:
            individual_rate = base_female_26plus_rate * 1.3 * 1.75 if age <= 25 else base_female_26plus_rate * 1.3

        return random.random() < individual_rate

    @classmethod
    def sample_gang_influence_by_gender(cls, country: str, gender: str) -> bool:
        """根据性别采样帮派接触率

        约束：
        - 男性帮派接触率是女性的 1.5 倍
        - 保持宏观帮派接触率不变
        """
        base_rate = cls.sample(country, "gang_influence_rate")

        # 宏观率 = 1.25 * female_rate → female_rate = base_rate / 1.25
        female_rate = base_rate / 1.25
        individual_rate = female_rate if gender == "female" else female_rate * 1.5
        return random.random() < individual_rate

    @classmethod
    def sample_numeric(cls, country: str, attribute: str) -> Union[int, float]:
        """直接返回数值型属性值（如 community_safety_index 或失业救济金）"""
        return cls.sample(country, attribute)