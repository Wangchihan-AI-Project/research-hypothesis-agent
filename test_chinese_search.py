# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')

from src.utils.pubmed import PubMedSearcher

searcher = PubMedSearcher()

# Test Chinese query translation
idea = '利用 UK Biobank 的多组学数据 构建一个因果图神经网络模型 研究 APOE 变体对后期痴呆风险的非线性影响 重点关注中介效应分析和残余混杂控制'

print('Testing keyword extraction...')
print(f'Input: {idea}')

try:
    search_terms = searcher._generate_search_terms_from_idea(idea)
    print(f'Extracted search terms: {search_terms}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
