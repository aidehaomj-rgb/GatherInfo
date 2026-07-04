 import { useMemo, useState } from "react";
 import { Search } from "lucide-react";
 import type { Source } from "../types";

 interface SourceSelectorProps {
   sources: Source[];
   selected: string[];
   onChange: (selected: string[]) => void;
 }

 export function SourceSelector({ sources, selected, onChange }: SourceSelectorProps) {
   const [search, setSearch] = useState("");

   const filtered = useMemo(() => {
     const q = search.trim().toLowerCase();
     if (!q) return sources;
     return sources.filter((s) =>
       `${s.name} ${s.id} ${s.channel} ${(s.default_categories ?? []).join(" ")}`
         .toLowerCase()
         .includes(q)
     );
   }, [sources, search]);

   const groups = useMemo(() => {
     const tree: Record<string, Record<string, Source[]>> = {};
     for (const s of filtered) {
       const cats = s.default_categories ?? [];
       const l1 = cats[0] || "未分类";
       const l2 = cats[1] || "—";
       tree[l1] = tree[l1] ?? {};
       tree[l1][l2] = tree[l1][l2] ?? [];
       tree[l1][l2].push(s);
     }
     return tree;
   }, [filtered]);

   const toggleSource = (id: string) => {
     onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
   };

   const toggleGroup = (l1: string, l2: string) => {
     const ids = groups[l1][l2].map((s) => s.id);
     const allSelected = ids.length > 0 && ids.every((id) => selected.includes(id));
     onChange(
       allSelected
         ? selected.filter((id) => !ids.includes(id))
         : Array.from(new Set([...selected, ...ids]))
     );
   };

   const toggleL1 = (l1: string) => {
     const ids = Object.values(groups[l1]).flat().map((s) => s.id);
     const allSelected = ids.length > 0 && ids.every((id) => selected.includes(id));
     onChange(
       allSelected
         ? selected.filter((id) => !ids.includes(id))
         : Array.from(new Set([...selected, ...ids]))
     );
   };

   return (
     <div className="source-selector">
       <div className="source-selector-search">
         <Search size={14} />
         <input
           type="text"
           value={search}
           onChange={(e) => setSearch(e.target.value)}
           placeholder="搜索信息源名称或分组"
         />
       </div>
       {Object.keys(groups).length === 0 && (
         <div className="text-muted small">无匹配信息源</div>
       )}
       {Object.entries(groups).map(([l1, l2map]) => {
         const l1Ids = Object.values(l2map).flat().map((s) => s.id);
         const l1AllSelected = l1Ids.length > 0 && l1Ids.every((id) => selected.includes(id));
         return (
           <div key={l1} className="source-selector-group">
             <div className="source-selector-l1">
               <label className="source-selector-checkbox">
                 <input type="checkbox" checked={l1AllSelected} onChange={() => toggleL1(l1)} />
                 <strong>{l1}</strong>
               </label>
               <span className="text-muted small">{l1Ids.length} 个</span>
             </div>
             {Object.entries(l2map).map(([l2, arr]) => {
               const ids = arr.map((s) => s.id);
               const allSelected = ids.length > 0 && ids.every((id) => selected.includes(id));
               return (
                 <div key={`${l1}::${l2}`} className="source-selector-subgroup">
                   <label className="source-selector-checkbox" style={{ paddingLeft: 12 }}>
                     <input type="checkbox" checked={allSelected} onChange={() => toggleGroup(l1, l2)} />
                     <span>{l2}</span>
                     <span className="text-muted small">({arr.length})</span>
                   </label>
                   <div className="source-selector-items">
                     {arr.map((s) => (
                       <label key={s.id} className="source-selector-row">
                         <input
                           type="checkbox"
                           checked={selected.includes(s.id)}
                           onChange={() => toggleSource(s.id)}
                         />
                         <span className="source-selector-name" title={`${s.name} (${s.id})`}>
                           {s.name}
                         </span>
                         <span className="source-selector-channel">{s.channel}</span>
                       </label>
                     ))}
                   </div>
                 </div>
               );
             })}
           </div>
         );
       })}
     </div>
   );
 }
