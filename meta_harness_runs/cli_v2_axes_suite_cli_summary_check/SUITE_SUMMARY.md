# Meta-Harness Suite 汇总

运行时间: 2026-04-24 18:14:51
Suite: v2_axes
运行前缀: cli_v2_axes_suite_cli_summary_check

## Candidate 总表

| Tier | Candidate | v2_frontier_sensitive | v2_roadmap_sensitive | v2_innovation_sensitive | 跨轴平均 | 强项标签 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| top | full_enhanced | 0.8014 | 0.5431 | 0.5153 | 0.6199 | frontier_strong, roadmap_strong, innovation_strong |
| strong | frontier_roadmap | 0.7299 | 0.5431 | 0.4438 | 0.5723 | frontier_strong, roadmap_strong |
| strong | roadmap_innovation | 0.6146 | 0.5431 | 0.5153 | 0.5577 | roadmap_strong, innovation_strong |
| strong | frontier_innovation | 0.7021 | 0.4438 | 0.5153 | 0.5537 | frontier_strong, innovation_strong |
| strong | roadmap_only | 0.5431 | 0.5431 | 0.4438 | 0.5100 | roadmap_strong |
| strong | frontier_only | 0.6305 | 0.4438 | 0.4438 | 0.5060 | frontier_strong |
| strong | innovation_only | 0.5153 | 0.4438 | 0.5153 | 0.4915 | innovation_strong |
| baseline | current_baseline | 0.4438 | 0.4438 | 0.4438 | 0.4438 | baseline_level |
| baseline | render_only | 0.4438 | 0.4438 | 0.4438 | 0.4438 | baseline_level |

## 强项标签规则

- method: midpoint_between_baseline_and_best
- v2_frontier_sensitive: baseline=0.4438, best=0.8014, threshold=0.6226
- v2_roadmap_sensitive: baseline=0.4438, best=0.5431, threshold=0.4934
- v2_innovation_sensitive: baseline=0.4438, best=0.5153, threshold=0.4795

## 排名分层规则

- top: rank == 1
- strong: rank > 1 且 strength_tags 不仅为 baseline_level
- baseline: 其余 candidate

## 分轴明细

### v2_frontier_sensitive

- full_enhanced: avg=0.8014, count=2
- frontier_roadmap: avg=0.7299, count=2
- frontier_innovation: avg=0.7021, count=2
- frontier_only: avg=0.6305, count=2
- roadmap_innovation: avg=0.6146, count=2
- roadmap_only: avg=0.5431, count=2
- innovation_only: avg=0.5153, count=2
- current_baseline: avg=0.4438, count=2
- render_only: avg=0.4438, count=2


### v2_roadmap_sensitive

- frontier_roadmap: avg=0.5431, count=2
- full_enhanced: avg=0.5431, count=2
- roadmap_innovation: avg=0.5431, count=2
- roadmap_only: avg=0.5431, count=2
- current_baseline: avg=0.4438, count=2
- frontier_innovation: avg=0.4438, count=2
- frontier_only: avg=0.4438, count=2
- innovation_only: avg=0.4438, count=2
- render_only: avg=0.4438, count=2


### v2_innovation_sensitive

- frontier_innovation: avg=0.5153, count=2
- full_enhanced: avg=0.5153, count=2
- innovation_only: avg=0.5153, count=2
- roadmap_innovation: avg=0.5153, count=2
- current_baseline: avg=0.4438, count=2
- frontier_only: avg=0.4438, count=2
- frontier_roadmap: avg=0.4438, count=2
- render_only: avg=0.4438, count=2
- roadmap_only: avg=0.4438, count=2



## 决策摘要

- 结论: 默认推荐 full_enhanced；备选 frontier_roadmap
- 默认推荐: full_enhanced (排名第1，跨轴平均 0.6199，强项: frontier_strong, roadmap_strong, innovation_strong)
- 备选: frontier_roadmap (排名第2，跨轴平均 0.5723，强项: frontier_strong, roadmap_strong)