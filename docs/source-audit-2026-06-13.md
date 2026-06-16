信息源核查清单（2026-06-13）

- 总数：54
- 已启用：36
- 已配置：44
- 说明：已启用表示本轮能连通或已修复到可采集入口；未启用表示缺 Key、站点拒绝自动请求、接口未配置或当前连接失败。

| 信息源ID | 名称 | 类型 | 启用 | 配置 | 处理结果/问题 |
|---|---|---:|---:|---:|---|
| `adb-rss` | ADB Trade News (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `asean-rss` | ASEAN News (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `bis-rss` | BIS Export Control (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `canada-trade-rss` | Canada Trade (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `cbp-newsroom` | CBP Newsroom 美国海关查获 | web_scrape | 是 | 是 | 可采集/已启用 |
| `cbp-rss` | CBP Newsroom (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `cn-fta` | 中国自由贸易区服务网 | web_scrape | 是 | 是 | 可采集/已启用 |
| `cn-mofcom` | 商务部公告 | web_scrape | 是 | 是 | 可采集/已启用 |
| `csis-rss` | CSIS Trade (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `eaeu-rss` | EAEU 欧亚经济联盟 (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `eu-daily-news-rss` | EU Daily News (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `eu-eurlex` | EU EUR-Lex | official | 是 | 是 | 可采集/已启用 |
| `eu-tax-customs-rss` | EU Customs & Tax (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `eu-trade-rss` | EU Trade News (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `fao-food-price-index` | FAO Food Price Index | web_scrape | 是 | 是 | 可采集/已启用 |
| `globaltradealert-rss` | Global Trade Alert (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `iea-rss` | IEA News (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `iisd-rss` | IISD Trade Policy (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `imf-commodity-prices` | IMF Primary Commodity Prices | web_scrape | 是 | 是 | 可采集/已启用 |
| `imf-rss` | IMF News (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `nz-mfat-rss` | New Zealand MFAT Trade (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `ofac-rss` | OFAC Sanctions (Web) | web_scrape | 是 | 是 | 可采集/已启用 |
| `piie-rss` | PIIE Trade Policy (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `singapore-customs-rss` | Singapore Customs (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `tavily-search` | Tavily Web 搜索 | api_search | 是 | 是 | 可采集/已启用 |
| `uk-dbt-rss` | UK Trade (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `un-news-rss` | UN News (RSS) | rss | 是 | 是 | 可采集/已启用 |
| `unctad-rss` | UNCTAD News (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `ustr` | USTR 美国贸易代表办公室 | web_scrape | 是 | 是 | 可采集/已启用 |
| `ustr-rss` | USTR Press (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `wco` | WCO 世界海关组织 | web_scrape | 是 | 是 | 可采集/已启用 |
| `wco-rss` | WCO News (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `worldbank-blog-rss` | World Bank Blog (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `worldbank-open-data` | World Bank Open Data | json_api | 是 | 是 | 可采集/已启用 |
| `wto-news-rss` | WTO News (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `wto-trade-monitoring-rss` | WTO Trade Monitoring (RSS) | web_scrape | 是 | 是 | 可采集/已启用 |
| `australia-dfat-rss` | Australia DFAT Trade (RSS) | web_scrape | 否 | 是 | DFAT 当前从本机采集请求超时/断开，建议后续改用搜索 API 或专用入口。 |
| `baidu-search` | 百度千帆搜索（免费额度） | api_search | 否 | 否 | 缺少 BAIDU_QIANFAN_API_KEY，暂不能启用。 |
| `bing-search` | Bing 搜索（需 API Key） | api_search | 否 | 否 | 缺少 Bing Search API Key，暂不能启用。 |
| `cn-customs` | 海关总署公告 | web_scrape | 否 | 是 | 海关总署当前直连仍返回 504/412 或 JS 校验，通用采集不稳定；建议通过 Tavily/Baidu 使用 site:customs.gov.cn 补采。 |
| `google-alerts` | Google Alerts 快速雷达 | rss | 否 | 否 | 未配置 Google Alerts RSS URL。 |
| `hk-tid-rss` | 香港工贸署 (RSS) | web_scrape | 否 | 是 | 香港工贸署新版首页可达，但 circular 列表由动态/门户页面提供，当前通用 scraper 抓不到实际条目。 |
| `inoreader` | Inoreader 情报中枢 | json_api | 否 | 否 | 缺少 Inoreader API Key。 |
| `itc-trademap` | ITC Trade Map 贸易地图 | manual | 否 | 否 | 手工/商业数据源，当前项目没有 manual connector 自动采集。 |
| `japan-meti-rss` | 日本經产省 METI (RSS) | rss | 否 | 是 | METI RSS/Atom 从本机请求失败，保留停用。 |
| `korea-customs-rss` | Korea Customs (RSS) | rss | 否 | 是 | 韩国海关英文页从本机请求失败/断开，保留停用。 |
| `newsapi` | NewsAPI 全球新闻聚合 | json_api | 否 | 否 | 缺少 NewsAPI API Key。 |
| `oecd-rss` | OECD News (RSS) | rss | 否 | 是 | OECD 当前对自动请求返回 403，保留停用。 |
| `rss-app` | RSS.app 生成源 | rss | 否 | 否 | 未配置 RSS.app 生成的 feed URL。 |
| `search1api` | Search1API（需 API Key） | api_search | 否 | 否 | 缺少 Search1API API Key。 |
| `un-comtrade` | UN Comtrade 全球贸易数据库 | json_api | 否 | 否 | UN Comtrade 新版 API 需要订阅 Key，当前未配置。 |
| `usda-fas-rss` | USDA FAS 农业贸易 (RSS) | rss | 否 | 是 | USDA FAS 当前对自动请求返回 403，保留停用。 |
| `usitc-rss` | USITC Releases (RSS) | rss | 否 | 是 | USITC 当前对自动请求返回 403，保留停用。 |
| `wto-eping` | WTO ePing 技术性贸易壁垒通报 | official | 否 | 否 | WTO ePing 当前未配置可用 API endpoint；网页平台不适合当前通用 scraper。 |

## 本轮修复

- 修正免费 RSS/Web/Official 信息源被误判为“未配置”的问题。
- 修复 Tavily 小批量采集时 max_results 可能为 0 导致 400 的问题。
- BIS 从失效 RSS 改为 https://www.bis.gov/news-updates。
- EAEU 从失效 RSS 改为 https://eec.eaeunion.org/en/news/ 并增加新闻链接选择规则。
- Global Trade Alert 从失效 RSS 改为 https://globaltradealert.org/analysis 并增加 blog/report 链接选择规则。
- Singapore Customs 从 404 地址改为 https://www.customs.gov.sg/news/ 并增加新闻/PDF 链接选择规则。
- New Zealand MFAT 从失效 RSS 改为 https://www.mfat.govt.nz/en/trade 并增加贸易页链接选择规则。
- World Bank Open Data 已启用，属于免费公开 JSON API。