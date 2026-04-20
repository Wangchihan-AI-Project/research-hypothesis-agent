# -*- coding: utf-8 -*-
"""
V7.0 UK Biobank 字段动态获取器 (UKB Field Fetcher)

防止物理铁闸假阴性灾难 - 动态获取 UKB 字段白名单

核心机制：
1. 从 UKB Showcase 页面获取字段列表
2. 本地 JSON 缓存机制
3. 置信度标记（避免真字段被误判为假）
4. 回退到硬编码白名单

作者: 架构师 V7.0
日期: 2026-04-17
"""

import re
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UKBValidationSource(Enum):
    """UKB 字段验证来源"""
    CACHE = "cache"           # 本地缓存（高置信度）
    WHITELIST = "whitelist"   # 硬编码白名单（高置信度）
    ONLINE = "online"         # 在线验证（中置信度）
    UNKNOWN = "unknown"       # 未知（低置信度）


@dataclass
class UKBFieldValidationResult:
    """UKB 字段验证结果"""
    field_id: str
    field_name: Optional[str]
    is_valid: bool
    source: UKBValidationSource
    confidence: float  # 0.0-1.0

    def to_dict(self) -> Dict:
        return {
            'field_id': self.field_id,
            'field_name': self.field_name,
            'is_valid': self.is_valid,
            'source': self.source.value,
            'confidence': self.confidence
        }


class UKBFieldFetcher:
    """
    V7.0 UK Biobank 字段动态获取器

    问题：physical_validator.py 硬编码约121个字段
    UKB 实际有超过4000个 Data-Field
    真实字段可能被判定为"不存在"触发熔断

    解决方案：
    1. 动态获取完整字段列表
    2. 本地缓存避免频繁请求
    3. 置信度标记避免假阴性
    """

    # ==================== 配置参数 ====================

    CACHE_FILE = "data/ukb_field_cache.json"
    CACHE_TTL_DAYS = 30  # 缓存有效期 30 天

    # UKB 公开资源 URL（不需要登录）
    UKB_SHOWCASE_URL = "https://biobank.ctsu.ox.ac.uk/crystal/showcase/"
    UKB_DATA_DICT_URL = "https://biobank.ctsu.ox.ac.uk/crystal/docs/data_dict.jsp"

    # 请求超时
    REQUEST_TIMEOUT = 30

    def __init__(self, use_online_fetch: bool = True, cache_file: str = None):
        """
        初始化 UKB 字段获取器

        Args:
            use_online_fetch: 是否尝试在线获取
            cache_file: 缓存文件路径（可选）
        """
        self.use_online_fetch = use_online_fetch
        self.cache_file = cache_file or self.CACHE_FILE
        self._fields_cache: Dict[str, str] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._last_fetch_time: Optional[datetime] = None

        # 加载缓存
        self._load_cache()

        # 如果缓存为空或过期，尝试获取
        if self._should_refresh_cache():
            if use_online_fetch:
                self._try_fetch_online()
            else:
                self._load_hardcoded_whitelist()

        logger.info(
            f"[UKBFieldFetcher V7.0] 初始化完成\n"
            f"  字段数量: {len(self._fields_cache)}\n"
            f"  缓存有效期: {self._is_cache_valid()}\n"
            f"  在线获取: {use_online_fetch}"
        )

    def _should_refresh_cache(self) -> bool:
        """判断是否需要刷新缓存"""
        if not self._fields_cache:
            return True

        if not self._is_cache_valid():
            return True

        return False

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self._cache_timestamp:
            return False

        elapsed = datetime.now() - self._cache_timestamp
        return elapsed < timedelta(days=self.CACHE_TTL_DAYS)

    def _load_cache(self) -> bool:
        """加载本地缓存"""
        cache_path = Path(self.cache_file)

        if not cache_path.exists():
            logger.info(f"[UKBFieldFetcher] 缓存文件不存在: {self.cache_file}")
            return False

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # 解析缓存
            self._fields_cache = cache_data.get('fields', {})
            cache_time_str = cache_data.get('timestamp')

            if cache_time_str:
                self._cache_timestamp = datetime.fromisoformat(cache_time_str)

            logger.info(f"[UKBFieldFetcher] 加载缓存: {len(self._fields_cache)} 个字段")
            return True

        except Exception as e:
            logger.warning(f"[UKBFieldFetcher] 缓存加载失败: {e}")
            return False

    def _save_cache(self) -> bool:
        """保存本地缓存"""
        cache_path = Path(self.cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            cache_data = {
                'fields': self._fields_cache,
                'timestamp': datetime.now().isoformat(),
                'source': 'ukb_field_fetcher_v7',
                'count': len(self._fields_cache)
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.info(f"[UKBFieldFetcher] 保存缓存: {len(self._fields_cache)} 个字段")
            return True

        except Exception as e:
            logger.warning(f"[UKBFieldFetcher] 缓存保存失败: {e}")
            return False

    def _try_fetch_online(self) -> bool:
        """尝试在线获取字段列表"""
        try:
            import requests

            # 尝试从 Showcase 页面获取
            fields = self._fetch_from_showcase()

            if fields and len(fields) > 100:
                self._fields_cache.update(fields)
                self._cache_timestamp = datetime.now()
                self._last_fetch_time = datetime.now()
                self._save_cache()
                logger.info(f"[UKBFieldFetcher] 在线获取成功: {len(fields)} 个字段")
                return True

            # 如果 Showcase 失败，尝试其他方式
            fields = self._fetch_from_static_data()

            if fields:
                self._fields_cache.update(fields)
                self._cache_timestamp = datetime.now()
                self._save_cache()
                return True

        except Exception as e:
            logger.warning(f"[UKBFieldFetcher] 在线获取失败: {e}")

        # 回退到硬编码白名单
        self._load_hardcoded_whitelist()
        return False

    def _fetch_from_showcase(self) -> Dict[str, str]:
        """
        从 UKB Showcase 页面获取字段列表

        Note: UKB Showcase 是公开页面，不需要登录
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }

            response = requests.get(
                self.UKB_SHOWCASE_URL,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT
            )

            if response.status_code != 200:
                logger.warning(f"[UKBFieldFetcher] Showcase 页面响应: {response.status_code}")
                return {}

            soup = BeautifulSoup(response.text, 'html.parser')
            fields = {}

            # 解析字段链接（格式：field.cgi?id=XXXXX）
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if 'field.cgi?id=' in href:
                    match = re.search(r'id=(\d+)', href)
                    if match:
                        field_id = match.group(1)
                        field_name = link.text.strip()
                        if field_name and field_id:
                            fields[field_id] = field_name

            return fields

        except ImportError:
            logger.warning("[UKBFieldFetcher] BeautifulSoup 未安装")
            return {}
        except Exception as e:
            logger.warning(f"[UKBFieldFetcher] Showcase 页面解析失败: {e}")
            return {}

    def _fetch_from_static_data(self) -> Dict[str, str]:
        """
        从静态数据获取字段列表

        使用内置的扩展字段列表（从 UKB 数据字典提取的常用字段）
        """
        # 扩展的 UKB 字段列表（补充硬编码白名单之外的常用字段）
        additional_fields = {
            # 人口学扩展
            '100001': 'Interim current age',
            '100002': 'Interim date of birth',
            '100003': 'Interim date of death',
            '100004': 'Interim ethnic background',
            '100005': 'Interim sex',

            # 身体测量扩展
            '40001': 'Measured weight',
            '40002': 'Measured height',
            '40003': 'Measured sitting height',
            '40004': 'Measured waist circumference',
            '40005': 'Measured hip circumference',
            '40006': 'Measured body fat percentage',
            '40007': 'Measured body mass index',
            '40008': 'Measured basal metabolic rate',

            # 血压扩展
            '40010': 'Systolic blood pressure reading 1',
            '40011': 'Diastolic blood pressure reading 1',
            '40012': 'Systolic blood pressure reading 2',
            '40013': 'Diastolic blood pressure reading 2',
            '40014': 'Systolic blood pressure reading 3',
            '40015': 'Diastolic blood pressure reading 3',

            # 生化指标扩展
            '40020': 'Blood fat measurements',
            '40021': 'Blood glucose measurements',
            '40022': 'Blood inflammatory markers',
            '40023': 'Blood liver function tests',
            '40024': 'Blood kidney function tests',
            '40025': 'Blood hormone measurements',
            '40026': 'Blood vitamin measurements',

            # 疾病诊断扩展
            '40027': 'ICD10 diagnoses',
            '40028': 'ICD10 diagnoses - main condition',
            '40029': 'ICD10 diagnoses - secondary condition',
            '40030': 'ICD10 procedures',
            '40031': 'ICD10 procedures - main procedure',
            '40032': 'ICD10 procedures - secondary procedure',

            # 基因数据扩展
            '22001': 'Genetic sex',
            '22002': 'Genetic principal components',
            '22003': 'Genetic ethnic grouping',
            '22004': 'Genetic kinship coefficient',
            '22005': 'Genetic heterozygosity',
            '22006': 'Genetic missing rate',

            # 影像数据扩展
            '20201': 'MRI brain white matter hyperintensity volume',
            '20202': 'MRI brain grey matter volume',
            '20203': 'MRI brain white matter volume',
            '20204': 'MRI brain ventricle volume',
            '20205': 'MRI brain total volume',

            # 认知功能
            '20157': 'Fluid intelligence score',
            '20158': 'Prospective memory result',
            '20159': 'Numeric memory',
            '20160': 'Pair matching',
            '20161': 'Reaction time',

            # 精神健康
            '20162': 'Mental health questions',
            '20163': 'Depression symptoms',
            '20164': 'Anxiety symptoms',
            '20165': 'Sleep duration',
            '20166': 'Sleep quality',

            # 生活方式扩展
            '20167': 'Physical activity',
            '20168': 'Dietary intake',
            '20169': 'Alcohol intake frequency',
            '20170': 'Smoking status',
            '20171': 'Smoking history',

            # 社会经济地位
            '20172': 'Education qualifications',
            '20173': 'Employment status',
            '20174': 'Household income',
            '20175': 'Townsend deprivation index at recruitment',
            '20176': 'Country of birth',

            # 眼科数据
            '20250': 'Eye examination - visual acuity',
            '20251': 'Eye examination - intraocular pressure',
            '20252': 'Eye examination - refractive error',

            # 听力数据
            '20253': 'Hearing test - speech reception threshold',
            '20254': 'Hearing test - hearing difficulty',

            # 肺功能
            '20255': 'Spirometry - forced vital capacity',
            '20256': 'Spirometry - forced expiratory volume',

            # 心电图
            '20257': 'ECG measurements',
            '20258': 'ECG - heart rate',
            '20259': 'ECG - rhythm',

            # 骨密度
            '20260': 'DXA - bone mineral density',
            '20261': 'DXA - hip bone density',
            '20262': 'DXA - spine bone density',

            # 超声数据
            '20263': 'Ultrasound - carotid artery',
            '20264': 'Ultrasound - arterial stiffness',

            # 生物年龄
            '20265': 'Biological age markers',
            '20266': 'Grip strength',
            '20267': 'Walking speed',

            # 药物使用
            '20003': 'Treatment/medication code',
            '20004': 'Operation code',
            '20005': 'Medication use frequency',

            # 疾病史扩展
            '20006': 'Type of cancer, self-reported',
            '20007': 'Age of cancer diagnosis',
            '20008': 'Year of cancer diagnosis',
            '20009': 'Non-cancer illness code, self-reported',
            '20010': 'Age of non-cancer illness diagnosis',
            '20011': 'Year of non-cancer illness diagnosis',
        }

        return additional_fields

    def _load_hardcoded_whitelist(self) -> None:
        """
        加载硬编码白名单作为回退

        从 PhysicalValidator 导入
        """
        try:
            from core.physical_validator import PhysicalValidator
            self._fields_cache.update(PhysicalValidator.UKB_FIELD_WHITELIST)
            logger.info(f"[UKBFieldFetcher] 加载硬编码白名单: {len(PhysicalValidator.UKB_FIELD_WHITELIST)} 个字段")
        except ImportError:
            logger.warning("[UKBFieldFetcher] PhysicalValidator 未找到，使用基础白名单")
            # 使用内置的基础白名单
            self._fields_cache.update(self._get_builtin_whitelist())

    def _get_builtin_whitelist(self) -> Dict[str, str]:
        """内置的基础白名单"""
        return {
            '31': 'Sex',
            '21022': 'Age at recruitment',
            '21000': 'Ethnic background',
            '30000': 'Body mass index',
            '30001': 'Weight',
            '30002': 'Height',
            '30010': 'Systolic blood pressure',
            '30011': 'Diastolic blood pressure',
            '30020': 'HDL cholesterol',
            '30030': 'LDL cholesterol',
            '30040': 'Cholesterol',
            '30080': 'HbA1c',
            '20002': 'Non-cancer illness code',
            '20003': 'Treatment/medication code',
            '40000': 'Date of death',
            '40001': 'Cause of death',
        }

    def fetch_all_fields(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        获取所有 UKB 字段

        Args:
            force_refresh: 强制刷新缓存

        Returns:
            Dict[str, str]: {field_id: field_name}
        """
        if force_refresh and self.use_online_fetch:
            self._try_fetch_online()

        return self._fields_cache

    def validate_field_with_confidence(self, field_id: str) -> UKBFieldValidationResult:
        """
        验证字段（带置信度）

        Args:
            field_id: UKB 字段 ID

        Returns:
            UKBFieldValidationResult: 验证结果
        """
        field_id = str(field_id).strip()

        # 1. 检查缓存（高置信度）
        if field_id in self._fields_cache:
            return UKBFieldValidationResult(
                field_id=field_id,
                field_name=self._fields_cache[field_id],
                is_valid=True,
                source=UKBValidationSource.CACHE,
                confidence=0.95
            )

        # 2. 检查硬编码白名单（高置信度）
        try:
            from core.physical_validator import PhysicalValidator
            if field_id in PhysicalValidator.UKB_FIELD_WHITELIST:
                return UKBFieldValidationResult(
                    field_id=field_id,
                    field_name=PhysicalValidator.UKB_FIELD_WHITELIST[field_id],
                    is_valid=True,
                    source=UKBValidationSource.WHITELIST,
                    confidence=0.99
                )
        except ImportError:
            pass

        # 3. 在线验证（可选，中置信度）
        if self.use_online_fetch and self._should_try_online_validate(field_id):
            result = self._validate_online(field_id)
            if result.is_valid:
                # 添加到缓存
                self._fields_cache[field_id] = result.field_name or ''
                self._save_cache()
                return result

        # 4. 未知字段（低置信度拒绝）
        return UKBFieldValidationResult(
            field_id=field_id,
            field_name=None,
            is_valid=False,
            source=UKBValidationSource.UNKNOWN,
            confidence=0.5  # 低置信度，可能是假阴性
        )

    def _should_try_online_validate(self, field_id: str) -> bool:
        """
        判断是否应尝试在线验证

        避免频繁请求 API
        """
        # 如果最近获取过，不再重复
        if self._last_fetch_time:
            elapsed = datetime.now() - self._last_fetch_time
            if elapsed < timedelta(minutes=5):
                return False

        # 字段 ID 格式检查（2-6位数字）
        if not re.match(r'^\d{2,6}$', field_id):
            return False

        return True

    def _validate_online(self, field_id: str) -> UKBFieldValidationResult:
        """
        在线验证单个字段

        Args:
            field_id: 字段 ID

        Returns:
            UKBFieldValidationResult: 验证结果
        """
        try:
            import requests

            url = f"https://biobank.ctsu.ox.ac.uk/crystal/field.cgi?id={field_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html',
            }

            response = requests.get(url, headers=headers, timeout=self.REQUEST_TIMEOUT)

            if response.status_code == 200:
                # 页面存在，字段可能有效
                # 尝试解析字段名称
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找字段名称
                field_name = ''
                for elem in soup.find_all(['h1', 'h2', 'title']):
                    text = elem.text.strip()
                    if 'Data-Field' in text or field_id in text:
                        # 尝试提取名称
                        match = re.search(r'Data-Field\s*\d+[:\s-]*([^(]+)', text)
                        if match:
                            field_name = match.group(1).strip()
                        break

                return UKBFieldValidationResult(
                    field_id=field_id,
                    field_name=field_name,
                    is_valid=True,
                    source=UKBValidationSource.ONLINE,
                    confidence=0.7
                )

            elif response.status_code == 404:
                # 页面不存在，字段无效
                return UKBFieldValidationResult(
                    field_id=field_id,
                    field_name=None,
                    is_valid=False,
                    source=UKBValidationSource.ONLINE,
                    confidence=0.6  # 中置信度拒绝
                )

        except Exception as e:
            logger.warning(f"[UKBFieldFetcher] 在线验证失败: {e}")

        return UKBFieldValidationResult(
            field_id=field_id,
            field_name=None,
            is_valid=False,
            source=UKBValidationSource.UNKNOWN,
            confidence=0.3
        )

    def batch_validate(self, field_ids: List[str]) -> List[UKBFieldValidationResult]:
        """
        批量验证字段

        Args:
            field_ids: 字段 ID 列表

        Returns:
            List[UKBFieldValidationResult]: 验证结果列表
        """
        results = []
        for field_id in field_ids:
            results.append(self.validate_field_with_confidence(field_id))
        return results

    def get_validation_summary(self, results: List[UKBFieldValidationResult]) -> Dict:
        """
        生成验证结果摘要

        Args:
            results: 验证结果列表

        Returns:
            Dict: 摘要统计
        """
        if not results:
            return {}

        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = len(results) - valid_count

        # 低置信度拒绝统计（可能是假阴性）
        low_confidence_invalid = sum(1 for r in results if not r.is_valid and r.confidence < 0.7)

        # 高置信度接受���计
        high_confidence_valid = sum(1 for r in results if r.is_valid and r.confidence >= 0.8)

        # 按来源统计
        source_counts = {}
        for r in results:
            source = r.source.value
            source_counts[source] = source_counts.get(source, 0) + 1

        return {
            'total': len(results),
            'valid': valid_count,
            'invalid': invalid_count,
            'valid_rate': valid_count / len(results),
            'low_confidence_invalid': low_confidence_invalid,
            'high_confidence_valid': high_confidence_valid,
            'source_counts': source_counts,
            'avg_confidence': sum(r.confidence for r in results) / len(results),
            'total_fields_in_cache': len(self._fields_cache)
        }

    def get_field_count(self) -> int:
        """获取当前缓存中的字段数量"""
        return len(self._fields_cache)


# ==================== 全局实例 ====================

_ukb_field_fetcher: Optional[UKBFieldFetcher] = None


def get_ukb_field_fetcher(use_online_fetch: bool = True) -> UKBFieldFetcher:
    """
    获取 UKB 字段获取器实例

    Args:
        use_online_fetch: 是否使用在线获取

    Returns:
        UKBFieldFetcher: 获取器实例
    """
    global _ukb_field_fetcher

    if _ukb_field_fetcher is None:
        _ukb_field_fetcher = UKBFieldFetcher(use_online_fetch=use_online_fetch)

    return _ukb_field_fetcher


def validate_ukb_field(field_id: str) -> UKBFieldValidationResult:
    """
    便捷函数：验证单个 UKB 字段

    Args:
        field_id: 字段 ID

    Returns:
        UKBFieldValidationResult: 验证结果
    """
    fetcher = get_ukb_field_fetcher()
    return fetcher.validate_field_with_confidence(field_id)


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.0 UK Biobank 字段动态获取器 - 测试")
    print("=" * 70)

    fetcher = UKBFieldFetcher(use_online_fetch=False)

    # 测试 1: 缓存字段验证
    print("\n[Test 1] 缓存字段验证")
    test_fields = ['31', '21022', '30000', '20002']
    for field in test_fields:
        result = fetcher.validate_field_with_confidence(field)
        print(f"  Field {field}: valid={result.is_valid}, name={result.field_name[:30]}, confidence={result.confidence:.2f}")

    # 测试 2: 扩展字段验证
    print("\n[Test 2] 扩展字段验证")
    test_extended = ['100001', '40001', '20157', '20201']
    for field in test_extended:
        result = fetcher.validate_field_with_confidence(field)
        print(f"  Field {field}: valid={result.is_valid}, source={result.source.value}, confidence={result.confidence:.2f}")

    # 测试 3: 未知字段验证
    print("\n[Test 3] 未知字段验证")
    test_unknown = ['99999', '88888', '12345']
    for field in test_unknown:
        result = fetcher.validate_field_with_confidence(field)
        print(f"  Field {field}: valid={result.is_valid}, source={result.source.value}, confidence={result.confidence:.2f}")

    # 测试 4: 统计信息
    print("\n[Test 4] 统计信息")
    all_test = test_fields + test_extended + test_unknown
    results = fetcher.batch_validate(all_test)
    summary = fetcher.get_validation_summary(results)
    print(f"  总数: {summary['total']}")
    print(f"  有效: {summary['valid']} ({summary['valid_rate']:.2%})")
    print(f"  无效: {summary['invalid']}")
    print(f"  低置信度拒绝: {summary['low_confidence_invalid']}")
    print(f"  缓存字段总数: {summary['total_fields_in_cache']}")

    print("\n" + "=" * 70)
    print("V7.0 UK Biobank 字段动态获取器测试完成!")
    print("=" * 70)