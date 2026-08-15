// _mock_lucide.mjs
import { createElement } from "react";
var icon = (name) => (props) => createElement("svg", { ...props, "data-icon": name });
var Check = icon("check");
var ChevronDown = icon("chevron-down");
var ChevronsDownUp = icon("chevrons-down-up");
var ChevronsUpDown = icon("chevrons-up-down");
var Search = icon("search");
var X = icon("x");

// src/components/SourceSelector.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
var MODELS_GROUP_ID = "__models__";
var PRIMARY_CATEGORY_LABELS = {
  commodity: "\u5546\u54C1\u4E0E\u5927\u5B97\u5546\u54C1",
  customs: "\u6D77\u5173\u76D1\u7BA1",
  enforcement: "\u6267\u6CD5\u98CE\u9669",
  export_control: "\u51FA\u53E3\u7BA1\u5236",
  fta: "\u81EA\u7531\u8D38\u6613\u534F\u5B9A",
  general: "\u7EFC\u5408\u4FE1\u606F",
  ip: "\u77E5\u8BC6\u4EA7\u6743",
  market: "\u5E02\u573A\u4E0E\u4EA7\u4E1A",
  policy: "\u653F\u7B56\u6CD5\u89C4",
  price: "\u4EF7\u683C\u4E0E\u884C\u60C5",
  regulation: "\u76D1\u7BA1\u89C4\u5219",
  risk: "\u98CE\u9669\u60C5\u62A5",
  sanction: "\u5236\u88C1\u4E0E\u5408\u89C4",
  search: "\u641C\u7D22\u4E0E\u4FE1\u606F\u805A\u5408",
  tbt_sps: "\u6280\u672F\u8D38\u6613\u63AA\u65BD",
  trade: "\u56FD\u9645\u8D38\u6613",
  trade_remedy: "\u8D38\u6613\u6551\u6D4E",
  "\u7F51\u9875\xB7\u6267\u6CD5\u4FE1\u606F": "\u7F51\u9875\u6267\u6CD5\u4FE1\u606F",
  "\u7F51\u9875\xB7\u70ED\u70B9\u4FE1\u606F": "\u7F51\u9875\u70ED\u70B9\u4FE1\u606F",
  "\u793E\u4EA4\u5A92\u4F53\xB7\u5FAE\u4FE1\u516C\u4F17\u53F7": "\u793E\u4EA4\u5A92\u4F53\uFF1A\u5FAE\u4FE1\u516C\u4F17\u53F7",
  "\u793E\u4EA4\u5A92\u4F53\xB7\u5FAE\u535A": "\u793E\u4EA4\u5A92\u4F53\uFF1A\u5FAE\u535A",
  "\u793E\u4EA4\u5A92\u4F53\xB7\u4ECA\u65E5\u5934\u6761": "\u793E\u4EA4\u5A92\u4F53\uFF1A\u4ECA\u65E5\u5934\u6761",
  "\u672A\u5206\u7C7B": "\u5176\u4ED6\u4FE1\u606F\u6E90"
};
var CHANNEL_LABELS = {
  ai_research: "AI \u63D0\u793A\u91C7\u96C6",
  api_search: "\u641C\u7D22\u91C7\u96C6",
  commercial: "\u5546\u4E1A\u6570\u636E",
  deepweb: "\u6DF1\u5EA6\u7F51\u9875",
  json_api: "\u6570\u636E\u63A5\u53E3",
  manual: "\u624B\u5DE5\u5F55\u5165",
  official: "\u5B98\u65B9\u6E20\u9053",
  rss: "RSS \u8BA2\u9605",
  social: "\u793E\u4EA4\u5A92\u4F53",
  web_scrape: "\u7F51\u9875\u6293\u53D6"
};
function primaryCategory(source) {
  return source.default_categories?.[0] || "\u672A\u5206\u7C7B";
}
function primaryLabel(category) {
  return PRIMARY_CATEGORY_LABELS[category] || "\u5176\u4ED6\u4FE1\u606F\u6E90";
}
function sourceUrl(source) {
  return source.homepage_url || source.base_url || source.api_endpoint || "";
}
function sourceMeta(source) {
  const tags = source.default_categories?.slice(1).join(" \xB7 ") || "";
  const url = sourceUrl(source);
  return [tags, url].filter(Boolean).join(" \xB7 ") || channelLabel(source.channel);
}
function channelLabel(channel) {
  return CHANNEL_LABELS[channel] || channel;
}
function TreeCheckbox({
  checked,
  mixed = false,
  onChange,
  label
}) {
  const inputRef = useRef(null);
  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = mixed;
  }, [mixed]);
  return /* @__PURE__ */ jsx(
    "input",
    {
      ref: inputRef,
      type: "checkbox",
      checked,
      "aria-label": label,
      onClick: (event) => event.stopPropagation(),
      onChange
    }
  );
}
function SourceLeaf({
  source,
  selected,
  onToggle
}) {
  return /* @__PURE__ */ jsxs("label", { className: `source-tree-leaf ${selected ? "source-tree-leaf--selected" : ""}`, children: [
    /* @__PURE__ */ jsx(TreeCheckbox, { checked: selected, label: `\u9009\u62E9\u4FE1\u606F\u6E90\uFF1A${source.name}`, onChange: onToggle }),
    /* @__PURE__ */ jsxs("span", { className: "source-tree-leaf-copy", children: [
      /* @__PURE__ */ jsx("strong", { children: source.name }),
      /* @__PURE__ */ jsx("span", { title: sourceMeta(source), children: sourceMeta(source) })
    ] }),
    /* @__PURE__ */ jsx("span", { className: "source-tree-channel", children: channelLabel(source.channel) })
  ] });
}
function TreeGroupHeader({
  label,
  expanded,
  selectedCount,
  totalCount,
  checkboxLabel,
  onToggleExpand,
  onToggleSelect
}) {
  const allSelected = selectedCount === totalCount && totalCount > 0;
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: "source-tree-root",
      role: "button",
      tabIndex: 0,
      "aria-expanded": expanded,
      onClick: onToggleExpand,
      onKeyDown: (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggleExpand();
        }
      },
      children: [
        /* @__PURE__ */ jsx(
          TreeCheckbox,
          {
            checked: allSelected,
            mixed: selectedCount > 0 && !allSelected,
            label: checkboxLabel,
            onChange: onToggleSelect
          }
        ),
        /* @__PURE__ */ jsxs("span", { className: "source-tree-toggle", children: [
          /* @__PURE__ */ jsx(ChevronDown, { size: 16, className: `source-tree-chevron ${expanded ? "" : "source-tree-chevron--closed"}` }),
          /* @__PURE__ */ jsx("span", { children: label })
        ] }),
        /* @__PURE__ */ jsxs("span", { className: "source-tree-count", children: [
          selectedCount,
          "/",
          totalCount
        ] })
      ]
    }
  );
}
function SourceSelector({
  sources,
  selected,
  onChange,
  models,
  selectedModelIds,
  onModelChange
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(selected);
  const [modelDraft, setModelDraft] = useState(selectedModelIds);
  const [search, setSearch] = useState("");
  const [collapsedIds, setCollapsedIds] = useState([]);
  const tree = useMemo(() => {
    const query = search.trim().toLowerCase();
    const buckets = {};
    for (const source of sources) {
      const category = primaryCategory(source);
      const searchable = [
        source.name,
        source.id,
        source.channel,
        sourceUrl(source),
        source.default_categories?.join(" ") || "",
        primaryLabel(category)
      ].join(" ").toLowerCase();
      if (query && !searchable.includes(query)) continue;
      buckets[category] = [...buckets[category] || [], source];
    }
    return Object.entries(buckets).map(([id, groupedSources]) => ({
      id,
      label: primaryLabel(id),
      sources: [...groupedSources].sort((left, right) => left.name.localeCompare(right.name, "zh-CN"))
    })).sort((left, right) => left.label.localeCompare(right.label, "zh-CN"));
  }, [search, sources]);
  const configuredModels = models.filter((model) => model.is_active && model.is_configured && Boolean(model.model_name));
  const configuredModelIds = configuredModels.map((model) => model.id);
  const allGroupIds = useMemo(
    () => configuredModels.length > 0 ? [MODELS_GROUP_ID, ...tree.map((group) => group.id)] : tree.map((group) => group.id),
    [configuredModels.length, tree]
  );
  const isSearching = search.trim().length > 0;
  const isGroupExpanded = (id) => isSearching || !collapsedIds.includes(id);
  const toggleExpanded = (id) => {
    setCollapsedIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  };
  const setAllExpanded = (expanded) => setCollapsedIds(expanded ? [] : allGroupIds);
  const openPicker = () => {
    setDraft([...selected]);
    setModelDraft([...selectedModelIds]);
    setSearch("");
    setCollapsedIds([]);
    setOpen(true);
  };
  const closePicker = () => setOpen(false);
  const saveSelection = () => {
    onChange(draft);
    onModelChange(modelDraft);
    setOpen(false);
  };
  const toggleSource = (id) => {
    setDraft((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  };
  const toggleIds = (ids) => {
    setDraft((current) => {
      const allSelected = ids.length > 0 && ids.every((id) => current.includes(id));
      return allSelected ? current.filter((id) => !ids.includes(id)) : Array.from(/* @__PURE__ */ new Set([...current, ...ids]));
    });
  };
  const toggleModel = (id) => {
    setModelDraft((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  };
  const toggleModelIds = (ids) => {
    setModelDraft((current) => {
      const allSelected = ids.length > 0 && ids.every((id) => current.includes(id));
      return allSelected ? current.filter((id) => !ids.includes(id)) : Array.from(/* @__PURE__ */ new Set([...current, ...ids]));
    });
  };
  const selectVisibleSources = () => {
    const visibleIds = tree.flatMap((group) => group.sources.map((source) => source.id));
    setDraft((current) => Array.from(/* @__PURE__ */ new Set([...current, ...visibleIds])));
  };
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs("div", { className: "topic-source-picker-trigger", children: [
      /* @__PURE__ */ jsxs("span", { className: "text-muted small", children: [
        "\u5DF2\u9009 ",
        selected.length,
        " \u4E2A\u4FE1\u606F\u6E90\u3001",
        selectedModelIds.length,
        " \u4E2A AI \u6A21\u578B"
      ] }),
      /* @__PURE__ */ jsx("button", { type: "button", className: "btn btn-secondary btn-sm", onClick: openPicker, children: "\u9009\u62E9\u4FE1\u606F\u6E90" })
    ] }),
    open && createPortal(
      /* @__PURE__ */ jsx(
        "div",
        {
          className: "modal-overlay source-picker-overlay",
          onClick: (event) => {
            if (event.target === event.currentTarget) closePicker();
          },
          children: /* @__PURE__ */ jsxs(
            "section",
            {
              className: "modal source-picker-modal",
              role: "dialog",
              "aria-modal": "true",
              "aria-labelledby": "source-picker-title",
              onClick: (event) => event.stopPropagation(),
              children: [
                /* @__PURE__ */ jsxs("header", { className: "source-picker-header", children: [
                  /* @__PURE__ */ jsxs("div", { children: [
                    /* @__PURE__ */ jsx("h3", { id: "source-picker-title", children: "\u5173\u8054\u4FE1\u606F\u6E90" }),
                    /* @__PURE__ */ jsx("p", { className: "text-muted small", children: "\u7F51\u7AD9\u4E0E RSS \u662F\u539F\u59CB\u8BC1\u636E\u6E20\u9053\uFF1BAI \u6A21\u578B\u590D\u7528\u5DF2\u751F\u6548\u914D\u7F6E\uFF0C\u7528\u4E8E\u751F\u6210\u8BED\u4E49\u68C0\u7D22\u8BA1\u5212\u3001\u4E2D\u6587\u8F6C\u8BD1\u548C\u5BA1\u6838\uFF0C\u4E0D\u9700\u8981\u518D\u6B21\u5F55\u5165\u5BC6\u94A5\u3002" })
                  ] }),
                  /* @__PURE__ */ jsx("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: closePicker, title: "\u5173\u95ED", children: /* @__PURE__ */ jsx(X, { size: 16 }) })
                ] }),
                /* @__PURE__ */ jsxs("div", { className: "source-picker-toolbar", children: [
                  /* @__PURE__ */ jsxs("label", { className: "source-selector-search", children: [
                    /* @__PURE__ */ jsx(Search, { size: 16 }),
                    /* @__PURE__ */ jsx(
                      "input",
                      {
                        type: "search",
                        value: search,
                        onChange: (event) => setSearch(event.target.value),
                        placeholder: "\u641C\u7D22\u6765\u6E90\u540D\u79F0\u3001URL\u3001\u6E20\u9053\u6216\u5206\u7C7B"
                      }
                    )
                  ] }),
                  /* @__PURE__ */ jsx("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: selectVisibleSources, children: "\u9009\u62E9\u5F53\u524D\u7ED3\u679C" }),
                  /* @__PURE__ */ jsxs("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: () => setAllExpanded(true), children: [
                    /* @__PURE__ */ jsx(ChevronsUpDown, { size: 14 }),
                    " \u5C55\u5F00\u5206\u7C7B"
                  ] }),
                  /* @__PURE__ */ jsxs("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: () => setAllExpanded(false), children: [
                    /* @__PURE__ */ jsx(ChevronsDownUp, { size: 14 }),
                    " \u6536\u8D77\u5206\u7C7B"
                  ] }),
                  /* @__PURE__ */ jsx("button", { type: "button", className: "btn btn-ghost btn-sm", onClick: () => {
                    setDraft([]);
                    setModelDraft([]);
                  }, children: "\u6E05\u7A7A\u9009\u62E9" })
                ] }),
                /* @__PURE__ */ jsxs("div", { className: "source-tree", role: "tree", "aria-label": "\u4FE1\u606F\u6E90\u5206\u7C7B\u6811", children: [
                  configuredModels.length > 0 && /* @__PURE__ */ jsxs(
                    "section",
                    {
                      className: "source-tree-group source-tree-group--models",
                      role: "treeitem",
                      "aria-expanded": isGroupExpanded(MODELS_GROUP_ID),
                      children: [
                        /* @__PURE__ */ jsx(
                          TreeGroupHeader,
                          {
                            label: "AI \u6A21\u578B\u4FE1\u606F\u6E90",
                            expanded: isGroupExpanded(MODELS_GROUP_ID),
                            selectedCount: configuredModelIds.filter((id) => modelDraft.includes(id)).length,
                            totalCount: configuredModelIds.length,
                            checkboxLabel: "\u9009\u62E9\u5168\u90E8 AI \u6A21\u578B",
                            onToggleExpand: () => toggleExpanded(MODELS_GROUP_ID),
                            onToggleSelect: () => toggleModelIds(configuredModelIds)
                          }
                        ),
                        isGroupExpanded(MODELS_GROUP_ID) && /* @__PURE__ */ jsx("div", { className: "source-tree-children", role: "group", children: configuredModels.map((model) => {
                          const isSelected = modelDraft.includes(model.id);
                          return /* @__PURE__ */ jsxs("label", { className: `source-tree-leaf ${isSelected ? "source-tree-leaf--selected" : ""}`, children: [
                            /* @__PURE__ */ jsx(TreeCheckbox, { checked: isSelected, label: `\u9009\u62E9 AI \u6A21\u578B\uFF1A${model.name}`, onChange: () => toggleModel(model.id) }),
                            /* @__PURE__ */ jsxs("span", { className: "source-tree-leaf-copy", children: [
                              /* @__PURE__ */ jsx("strong", { children: model.name }),
                              /* @__PURE__ */ jsxs("span", { children: [
                                model.provider,
                                " \xB7 ",
                                model.model_name
                              ] })
                            ] }),
                            /* @__PURE__ */ jsx("span", { className: "source-tree-channel", children: "\u5DF2\u914D\u7F6E" })
                          ] }, model.id);
                        }) })
                      ]
                    }
                  ),
                  tree.length === 0 && /* @__PURE__ */ jsx("div", { className: "text-muted small", children: "\u65E0\u5339\u914D\u4FE1\u606F\u6E90" }),
                  tree.map((group) => {
                    const groupIds = group.sources.map((source) => source.id);
                    const groupSelected = groupIds.filter((id) => draft.includes(id)).length;
                    const expanded = isGroupExpanded(group.id);
                    return /* @__PURE__ */ jsxs("section", { className: "source-tree-group", role: "treeitem", "aria-expanded": expanded, children: [
                      /* @__PURE__ */ jsx(
                        TreeGroupHeader,
                        {
                          label: group.label,
                          expanded,
                          selectedCount: groupSelected,
                          totalCount: groupIds.length,
                          checkboxLabel: `\u9009\u62E9\u5206\u7C7B\uFF1A${group.label}`,
                          onToggleExpand: () => toggleExpanded(group.id),
                          onToggleSelect: () => toggleIds(groupIds)
                        }
                      ),
                      expanded && /* @__PURE__ */ jsx("div", { className: "source-tree-children", role: "group", children: group.sources.map((source) => /* @__PURE__ */ jsx(
                        SourceLeaf,
                        {
                          source,
                          selected: draft.includes(source.id),
                          onToggle: () => toggleSource(source.id)
                        },
                        source.id
                      )) })
                    ] }, group.id);
                  })
                ] }),
                /* @__PURE__ */ jsxs("footer", { className: "source-picker-footer", children: [
                  /* @__PURE__ */ jsxs("span", { className: "text-muted small", children: [
                    "\u5F53\u524D\u9009\u62E9 ",
                    draft.length,
                    " \u4E2A\u4FE1\u606F\u6E90\u3001",
                    modelDraft.length,
                    " \u4E2A AI \u6A21\u578B"
                  ] }),
                  /* @__PURE__ */ jsxs("div", { className: "modal-actions source-picker-actions", children: [
                    /* @__PURE__ */ jsx("button", { type: "button", className: "btn btn-ghost", onClick: closePicker, children: "\u53D6\u6D88" }),
                    /* @__PURE__ */ jsxs("button", { type: "button", className: "btn btn-primary", onClick: saveSelection, children: [
                      /* @__PURE__ */ jsx(Check, { size: 16 }),
                      " \u4FDD\u5B58\u9009\u62E9"
                    ] })
                  ] })
                ] })
              ]
            }
          )
        }
      ),
      document.body
    )
  ] });
}
export {
  SourceSelector
};
