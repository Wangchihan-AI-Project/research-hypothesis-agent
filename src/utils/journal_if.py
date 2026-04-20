"""
期刊影响因子查询工具
使用 NCBI Journal Database API 获取期刊信息
"""
import re
import requests
from typing import Optional, Dict, Tuple
from functools import lru_cache

# 本地缓存的高影响因子期刊（用于快速匹配和离线回退）
HIGH_IMPACT_JOURNALS = {
    # 综合类
    'NATURE': 50.5,
    'SCIENCE': 49.0,
    'NATURE MEDICINE': 30.5,
    'NATURE GENETICS': 31.0,
    'NATURE BIOTECHNOLOGY': 54.0,
    'NATURE METHODS': 36.0,
    'NATURE COMMUNICATIONS': 16.0,
    'SCIENCE TRANSLATIONAL MEDICINE': 18.0,
    'SCIENCE ADVANCES': 14.0,
    'CELL': 64.5,
    'CELL REPORTS': 10.0,
    'LANCET': 168.0,
    'LANCET ONCOLOGY': 51.0,
    'LANCET DIGITAL HEALTH': 36.0,
    'JAMA': 63.0,
    'JAMA ONCOLOGY': 22.0,
    'JAMA INTERNAL MEDICINE': 44.0,
    'BMJ': 106.0,
    'BMJ QUALITY & SAFETY': 12.0,
    'PLOS MEDICINE': 11.0,
    # 生物学/医学
    'NATURE CELL BIOLOGY': 21.0,
    'NATURE IMMUNOLOGY': 30.0,
    'NATURE NEUROSCIENCE': 25.0,
    'NATURE STRUCTURAL & MOLECULAR BIOLOGY': 15.0,
    'CELL HOST & MICROBE': 30.0,
    'CELL METABOLISM': 29.0,
    'CELL STEM CELL': 24.0,
    'CELL SYSTEMS': 12.0,
    'CANCER CELL': 50.0,
    'CANCER DISCOVERY': 28.0,
    'NATURE REVIEWS CANCER': 78.0,
    'JOURNAL OF CLINICAL INVESTIGATION': 15.0,
    'EMBO JOURNAL': 11.0,
    'EMBO MOLECULAR MEDICINE': 11.0,
    'GENOME RESEARCH': 10.0,
    'GENOME BIOLOGY': 13.0,
    # 机器学习/AI
    'NATURE MACHINE INTELLIGENCE': 25.0,
    'JOURNAL OF MACHINE LEARNING RESEARCH': 8.0,
    'MACHINE LEARNING': 8.0,
    'IEEE PATTERN ANALYSIS AND MACHINE INTELLIGENCE': 24.0,
    # 生物信息学/计算生物学
    'BIOINFORMATICS': 6.0,
    'PLOS COMPUTATIONAL BIOLOGY': 4.0,
    'BRIEFINGS IN BIOINFORMATICS': 10.0,
    'NATURE COMPUTATIONAL SCIENCE': 6.0,
    # 医学各领域
    'CIRCULATION': 37.0,
    'CIRCULATION RESEARCH': 23.0,
    'EUROPEAN HEART JOURNAL': 39.0,
    'JACC': 24.0,
    'ANNUAL REVIEW OF MEDICINE': 50.0,
    'ANNUAL REVIEW OF BIOPHYSICS': 15.0,
    'ANNUAL REVIEW OF BIOCHEMISTRY': 40.0,
    'ANNUAL REVIEW OF GENETICS': 20.0,
    'ANNUAL REVIEW OF IMMUNOLOGY': 50.0,
    'ANNUAL REVIEW OF NEUROSCIENCE': 20.0,
    'NEUROIMAGE': 6.0,
    'NEURON': 16.0,
    'BRAIN': 15.0,
    'AMERICAN JOURNAL OF HUMAN GENETICS': 9.0,
    'HUMAN MOLECULAR GENETICS': 8.0,
    'MOLECULAR PSYCHIATRY': 14.0,
    'AMERICAN JOURNAL OF PSYCHIATRY': 15.0,
    'JAMA PSYCHIATRY': 25.0,
    'WORLD PSYCHIATRY': 12.0,
}

# NLM Catalog 期刊排名（基于引用频次）的粗略 IF 估算
JOURNAL_TIER_ESTIMATES = {
    # Tier 1 (IF ~50+)
    'CA-A CANCER JOURNAL FOR CLINICIANS': 503,
    'LANCET': 168,
    'NEW ENGLAND JOURNAL OF MEDICINE': 158,
    'JAMA': 63,
    'BMJ': 106,
    'CELL': 64.5,
    'NATURE': 50.5,
    'SCIENCE': 49,
    # Tier 2 (IF ~20-50)
    'NATURE MEDICINE': 30.5,
    'NATURE GENETICS': 31,
    'NATURE BIOTECHNOLOGY': 54,
    'NATURE METHODS': 36,
    'NATURE IMMUNOLOGY': 30,
    'CANCER CELL': 50,
    'NATURE REVIEWS CANCER': 78,
    'CIRCULATION': 37,
    # Tier 3 (IF ~10-20)
    'NATURE COMMUNICATIONS': 16,
    'SCIENCE ADVANCES': 14,
    'GENOME BIOLOGY': 13,
    'BRIEFINGS IN BIOINFORMATICS': 10,
    'JOURNAL OF CLINICAL INVESTIGATION': 15,
}


class JournalInfoFetcher:
    """期刊信息获取器 - 使用 NCBI API"""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self):
        self._cache: Dict[str, Tuple[float, str]] = {}  # {journal_name: (if_score, nlmid)}

    def _normalize_journal_name(self, name: str) -> str:
        """标准化期刊名称"""
        if not name:
            return ""

        # 转大写
        name = name.upper().strip()

        # 移除常见的期刊名后缀/前缀
        patterns_to_remove = [
            r'^THE\s+',
            r'\s*:.*',
            r'\s*\.',
            r'\s*JOURNAL$',
            r'\s*JNL$',
        ]
        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)

        # 标准化特殊字符
        name = name.replace(' & ', ' AND ')
        name = name.replace('-', ' ')

        # 压缩多余空格
        name = ' '.join(name.split())

        return name

    def _search_ncbi_journal(self, journal_name: str) -> Optional[Dict]:
        """在 NCBI NLM Catalog 中搜索期刊"""
        try:
            # 使用 NLM Catalog 数据库
            params = {
                'db': 'nlmcatalog',
                'term': f'"{journal_name}"[TA]',  # TA = Journal Title
                'retmax': 1,
                'retmode': 'json',
            }

            response = requests.get(self.BASE_URL, params=params, timeout=10)
            if response.status_code != 200:
                return None

            data = response.json()
            id_list = data.get('esearchresult', {}).get('idlist', [])

            if not id_list:
                return None

            # 获取期刊详细信息
            nlm_id = id_list[0]
            summary_params = {
                'db': 'nlmcatalog',
                'id': nlm_id,
                'retmode': 'json',
            }

            summary_response = requests.get(self.FETCH_URL, params=summary_params, timeout=10)
            if summary_response.status_code != 200:
                return None

            summary_data = summary_response.json()
            result = summary_data.get('result', {}).get(nlm_id, {})

            return {
                'nlm_id': nlm_id,
                'title': result.get('title', ''),
                'issn': result.get('issn', ''),
                'selective': result.get('selective', ''),  # 是否有同行评议
            }

        except Exception as e:
            return None

    def get_journal_if(self, journal_name: str) -> Tuple[float, str]:
        """
        获取期刊影响因子

        Returns:
            (影响因子, 数据来源)
            数据来源: 'cache', 'local', 'estimated', 'unknown'
        """
        if not journal_name:
            return 0.0, 'unknown'

        # 检查缓存
        normalized = self._normalize_journal_name(journal_name)
        if normalized in self._cache:
            return self._cache[normalized]

        # 1. 尝试精确匹配本地缓存
        journal_upper = journal_name.upper().strip()
        if journal_upper in HIGH_IMPACT_JOURNALS:
            if_val = HIGH_IMPACT_JOURNALS[journal_upper]
            result = (if_val, 'local') if isinstance(if_val, (int, float)) else (15.0, 'local')
            self._cache[normalized] = result
            return result

        # 2. 尝试模糊匹配本地缓存
        for key, val in HIGH_IMPACT_JOURNALS.items():
            if isinstance(val, (int, float)):
                # 检查包含关系
                if key in journal_upper or journal_upper in key:
                    # 确保匹配度足够高（至少50%重叠）
                    overlap = min(len(key), len(journal_upper))
                    total = max(len(key), len(journal_upper))
                    if overlap / total > 0.5:
                        self._cache[normalized] = (val, 'local')
                        return (val, 'local')

        # 3. 尝试从期刊名特征估算 IF
        if_val = self._estimate_if_from_name(journal_name)
        if if_val > 0:
            self._cache[normalized] = (if_val, 'estimated')
            return (if_val, 'estimated')

        # 4. 尝试查询 NCBI（可选，较慢）
        # nlm_info = self._search_ncbi_journal(journal_name)
        # if nlm_info:
        #     # 可以根据 NLM 信息进一步判断
        #     pass

        self._cache[normalized] = (0.0, 'unknown')
        return (0.0, 'unknown')

    def _estimate_if_from_name(self, journal_name: str) -> float:
        """根据期刊名称特征估算影响因子"""
        if not journal_name:
            return 0.0

        name_upper = journal_name.upper()

        # 高影响力期刊特征
        high_if_keywords = {
            'NATURE': 25.0,
            'SCIENCE': 25.0,
            'CELL': 30.0,
            'LANCET': 40.0,
            'JAMA': 20.0,
            'BMJ': 20.0,
            'PLOS MEDICINE': 12.0,
            'PLOS BIOLOGY': 10.0,
            'ANNUAL REVIEW': 15.0,
            'PHYSICAL REVIEW LETTERS': 10.0,
            'NEW ENGLAND JOURNAL': 50.0,
        }

        # 中等影响力期刊特征
        medium_if_keywords = {
            'JOURNAL OF': 5.0,
            'TRANSLATIONAL': 8.0,
            'CLINICAL': 6.0,
            'EXPERIMENTAL': 5.0,
            'MOLECULAR': 5.0,
            'GENETICS': 6.0,
            'IMMUNOLOGY': 7.0,
            'NEUROSCIENCE': 6.0,
            'BIOTECHNOLOGY': 10.0,
            'BIOINFORMATICS': 6.0,
            'COMPUTATIONAL': 5.0,
        }

        # 检查高影响力关键词
        for keyword, base_if in high_if_keywords.items():
            if keyword in name_upper:
                # 如果是 Nature/Science 子刊，给予较高 IF
                if 'NATURE' in name_upper and len(name_upper.split()) > 1:
                    return min(base_if * 1.2, 50.0)  # 子刊 IF 稍高
                return base_if

        # 检查中等影响力关键词
        for keyword, base_if in medium_if_keywords.items():
            if keyword in name_upper:
                return base_if

        # 检查是否为知名期刊（但 IF < 10）
        known_journals = {
            'SCIENTIFIC REPORTS': 4.6,
            'PLOS ONE': 3.5,
            'IEEE ACCESS': 3.9,
            'FRONTIERS': 3.0,
            'BMJ OPEN': 3.0,
            'MEDICINE': 2.5,
            'SCIENTIFIC Reports': 4.6,
        }

        for keyword, base_if in known_journals.items():
            if keyword in name_upper:
                return base_if

        return 0.0


# 全局实例
_journal_fetcher = JournalInfoFetcher()


@lru_cache(maxsize=1000)
def get_journal_if(journal_name: str) -> float:
    """
    获取期刊的影响因子（带缓存）

    Args:
        journal_name: 期刊名称

    Returns:
        影响因子，如果找不到返回 0
    """
    if not journal_name:
        return 0.0

    # 确保 journal_name 是字符串
    if not isinstance(journal_name, str):
        journal_name = str(journal_name)

    # 如果包含无用信息，返回0
    if 'DictionaryElement' in journal_name or 'StringElement' in journal_name:
        return 0.0

    if_val, _ = _journal_fetcher.get_journal_if(journal_name)
    return if_val


def get_journal_if_with_source(journal_name: str) -> Tuple[float, str]:
    """
    获取期刊影响因子和数据来源

    Returns:
        (影响因子, 数据来源)
        数据来源: 'cache', 'local', 'estimated', 'unknown'
    """
    if not journal_name:
        return 0.0, 'unknown'

    if not isinstance(journal_name, str):
        journal_name = str(journal_name)

    return _journal_fetcher.get_journal_if(journal_name)


# ==================== 顶刊白名单查询串生成器 ====================

def build_journal_whitelist_query(min_if: float = 10.0) -> str:
    """
    构建顶刊白名单查询串（谓词下推优化版）

    从本地 IF 字典中提取所有 IF ≥ min_if 的期刊名称，
    拼接成 PubMed 原生支持的查询语法。

    Args:
        min_if: 最低影响因子要求，默认 10.0

    Returns:
        PubMed 查询串，例如：("Nature"[Journal] OR "Science"[Journal] OR ...)

    Examples:
        >>> build_journal_whitelist_query(10.0)
        '("Nature"[Journal] OR "Science"[Journal] OR "Cell"[Journal] OR ...)'
    """
    # 筛选 IF ≥ min_if 的期刊
    selected_journals = []
    for journal_name, if_value in HIGH_IMPACT_JOURNALS.items():
        if isinstance(if_value, (int, float)) and if_value >= min_if:
            selected_journals.append(journal_name)

    if not selected_journals:
        return ""

    # 构建 PubMed 查询串
    # 格式：("Journal1"[Journal] OR "Journal2"[Journal] OR ...)
    journal_terms = [f'"{journal}"[Journal]' for journal in selected_journals]
    query = '(' + ' OR '.join(journal_terms) + ')'

    print(f"[顶刊白名单] 提取了 {len(selected_journals)} 个 IF ≥ {min_if} 的期刊")
    return query


def get_whitelist_journal_names(min_if: float = 10.0) -> List[str]:
    """
    获取顶刊白名单期刊名称列表

    Args:
        min_if: 最低影响因子要求

    Returns:
        期刊名称列表
    """
    return [name for name, if_val in HIGH_IMPACT_JOURNALS.items()
            if isinstance(if_val, (int, float)) and if_val >= min_if]


# ================================================================================

def is_high_impact_journal(journal_name: str, min_if: float = 10.0) -> bool:
    """
    判断是否为高影响因子期刊

    Args:
        journal_name: 期刊名称
        min_if: 最低影响因子要求

    Returns:
        是否为高影响因子期刊
    """
    if_val = get_journal_if(journal_name)
    return if_val >= min_if


if __name__ == '__main__':
    # 测试
    test_journals = [
        "Nature",
        "Science",
        "Cell",
        "Bioinformatics",
        "PLOS ONE",
        "Journal of Biological Chemistry",
        "Nature Communications",
        "Frontiers in Neuroscience",
        "Some Unknown Journal",
    ]

    print("期刊影响因子测试:")
    print("-" * 50)
    for journal in test_journals:
        if_val, source = get_journal_if_with_source(journal)
        print(f"{journal:40s} IF={if_val:5.1f} (来源: {source})")
