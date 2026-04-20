"""
测试期刊IF和发表日期解析的改进
"""
import sys
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')

from src.utils.pubmed import PubMedSearcher
from src.utils.journal_if import get_journal_if, get_journal_if_with_source
from Bio import Entrez

# 配置 PubMed
Entrez.email = "test@example.com"


def test_journal_if():
    """测试期刊IF获取"""
    print("=" * 60)
    print("测试期刊影响因子获取")
    print("=" * 60)

    test_journals = [
        "Nature",
        "Science",
        "Cell",
        "Bioinformatics",
        "PLOS ONE",
        "Nature Communications",
        "Frontiers in Neuroscience",
        "Journal of Biological Chemistry",
        "Lancet",
        "NEJM",
        "JAMA",
        "Unknown Journal 123",
    ]

    for journal in test_journals:
        if_val, source = get_journal_if_with_source(journal)
        status = "✓" if if_val > 0 else "✗"
        print(f"{status} {journal:45s} IF={if_val:6.2f} (来源: {source})")

    print()


def test_date_parsing():
    """测试日期解析"""
    print("=" * 60)
    print("测试发表日期解析")
    print("=" * 60)

    searcher = PubMedSearcher(email="test@example.com")

    # 搜索几篇论文进行测试
    print("正在搜索测试论文...")
    try:
        papers = searcher.search_papers("CRISPR gene editing", max_results=5)

        if not papers:
            print("未找到论文")
            return

        print(f"\n找到 {len(papers)} 篇论文:\n")

        for i, paper in enumerate(papers, 1):
            print(f"【论文 {i}】")
            print(f"  PMID: {paper.get('pmid', 'N/A')}")
            print(f"  标题: {paper.get('title', 'N/A')[:60]}...")
            print(f"  期刊: {paper.get('journal', 'N/A')}")

            # 显示IF
            journal = paper.get('journal', '')
            if journal:
                if_val, source = get_journal_if_with_source(journal)
                print(f"  影响因子: {if_val:.2f} (来源: {source})")

            # 显示日期
            pub_date = paper.get('publication_date', 'N/A')
            print(f"  发表日期: {pub_date}")

            # 评估日期质量
            if pub_date and pub_date != 'N/A':
                if len(pub_date) >= 4:
                    year = pub_date[:4]
                    try:
                        year_int = int(year)
                        if 1990 <= year_int <= 2030:
                            print(f"  日期解析: ✓ 有效")
                        else:
                            print(f"  日期解析: ⚠ 年份异常 ({year})")
                    except:
                        print(f"  日期解析: ⚠ 无法解析年份")
                else:
                    print(f"  日期解析: ⚠ 日期格式不完整")
            else:
                print(f"  日期解析: ✗ 未获取到日期")

            print()

    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()


def test_specific_pmids():
    """测试特定PMID的解析"""
    print("=" * 60)
    print("测试特定论文的解析")
    print("=" * 60)

    # 几篇已知的论文PMID
    test_pmids = [
        "30390086",  # Nature 论文
        "30573278",  # Science 论文
        "32855795",  # Nature Communications
    ]

    searcher = PubMedSearcher(email="test@example.com")

    for pmid in test_pmids:
        print(f"\n--- PMID: {pmid} ---")
        try:
            handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
            records = Entrez.read(handle)
            handle.close()

            if records and 'PubmedArticle' in records.keys():
                article = records['PubmedArticle']
                if isinstance(article, list) and len(article) > 0:
                    article = article[0]

                paper = searcher._parse_pubmed_article(article, "test_query")
                if paper:
                    print(f"标题: {paper['title'][:50]}...")
                    print(f"期刊: {paper.get('journal', 'N/A')}")
                    print(f"日期: {paper.get('publication_date', 'N/A')}")

                    journal = paper.get('journal', '')
                    if journal:
                        if_val, source = get_journal_if_with_source(journal)
                        print(f"IF: {if_val:.2f} (来源: {source})")
                else:
                    print("解析失败")
        except Exception as e:
            print(f"错误: {e}")


if __name__ == '__main__':
    # 测试1: 期刊IF
    test_journal_if()

    # 测试2: 日期解析
    test_date_parsing()

    # 测试3: 特定论文
    test_specific_pmids()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
