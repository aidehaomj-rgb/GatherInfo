export type SourceGroupId =
  | "news_risk_media"
  | "trade_industry_media"
  | "enforcement_risk_media"
  | "regional_hotspot_media"
  | "research_thinktank"
  | "government_igo"
  | "community_social"
  | "customs_enforcement"
  | "regulation_trade_measures"
  | "trade_commodity_data"
  | "supply_chain_company"
  | "search_aggregation"
  | "procurement_opportunity"
  | "other";

export interface SourceGroupDefinition {
  id: SourceGroupId;
  label: string;
  shortLabel: string;
  description: string;
  icon: "newspaper" | "chart" | "shield" | "map" | "library" | "landmark" | "messages" | "scale" | "database" | "route" | "search" | "briefcase";
  tone: string;
}

export const SOURCE_GROUPS: SourceGroupDefinition[] = [
  {
    id: "news_risk_media",
    label: "综合新闻媒体",
    shortLabel: "综合新闻",
    description: "通讯社、综合新闻门户及其他公开媒体来源",
    icon: "newspaper",
    tone: "coral",
  },
  {
    id: "trade_industry_media",
    label: "贸易与行业媒体",
    shortLabel: "贸易行业",
    description: "国际贸易、航运物流、产业和企业动态专业媒体",
    icon: "chart",
    tone: "amber",
  },
  {
    id: "enforcement_risk_media",
    label: "执法案件与风险事件",
    shortLabel: "执法风险",
    description: "执法查获、走私案件、跨境犯罪与合规风险报道",
    icon: "shield",
    tone: "red",
  },
  {
    id: "regional_hotspot_media",
    label: "地区热点媒体",
    shortLabel: "地区热点",
    description: "国家和地区政经热点、突发事件与区域风险媒体",
    icon: "map",
    tone: "cyan",
  },
  {
    id: "research_thinktank",
    label: "研究机构与智库",
    shortLabel: "研究智库",
    description: "智库、大学、研究机构及专业政策分析来源",
    icon: "library",
    tone: "violet",
  },
  {
    id: "government_igo",
    label: "政府与国际组织",
    shortLabel: "政府组织",
    description: "政府部门、国际组织及官方政策发布渠道",
    icon: "landmark",
    tone: "blue",
  },
  {
    id: "community_social",
    label: "行业社区与社会线索",
    shortLabel: "社区线索",
    description: "论坛、社交平台与从业者社区的一手线索",
    icon: "messages",
    tone: "pink",
  },
  {
    id: "customs_enforcement",
    label: "海关执法与通关合规",
    shortLabel: "海关通关",
    description: "海关公告、执法查获、清关与关务合规",
    icon: "shield",
    tone: "teal",
  },
  {
    id: "regulation_trade_measures",
    label: "法规政策与贸易措施",
    shortLabel: "法规措施",
    description: "出口管制、制裁、贸易救济、关税和技术壁垒",
    icon: "scale",
    tone: "indigo",
  },
  {
    id: "trade_commodity_data",
    label: "贸易数据与商品市场",
    shortLabel: "贸易数据",
    description: "贸易数据库、关键矿产、商品价格与市场数据",
    icon: "database",
    tone: "green",
  },
  {
    id: "supply_chain_company",
    label: "供应链物流与企业动态",
    shortLabel: "供应链",
    description: "航运物流、货代、供应链和企业经营动态",
    icon: "route",
    tone: "orange",
  },
  {
    id: "search_aggregation",
    label: "搜索与聚合工具",
    shortLabel: "搜索聚合",
    description: "搜索 API、新闻聚合、RSS 与智能研究工具",
    icon: "search",
    tone: "slate",
  },
  {
    id: "procurement_opportunity",
    label: "采购招标与供应商机会",
    shortLabel: "采购招标",
    description: "政府采购、国防合同、招标和供应商机会",
    icon: "briefcase",
    tone: "gold",
  },
];

export const OTHER_SOURCE_GROUP: SourceGroupDefinition = {
  id: "other",
  label: "未分类",
  shortLabel: "未分类",
  description: "尚待人工整理的信息源",
  icon: "search",
  tone: "slate",
};

export function getSourceGroupDefinition(value?: string | null): SourceGroupDefinition {
  return SOURCE_GROUPS.find((group) => group.id === value) ?? OTHER_SOURCE_GROUP;
}
