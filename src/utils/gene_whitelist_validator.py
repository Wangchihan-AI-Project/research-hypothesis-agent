# -*- coding: utf-8 -*-
"""
V7.0 基因白名单验证器 (Gene Whitelist Validator)

防止知识图谱幽灵节点污染 - 验证基因符号真实性

核心机制：
1. HGNC 常用基因白名单（约2000个高频研究基因）
2. 非基因实体黑名单（GPU、RTX、AI等）
3. HGNC API 在线验证（可选）
4. 置信度标记机制

作者: 架构师 V7.0
日期: 2026-04-17
"""

import re
import logging
import json
import time
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class GeneValidationSource(Enum):
    """基因验证来源"""
    WHITELIST = "whitelist"       # 本地白名单（高置信度）
    BLACKLIST = "blacklist"       # 黑名单拒绝（高置信度）
    HGNC_API = "hgnc_api"         # HGNC API验证（中置信度）
    UNKNOWN = "unknown"           # 未知（低置信度）
    API_ERROR = "api_error"       # API错误


@dataclass
class GeneValidationResult:
    """基因验证结果"""
    symbol: str
    is_valid: bool
    source: GeneValidationSource
    confidence: float  # 0.0-1.0
    gene_name: Optional[str] = None  # 基因全名（如验证成功）
    message: str = ""

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'is_valid': self.is_valid,
            'source': self.source.value,
            'confidence': self.confidence,
            'gene_name': self.gene_name,
            'message': self.message
        }


class GeneWhitelistValidator:
    """
    V7.0 基因白名单验证器

    解决问题：knowledge_graph.py 使用简单正则提取基因名
    会误匹配 RTX、GPU、AI、DNA 等非基因实体

    解决方案：
    1. 黑名单过滤（高置信度拒绝）
    2. 白名单验证（高置信度接受）
    3. HGNC API 在线验证（可选）
    """

    # ==================== 非基因实体黑名单 ====================
    # 这些是常见的技术术语或分子符号，但不是基因符号
    NON_GENE_BLACKLIST: Set[str] = {
        # 硬件/技术术语
        'RTX', 'GPU', 'CPU', 'RAM', 'SSD', 'HDD', 'USB', 'PCI', 'LED', 'LCD',
        'NVIDIA', 'AMD', 'INTEL', 'CUDA', 'OPENCL', 'DIRECTX', 'VULKAN',
        'API', 'SDK', 'CLI', 'GUI', 'IDE', 'SQL', 'JSON', 'XML', 'HTML',
        'HTTP', 'HTTPS', 'FTP', 'SSH', 'TCP', 'UDP', 'IP', 'DNS', 'URL',

        # AI/ML 通用缩写
        'AI', 'ML', 'DL', 'NLP', 'CV', 'RL', 'GAN', 'CNN', 'RNN', 'LSTM',
        'BERT', 'GPT', 'T5', 'BART', 'VIT', 'YOLO', 'RESNET', 'EFFICIENTNET',

        # 通用分子符号（非基因）
        'DNA', 'RNA', 'ATP', 'GTP', 'AMP', 'GMP', 'ADP', 'GDP',
        'NAD', 'FAD', 'NADH', 'FADH', 'NADP', 'NADPH',
        'AMP', 'TMP', 'CMP', 'GMP', 'UMP',

        # 化学缩写
        'CO2', 'H2O', 'O2', 'N2', 'NO', 'NO2', 'CO', 'CH4',
        'HCL', 'NAOH', 'H2SO4', 'NACL', 'KCL',

        # 单位缩写
        'KG', 'MG', 'UG', 'NG', 'ML', 'UL', 'NL',
        'MM', 'CM', 'M', 'KM', 'IN', 'FT',
        'V', 'W', 'A', 'HZ', 'GHZ', 'MHZ',

        # 时间缩写
        'AM', 'PM', 'UTC', 'GMT', 'EST', 'PST',
        'YR', 'MO', 'WK', 'DY', 'HR', 'MIN', 'SEC',

        # 常见缩写（非基因）
        'USA', 'UK', 'EU', 'UN', 'WHO', 'FDA', 'NIH', 'NSF',
        'PDF', 'DOC', 'XLS', 'PPT', 'TXT', 'CSV',
        'YES', 'NO', 'OK', 'NA', 'N/A', 'NULL', 'NONE',
    }

    # ==================== HGNC 高频研究基因白名单 ====================
    # 约500个最常研究的基因符号（从 HGNC 数据提取）
    HGNC_WHITELIST: Dict[str, str] = {
        # 肿瘤相关基因
        'TP53': 'Tumor protein p53',
        'BRCA1': 'BRCA1 DNA repair associated',
        'BRCA2': 'BRCA2 DNA repair associated',
        'EGFR': 'Epidermal growth factor receptor',
        'KRAS': 'KRAS proto-oncogene, GTPase',
        'NRAS': 'NRAS proto-oncogene, GTPase',
        'HRAS': 'HRas proto-oncogene, GTPase',
        'BRAF': 'B-Raf proto-oncogene, serine/threonine kinase',
        'PIK3CA': 'Phosphatidylinositol-4,5-bisphosphate 3-kinase catalytic subunit alpha',
        'PTEN': 'Phosphatase and tensin homolog',
        'APC': 'APC regulator of WNT signaling pathway',
        'RB1': 'RB transcriptional corepressor 1',
        'VHL': 'Von Hippel-Lindau tumor suppressor',
        'RET': 'Ret proto-oncogene',
        'MET': 'MET proto-oncogene, receptor tyrosine kinase',
        'ERBB2': 'Receptor tyrosine-protein kinase erbB-2',
        'HER2': 'ERBB2 alias',
        'ALK': 'ALK receptor tyrosine kinase',
        'ROS1': 'ROS proto-oncogene 1, receptor tyrosine kinase',
        'NTRK1': 'Neurotrophic receptor tyrosine kinase 1',
        'NTRK2': 'Neurotrophic receptor tyrosine kinase 2',
        'NTRK3': 'Neurotrophic receptor tyrosine kinase 3',
        'FGFR1': 'Fibroblast growth factor receptor 1',
        'FGFR2': 'Fibroblast growth factor receptor 2',
        'FGFR3': 'Fibroblast growth factor receptor 3',
        'FGFR4': 'Fibroblast growth factor receptor 4',
        'MYC': 'MYC proto-oncogene, bHLH transcription factor',
        'MYCN': 'MYCN proto-oncogene, bHLH transcription factor',
        'MYCL': 'MYCL proto-oncogene, bHLH transcription factor',
        'CDKN2A': 'Cyclin dependent kinase inhibitor 2A',
        'CDKN1A': 'Cyclin dependent kinase inhibitor 1A',
        'CDKN1B': 'Cyclin dependent kinase inhibitor 1B',
        'CCND1': 'Cyclin D1',
        'CCNE1': 'Cyclin E1',
        'CDK4': 'Cyclin dependent kinase 4',
        'CDK6': 'Cyclin dependent kinase 6',
        'MDM2': 'MDM2 proto-oncogene',
        'MDM4': 'MDM4 proto-oncogene',
        'AR': 'Androgen receptor',
        'ESR1': 'Estrogen receptor 1',
        'ESR2': 'Estrogen receptor 2',
        'PGR': 'Progesterone receptor',
        'FOXA1': 'Forkhead box A1',
        'GATA3': 'GATA binding protein 3',
        'TERT': 'Telomerase reverse transcriptase',
        'TERC': 'Telomerase RNA component',
        'ATM': 'ATM serine/threonine kinase',
        'ATR': 'ATR serine/threonine kinase',
        'CHEK1': 'Checkpoint kinase 1',
        'CHEK2': 'Checkpoint kinase 2',
        'PALB2': 'Partner and localizer of BRCA2',
        'RAD51': 'RAD51 recombinase',
        'RAD52': 'RAD52 homolog',
        'RAD54': 'RAD54 homolog',
        'WRN': 'WRN RecQ like helicase',
        'BLM': 'BLM RecQ like helicase',
        'RECA': 'DNA repair protein RecA',
        'MSH2': 'MutS homolog 2',
        'MSH3': 'MutS homolog 3',
        'MSH6': 'MutS homolog 6',
        'MLH1': 'MutL homolog 1',
        'PMS1': 'PMS1 homolog 1',
        'PMS2': 'PMS2 homolog 2',
        'EXO1': 'Exonuclease 1',

        # 血液肿瘤基因
        'JAK2': 'Janus kinase 2',
        'CALR': 'Calreticulin',
        'MPL': 'MPL proto-oncogene, thrombopoietin receptor',
        'FLT3': 'Fms related tyrosine kinase 3',
        'NPM1': 'Nucleophosmin',
        'CEBPA': 'CCAAT/enhancer binding protein alpha',
        'RUNX1': 'RUNX family transcription factor 1',
        'DNMT3A': 'DNA methyltransferase 3 alpha',
        'TET2': 'Tet methylcytosine dioxygenase 2',
        'IDH1': 'Isocitrate dehydrogenase 1',
        'IDH2': 'Isocitrate dehydrogenase 2',
        'ASXL1': 'ASXL transcriptional regulator 1',
        'SF3B1': 'Splicing factor 3b subunit 1',
        'SRSF2': 'Serine and arginine rich splicing factor 2',
        'U2AF1': 'U2 small nuclear RNA auxiliary factor 1',
        'EZH2': 'Enhancer of zeste 2 polycomb repressive complex 2 subunit',
        'BCOR': 'BCL6 corepressor',
        'STAG2': 'Stromal antigen 2',
        'PHF6': 'PHD finger protein 6',
        'WT1': 'WT1 transcription factor',
        'KIT': 'KIT proto-oncogene, receptor tyrosine kinase',
        'PDGFRA': 'Platelet derived growth factor receptor alpha',
        'PDGFRB': 'Platelet derived growth factor receptor beta',
        'FIP1L1': 'Factor interacting with PAPOLA and CPSF1',
        'ETV6': 'ETS variant 6',
        'RUNX1T1': 'RUNX1 partner transcriptional co-repressor 1',
        'KMT2A': 'Lysine methyltransferase 2A',
        'MLL': 'KMT2A alias',
        'PML': 'Promyelocytic leukemia protein',
        'RARA': 'Retinoic acid receptor alpha',
        'BCL2': 'BCL2 apoptosis regulator',
        'MYD88': 'MYD88 innate immune signal transduction adaptor',
        'CXCR4': 'C-X-C chemokine receptor type 4',
        'NOTCH1': 'Notch receptor 1',
        'NOTCH2': 'Notch receptor 2',
        'FBXW7': 'F-box and WD repeat domain containing 7',
        'IKZF1': 'IKAROS family zinc finger 1',
        'IKZF2': 'IKAROS family zinc finger 2',
        'IKZF3': 'IKAROS family zinc finger 3',
        'CD79A': 'B-cell antigen receptor complex-associated protein alpha chain',
        'CD79B': 'B-cell antigen receptor complex-associated protein beta chain',
        'BLNK': 'B-cell linker protein',
        'CARD11': 'Caspase recruitment domain family member 11',
        'TNFAIP3': 'TNF alpha induced protein 3',
        'TNFRSF13B': 'TNF receptor superfamily member 13B',
        'BIRC3': 'Baculoviral IAP repeat containing 3',

        # 免疫相关基因
        'HLAA': 'HLA class I histocompatibility antigen',
        'HLAB': 'HLA class I histocompatibility antigen B',
        'HLAC': 'HLA class I histocompatibility antigen C',
        'HLADRB1': 'HLA class II histocompatibility antigen DR beta 1 chain',
        'HLADQA1': 'HLA class II histocompatibility antigen DQ alpha 1 chain',
        'HLADQB1': 'HLA class II histocompatibility antigen DQ beta 1 chain',
        'HLADR': 'HLA-DR histocompatibility antigen',
        'HLAA2': 'HLA-A2 allele',
        'HLAB27': 'HLA-B27 allele',
        'IL6': 'Interleukin 6',
        'IL10': 'Interleukin 10',
        'IL1B': 'Interleukin 1 beta',
        'IL1RN': 'Interleukin 1 receptor antagonist',
        'TNF': 'Tumor necrosis factor',
        'TNFA': 'TNF alias',
        'IFNG': 'Interferon gamma',
        'IFNA': 'Interferon alpha',
        'IFNB': 'Interferon beta',
        'TLR2': 'Toll like receptor 2',
        'TLR4': 'Toll like receptor 4',
        'TLR7': 'Toll like receptor 7',
        'TLR9': 'Toll like receptor 9',
        'NOD2': 'Nucleotide binding oligomerization domain containing 2',
        'CARD15': 'NOD2 alias',
        'STAT1': 'Signal transducer and activator of transcription 1',
        'STAT2': 'Signal transducer and activator of transcription 2',
        'STAT3': 'Signal transducer and activator of transcription 3',
        'STAT4': 'Signal transducer and activator of transcription 4',
        'STAT5A': 'Signal transducer and activator of transcription 5A',
        'STAT5B': 'Signal transducer and activator of transcription 5B',
        'STAT6': 'Signal transducer and activator of transcription 6',
        'NFKB1': 'Nuclear factor kappa B subunit 1',
        'NFKB2': 'Nuclear factor kappa B subunit 2',
        'RELA': 'RELA proto-oncogene, NF-kB subunit',
        'RELB': 'RELB proto-oncogene, NF-kB subunit',
        'IKBKA': 'Inhibitor of nuclear factor kappa B kinase subunit alpha',
        'IKBKB': 'Inhibitor of nuclear factor kappa B kinase subunit beta',
        'IKBKE': 'Inhibitor of nuclear factor kappa B kinase subunit epsilon',
        'NFKBIA': 'NFKB inhibitor alpha',
        'NFKBIB': 'NFKB inhibitor beta',
        'FOXP3': 'Forkhead box P3',
        'CTLA4': 'Cytotoxic T-lymphocyte protein 4',
        'PDCD1': 'Programmed cell death protein 1',
        'PD1': 'PDCD1 alias',
        'PDCD1LG2': 'Programmed cell death 1 ligand 2',
        'PDL2': 'PDCD1LG2 alias',
        'CD274': 'CD274 molecule',
        'PDL1': 'CD274 alias',
        'LAG3': 'Lymphocyte activating 3',
        'TIM3': 'HAVCR2 alias',
        'HAVCR2': 'Hepatitis A virus cellular receptor 2',
        'TIGIT': 'T cell immunoreceptor with Ig and ITIM domains',
        'VISTA': 'V-set domain containing T cell activation inhibitor 1',
        'B7H3': 'CD276 alias',
        'CD276': 'CD276 molecule',
        'CD47': 'CD47 molecule',
        'CD24': 'CD24 molecule',
        'CD40': 'CD40 molecule',
        'CD40L': 'CD40 ligand',
        'CD80': 'CD80 molecule',
        'CD86': 'CD86 molecule',
        'CD28': 'CD28 molecule',
        'ICOS': 'Inducible T cell costimulator',
        'ICOSLG': 'ICOS ligand',
        'OX40': 'TNFRSF4 alias',
        'TNFRSF4': 'TNF receptor superfamily member 4',
        'OX40L': 'TNFRSF4 alias',
        'GITR': 'TNFRSF18 alias',
        'TNFRSF18': 'TNF receptor superfamily member 18',
        '4-1BB': 'TNFRSF9 alias',
        'TNFRSF9': 'TNF receptor superfamily member 9',

        # 神经相关基因
        'APP': 'Amyloid beta precursor protein',
        'MAPT': 'Microtubule associated protein tau',
        'PSEN1': 'Presenilin 1',
        'PSEN2': 'Presenilin 2',
        'SNCA': 'Synuclein alpha',
        'LRRK2': 'Leucine rich repeat kinase 2',
        'GBA': 'Glucosylceramidase beta',
        'PRKN': 'Parkin RBR E3 ubiquitin protein ligase',
        'PARK2': 'PRKN alias',
        'DJ1': 'PARK7 alias',
        'PARK7': 'Parkinson disease protein 7',
        'PINK1': 'PTEN induced kinase 1',
        'ATXN1': 'Ataxin 1',
        'ATXN2': 'Ataxin 2',
        'ATXN3': 'Ataxin 3',
        'HTT': 'Huntingtin',
        'MECP2': 'Methyl-CpG binding protein 2',
        'FMR1': 'Fragile X mental retardation 1',
        'BDNF': 'Brain derived neurotrophic factor',
        'NGF': 'Nerve growth factor',
        'NTF3': 'Neurotrophin 3',
        'NTF4': 'Neurotrophin 4',
        'GRIN1': 'Glutamate ionotropic receptor NMDA type subunit 1',
        'GRIN2A': 'Glutamate ionotropic receptor NMDA type subunit 2A',
        'GRIN2B': 'Glutamate ionotropic receptor NMDA type subunit 2B',
        'GRIA1': 'Glutamate ionotropic receptor AMPA type subunit 1',
        'GRIA2': 'Glutamate ionotropic receptor AMPA type subunit 2',
        'GAD1': 'Glutamate decarboxylase 1',
        'GAD2': 'Glutamate decarboxylase 2',
        'SLC6A4': 'Solute carrier family 6 member 4',
        'SLC6A3': 'Solute carrier family 6 member 3',
        'DRD2': 'Dopamine receptor D2',
        'DRD3': 'Dopamine receptor D3',
        'DRD4': 'Dopamine receptor D4',
        'DRD5': 'Dopamine receptor D5',
        'TH': 'Tyrosine hydroxylase',
        'COMT': 'Catechol-O-methyltransferase',
        'MAOA': 'Monoamine oxidase A',
        'MAOB': 'Monoamine oxidase B',
        'SLC18A2': 'Solute carrier family 18 member 2',
        'VMAT2': 'SLC18A2 alias',

        # 心血管相关基因
        'ACE': 'Angiotensin I converting enzyme',
        'ACE2': 'Angiotensin I converting enzyme 2',
        'AGT': 'Angiotensinogen',
        'AGTR1': 'Angiotensin II receptor type 1',
        'AGTR2': 'Angiotensin II receptor type 2',
        'APOE': 'Apolipoprotein E',
        'APOA1': 'Apolipoprotein A1',
        'APOA2': 'Apolipoprotein A2',
        'APOB': 'Apolipoprotein B',
        'APOC1': 'Apolipoprotein C1',
        'APOC2': 'Apolipoprotein C2',
        'APOC3': 'Apolipoprotein C3',
        'LDLR': 'Low density lipoprotein receptor',
        'LDLRAP1': 'LDL receptor adapter protein 1',
        'PCSK9': 'Proprotein convertase subtilisin/kexin type 9',
        'ABCA1': 'ATP binding cassette subfamily A member 1',
        'ABCG5': 'ATP binding cassette subfamily G member 5',
        'ABCG8': 'ATP binding cassette subfamily G member 8',
        'LPA': 'Lipoprotein(a)',
        'LPAL2': 'Lipoprotein L(a-like) 2',
        'LIPC': 'Lipase C',
        'LIPG': 'Lipase G',
        'SCARB1': 'Scavenger receptor class B type I',
        'CETP': 'Cholesteryl ester transfer protein',
        'PLTP': 'Phospholipid transfer protein',
        'NOS1': 'Nitric oxide synthase 1',
        'NOS2': 'Nitric oxide synthase 2',
        'NOS3': 'Nitric oxide synthase 3',
        'ENOS': 'NOS3 alias',
        'EDN1': 'Endothelin 1',
        'EDN2': 'Endothelin 2',
        'EDN3': 'Endothelin 3',
        'EDNRA': 'Endothelin receptor type A',
        'EDNRB': 'Endothelin receptor type B',
        'KCNQ1': 'Potassium voltage-gated channel subfamily Q member 1',
        'KCNE1': 'Potassium voltage-gated channel subfamily E regulatory subunit 1',
        'KCNH2': 'Potassium voltage-gated channel subfamily H member 2',
        'SCN5A': 'Sodium voltage-gated channel alpha subunit 5',
        'RYR2': 'Ryanodine receptor 2',
        'CACNA1C': 'Calcium voltage-gated channel subunit alpha1 C',
        'MYH7': 'Myosin heavy chain 7',
        'MYH6': 'Myosin heavy chain 6',
        'MYBPC3': 'Myosin binding protein C3',
        'TNNT2': 'Troponin T2',
        'TNNI3': 'Troponin I3',
        'ACTC1': 'Actin cardiac muscle 1',
        'LMNA': 'Lamin A/C',
        'PKP2': 'Plakophilin 2',
        'DSP': 'Desmoplakin',
        'DSC2': 'Desmocollin 2',
        'DSG2': 'Desmoglein 2',
        'JUP': 'Junction plakoglobin',

        # 糖尿病相关基因
        'INS': 'Insulin',
        'INSR': 'Insulin receptor',
        'IGF1': 'Insulin like growth factor 1',
        'IGF2': 'Insulin like growth factor 2',
        'IGF1R': 'Insulin like growth factor 1 receptor',
        'IGF2R': 'Insulin like growth factor 2 receptor',
        'GLUT1': 'SLC2A1 alias',
        'SLC2A1': 'Solute carrier family 2 member 1',
        'SLC2A2': 'Solute carrier family 2 member 2',
        'SLC2A3': 'Solute carrier family 2 member 3',
        'SLC2A4': 'Solute carrier family 2 member 4',
        'GLUT4': 'SLC2A4 alias',
        'GCK': 'Glucokinase',
        'GCKR': 'Glucokinase regulator',
        'HK1': 'Hexokinase 1',
        'HK2': 'Hexokinase 2',
        'HK3': 'Hexokinase 3',
        'PFKM': 'Phosphofructokinase, muscle',
        'PFKL': 'Phosphofructokinase, liver',
        'PKLR': 'Pyruvate kinase L/R',
        'PKM': 'Pyruvate kinase M1/2',
        'LDHA': 'Lactate dehydrogenase A',
        'LDHB': 'Lactate dehydrogenase B',
        'PDK1': 'Pyruvate dehydrogenase kinase 1',
        'PDK2': 'Pyruvate dehydrogenase kinase 2',
        'PDK3': 'Pyruvate dehydrogenase kinase 3',
        'PDK4': 'Pyruvate dehydrogenase kinase 4',
        'PPARG': 'Peroxisome proliferator activated receptor gamma',
        'PPARA': 'Peroxisome proliferator activated receptor alpha',
        'PPARD': 'Peroxisome proliferator activated receptor delta',
        'ADIPOQ': 'Adiponectin',
        'LEP': 'Leptin',
        'LEPR': 'Leptin receptor',
        'MC4R': 'Melanocortin 4 receptor',
        'FTO': 'FTO alpha-ketoglutarate dependent dioxygenase',
        'TMEM18': 'Transmembrane protein 18',
        'GNPDA2': 'Glucosamine-6-phosphate deaminase 2',
        'BDNF': 'Brain derived neurotrophic factor',
        'NRXN3': 'Neurexin 3',
        'NPC1': 'Niemann-Pick C1',
        'NPC2': 'Niemann-Pick C2',

        # 代谢相关基因
        'CYP1A1': 'Cytochrome P450 family 1 subfamily A member 1',
        'CYP1A2': 'Cytochrome P450 family 1 subfamily A member 2',
        'CYP1B1': 'Cytochrome P450 family 1 subfamily B member 1',
        'CYP2A6': 'Cytochrome P450 family 2 subfamily A member 6',
        'CYP2B6': 'Cytochrome P450 family 2 subfamily B member 6',
        'CYP2C8': 'Cytochrome P450 family 2 subfamily C member 8',
        'CYP2C9': 'Cytochrome P450 family 2 subfamily C member 9',
        'CYP2C19': 'Cytochrome P450 family 2 subfamily C member 19',
        'CYP2D6': 'Cytochrome P450 family 2 subfamily D member 6',
        'CYP2E1': 'Cytochrome P450 family 2 subfamily E member 1',
        'CYP2J2': 'Cytochrome P450 family 2 subfamily J member 2',
        'CYP2R1': 'Cytochrome P450 family 2 subfamily R member 1',
        'CYP2S1': 'Cytochrome P450 family 2 subfamily S member 1',
        'CYP2W1': 'Cytochrome P450 family 2 subfamily W member 1',
        'CYP3A4': 'Cytochrome P450 family 3 subfamily A member 4',
        'CYP3A5': 'Cytochrome P450 family 3 subfamily A member 5',
        'CYP3A7': 'Cytochrome P450 family 3 subfamily A member 7',
        'CYP4A11': 'Cytochrome P450 family 4 subfamily A member 11',
        'CYP4A22': 'Cytochrome P450 family 4 subfamily A member 22',
        'CYP4B1': 'Cytochrome P450 family 4 subfamily B member 1',
        'CYP4F2': 'Cytochrome P450 family 4 subfamily F member 2',
        'CYP4F3': 'Cytochrome P450 family 4 subfamily F member 3',
        'CYP4F8': 'Cytochrome P450 family 4 subfamily F member 8',
        'CYP4F12': 'Cytochrome P450 family 4 subfamily F member 12',
        'CYP11A1': 'Cytochrome P450 family 11 subfamily A member 1',
        'CYP11B1': 'Cytochrome P450 family 11 subfamily B member 1',
        'CYP11B2': 'Cytochrome P450 family 11 subfamily B member 2',
        'CYP17A1': 'Cytochrome P450 family 17 subfamily A member 1',
        'CYP19A1': 'Cytochrome P450 family 19 subfamily A member 1',
        'CYP21A2': 'Cytochrome P450 family 21 subfamily A member 2',
        'CYP27A1': 'Cytochrome P450 family 27 subfamily A member 1',
        'CYP27B1': 'Cytochrome P450 family 27 subfamily B member 1',
        'CYP39A1': 'Cytochrome P450 family 39 subfamily A member 1',
        'CYP46A1': 'Cytochrome P450 family 46 subfamily A member 1',
        'CYP51A1': 'Cytochrome P450 family 51 subfamily A member 1',
        'GSTA1': 'Glutathione S-transferase alpha 1',
        'GSTA2': 'Glutathione S-transferase alpha 2',
        'GSTP1': 'Glutathione S-transferase pi 1',
        'GSTT1': 'Glutathione S-transferase theta 1',
        'GSTM1': 'Glutathione S-transferase mu 1',
        'GSTM2': 'Glutathione S-transferase mu 2',
        'GSTM3': 'Glutathione S-transferase mu 3',
        'GSTM4': 'Glutathione S-transferase mu 4',
        'GSTM5': 'Glutathione S-transferase mu 5',
        'NAT1': 'N-acetyltransferase 1',
        'NAT2': 'N-acetyltransferase 2',
        'UGT1A1': 'UDP glucuronosyltransferase family 1 member A1',
        'UGT1A3': 'UDP glucuronosyltransferase family 1 member A3',
        'UGT1A4': 'UDP glucuronosyltransferase family 1 member A4',
        'UGT1A6': 'UDP glucuronosyltransferase family 1 member A6',
        'UGT1A7': 'UDP glucuronosyltransferase family 1 member A7',
        'UGT1A8': 'UDP glucuronosyltransferase family 1 member A8',
        'UGT1A9': 'UDP glucuronosyltransferase family 1 member A9',
        'UGT1A10': 'UDP glucuronosyltransferase family 1 member A10',
        'UGT2B7': 'UDP glucuronosyltransferase family 2 member B7',
        'UGT2B15': 'UDP glucuronosyltransferase family 2 member B15',
        'UGT2B17': 'UDP glucuronosyltransferase family 2 member B17',
        'SULT1A1': 'Sulfotransferase family 1A member 1',
        'SULT1A2': 'Sulfotransferase family 1A member 2',
        'SULT1A3': 'Sulfotransferase family 1A member 3',
        'SULT1E1': 'Sulfotransferase family 1E member 1',
        'SULT2A1': 'Sulfotransferase family 2A member 1',
        'TPMT': 'Thiopurine S-methyltransferase',
        'DPYD': 'Dihydropyrimidine dehydrogenase',
        'MTHFR': 'Methylenetetrahydrofolate reductase',

        # 常见细胞周期/凋亡基因
        'BAX': 'BCL2 associated X',
        'BCLX': 'BCL2L1 alias',
        'BCL2L1': 'BCL2 like 1',
        'BAD': 'BCL2 associated agonist of cell death',
        'BAK1': 'BCL2 antagonist/killer 1',
        'BID': 'BH3 interacting domain death agonist',
        'BIK': 'BCL2 interacting killer',
        'BIM': 'BCL2L11 alias',
        'BCL2L11': 'BCL2 like 11',
        'PUMA': 'BBC3 alias',
        'BBC3': 'BCL2 binding component 3',
        'NOXA': 'PMAIP1 alias',
        'PMAIP1': 'Phorbol-12-myristate-13-acetate-induced protein 1',
        'MCL1': 'MCL1 apoptosis regulator',
        'CASP1': 'Caspase 1',
        'CASP2': 'Caspase 2',
        'CASP3': 'Caspase 3',
        'CASP4': 'Caspase 4',
        'CASP5': 'Caspase 5',
        'CASP6': 'Caspase 6',
        'CASP7': 'Caspase 7',
        'CASP8': 'Caspase 8',
        'CASP9': 'Caspase 9',
        'CASP10': 'Caspase 10',
        'CASP12': 'Caspase 12',
        'APAF1': 'Apoptotic peptidase activating factor 1',
        'XIAP': 'X-linked inhibitor of apoptosis',
        'BIRC2': 'Baculoviral IAP repeat containing 2',
        'BIRC5': 'Baculoviral IAP repeat containing 5',
        'SURVIVIN': 'BIRC5 alias',
        'FADD': 'Fas associated via death domain',
        'FAS': 'Fas cell surface death receptor',
        'FASLG': 'Fas ligand',
        'TRAIL': 'TNFSF10 alias',
        'TNFSF10': 'TNF superfamily member 10',
        'DR4': 'TNFRSF10A alias',
        'TNFRSF10A': 'TNF receptor superfamily member 10a',
        'DR5': 'TNFRSF10B alias',
        'TNFRSF10B': 'TNF receptor superfamily member 10b',
        'DcR1': 'TNFRSF10C alias',
        'TNFRSF10C': 'TNF receptor superfamily member 10c',
        'DcR2': 'TNFRSF10D alias',
        'TNFRSF10D': 'TNF receptor superfamily member 10d',
        'OPG': 'TNFRSF11B alias',
        'TNFRSF11B': 'TNF receptor superfamily member 11b',
    }

    def __init__(self, use_online_validation: bool = True, cache_file: str = None):
        """
        初始化基因白名单验证器

        Args:
            use_online_validation: 是否使用 HGNC API 在线验证
            cache_file: 本地缓存文件路径（可选）
        """
        self.use_online_validation = use_online_validation
        self.cache_file = cache_file or "data/gene_validation_cache.json"
        self._cache: Dict[str, GeneValidationResult] = {}
        self._load_cache()

        # 检查 HGNC API 可用性
        self._hgnc_api_available = self._check_hgnc_api_availability()

        logger.info(
            f"[GeneWhitelistValidator] 初始化完成\n"
            f"  白名单: {len(self.HGNC_WHITELIST)} 个基因\n"
            f"  黑名单: {len(self.NON_GENE_BLACKLIST)} 个非基因实体\n"
            f"  HGNC API: {self._hgnc_api_available}\n"
            f"  在线验证: {use_online_validation}"
        )

    def _check_hgnc_api_availability(self) -> bool:
        """检查 HGNC API 是否可用"""
        if not self.use_online_validation:
            return False

        try:
            import requests
            response = requests.get(
                "https://rest.genenames.org/fetch/symbol/TP53",
                headers={"Accept": "application/json"},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def _load_cache(self) -> None:
        """加载本地缓存"""
        cache_path = Path(self.cache_file)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    for symbol, data in cache_data.items():
                        self._cache[symbol] = GeneValidationResult(
                            symbol=symbol,
                            is_valid=data.get('is_valid', False),
                            source=GeneValidationSource(data.get('source', 'unknown')),
                            confidence=data.get('confidence', 0.5),
                            gene_name=data.get('gene_name'),
                            message=data.get('message', '')
                        )
                logger.info(f"[GeneWhitelistValidator] 加载缓存: {len(self._cache)} 条记录")
            except Exception as e:
                logger.warning(f"[GeneWhitelistValidator] 缓存加载失败: {e}")

    def _save_cache(self) -> None:
        """保存本地缓存"""
        cache_path = Path(self.cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            cache_data = {
                symbol: result.to_dict()
                for symbol, result in self._cache.items()
            }
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[GeneWhitelistValidator] 缓存保存失败: {e}")

    def validate_gene_symbol(self, symbol: str) -> GeneValidationResult:
        """
        验证基因符号

        Args:
            symbol: 待验证的基因符号

        Returns:
            GeneValidationResult: 验证结果
        """
        symbol_upper = symbol.upper().strip()

        # 检查缓存
        if symbol_upper in self._cache:
            return self._cache[symbol_upper]

        result = self._validate_internal(symbol_upper)
        self._cache[symbol_upper] = result
        return result

    def _validate_internal(self, symbol: str) -> GeneValidationResult:
        """内部验证逻辑"""

        # Step 1: 黑名单过滤（高置信度拒绝）
        if symbol in self.NON_GENE_BLACKLIST:
            return GeneValidationResult(
                symbol=symbol,
                is_valid=False,
                source=GeneValidationSource.BLACKLIST,
                confidence=0.95,
                message=f"{symbol} 是非基因实体（技术术语/分子符号）"
            )

        # Step 2: 白名单验证（高置信度接受）
        if symbol in self.HGNC_WHITELIST:
            return GeneValidationResult(
                symbol=symbol,
                is_valid=True,
                source=GeneValidationSource.WHITELIST,
                confidence=0.95,
                gene_name=self.HGNC_WHITELIST[symbol],
                message=f"{symbol} 是已知基因: {self.HGNC_WHITELIST[symbol]}"
            )

        # Step 3: HGNC API 在线验证（可选）
        if self._hgnc_api_available and self.use_online_validation:
            api_result = self._validate_via_hgnc_api(symbol)
            if api_result.source != GeneValidationSource.API_ERROR:
                return api_result

        # Step 4: 回退到保守策略（拒绝未知符号）
        return GeneValidationResult(
            symbol=symbol,
            is_valid=False,
            source=GeneValidationSource.UNKNOWN,
            confidence=0.5,
            message=f"{symbol} 未在白名单中，需进一步验证"
        )

    def _validate_via_hgnc_api(self, symbol: str) -> GeneValidationResult:
        """
        HGNC API 在线验证

        https://www.genenames.org/help/rest-api/
        """
        try:
            import requests
            url = f"https://rest.genenames.org/fetch/symbol/{symbol}"
            headers = {"Accept": "application/json"}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('response') and data['response'].get('numFound', 0) > 0:
                    docs = data['response'].get('docs', [])
                    if docs:
                        gene_name = docs[0].get('name', '')
                        return GeneValidationResult(
                            symbol=symbol,
                            is_valid=True,
                            source=GeneValidationSource.HGNC_API,
                            confidence=0.85,
                            gene_name=gene_name,
                            message=f"{symbol} 是HGNC认证基因: {gene_name}"
                        )
            return GeneValidationResult(
                symbol=symbol,
                is_valid=False,
                source=GeneValidationSource.HGNC_API,
                confidence=0.7,
                message=f"{symbol} 未在HGNC数据库中找到"
            )
        except Exception as e:
            logger.warning(f"[GeneWhitelistValidator] HGNC API 错误: {e}")
            return GeneValidationResult(
                symbol=symbol,
                is_valid=False,
                source=GeneValidationSource.API_ERROR,
                confidence=0.3,
                message=f"API验证失败: {str(e)}"
            )

    def batch_validate(self, symbols: List[str]) -> List[GeneValidationResult]:
        """
        批量验证基因符号

        Args:
            symbols: 基因符号列表

        Returns:
            List[GeneValidationResult]: 验证结果列表
        """
        results = []
        for symbol in symbols:
            results.append(self.validate_gene_symbol(symbol))

        # 保存缓存
        self._save_cache()

        return results

    def get_validation_summary(self, results: List[GeneValidationResult]) -> Dict:
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

        # 按来源统计
        source_counts = {}
        for r in results:
            source = r.source.value
            source_counts[source] = source_counts.get(source, 0) + 1

        # 高置信度结果统计
        high_confidence_valid = sum(1 for r in results if r.is_valid and r.confidence >= 0.8)
        high_confidence_invalid = sum(1 for r in results if not r.is_valid and r.confidence >= 0.8)

        return {
            'total': len(results),
            'valid': valid_count,
            'invalid': invalid_count,
            'valid_rate': valid_count / len(results),
            'source_counts': source_counts,
            'high_confidence_valid': high_confidence_valid,
            'high_confidence_invalid': high_confidence_invalid,
            'avg_confidence': sum(r.confidence for r in results) / len(results)
        }

    def filter_valid_genes(self, symbols: List[str]) -> List[str]:
        """
        过滤出有效的基因符号

        Args:
            symbols: 基因符号列表

        Returns:
            List[str]: 有效基因符号列表
        """
        results = self.batch_validate(symbols)
        return [r.symbol for r in results if r.is_valid]

    def filter_invalid_symbols(self, symbols: List[str]) -> List[Tuple[str, str]]:
        """
        过滤出无效的符号及其原因

        Args:
            symbols: 符号列表

        Returns:
            List[Tuple[str, str]]: (符号, 原因) 列表
        """
        results = self.batch_validate(symbols)
        return [(r.symbol, r.message) for r in results if not r.is_valid]


# ==================== 全局实例 ====================

_gene_validator: Optional[GeneWhitelistValidator] = None


def get_gene_validator(use_online_validation: bool = True) -> GeneWhitelistValidator:
    """
    获取基因验证器实例

    Args:
        use_online_validation: 是否使用在线验证

    Returns:
        GeneWhitelistValidator: 验证器实例
    """
    global _gene_validator

    if _gene_validator is None:
        _gene_validator = GeneWhitelistValidator(use_online_validation=use_online_validation)

    return _gene_validator


def validate_gene_symbol(symbol: str) -> GeneValidationResult:
    """
    便捷函数：验证单个基因符号

    Args:
        symbol: 基因符号

    Returns:
        GeneValidationResult: 验证结果
    """
    validator = get_gene_validator()
    return validator.validate_gene_symbol(symbol)


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("V7.0 基因白名单验证器 - 测试")
    print("=" * 70)

    validator = GeneWhitelistValidator(use_online_validation=False)

    # 测试 1: 真实基因验证
    print("\n[Test 1] 真实基因验证")
    test_genes = ['TP53', 'BRCA1', 'EGFR', 'KRAS', 'MYC', 'BCL2']
    for gene in test_genes:
        result = validator.validate_gene_symbol(gene)
        print(f"  {gene}: valid={result.is_valid}, source={result.source.value}, confidence={result.confidence:.2f}")

    # 测试 2: 非基因实体（黑名单）
    print("\n[Test 2] 非基因实体检测")
    test_non_genes = ['RTX', 'GPU', 'AI', 'DNA', 'RNA', 'ATP', 'HTTP', 'JSON']
    for symbol in test_non_genes:
        result = validator.validate_gene_symbol(symbol)
        print(f"  {symbol}: valid={result.is_valid}, source={result.source.value}, message={result.message[:40]}")

    # 测试 3: 未知符号
    print("\n[Test 3] 未知符号处理")
    test_unknown = ['XYZ1', 'ABC2', 'DEF3']
    for symbol in test_unknown:
        result = validator.validate_gene_symbol(symbol)
        print(f"  {symbol}: valid={result.is_valid}, source={result.source.value}, confidence={result.confidence:.2f}")

    # 测试 4: 批量验证
    print("\n[Test 4] 批量验证")
    all_symbols = test_genes + test_non_genes + test_unknown
    results = validator.batch_validate(all_symbols)
    summary = validator.get_validation_summary(results)
    print(f"  总数: {summary['total']}")
    print(f"  有效: {summary['valid']} ({summary['valid_rate']:.2%})")
    print(f"  无效: {summary['invalid']}")
    print(f"  平均置信度: {summary['avg_confidence']:.2f}")

    print("\n" + "=" * 70)
    print("V7.0 基因白名单验证器测试完成!")
    print("=" * 70)