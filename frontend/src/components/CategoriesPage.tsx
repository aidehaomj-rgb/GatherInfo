import { ConfirmDialog } from "./shared/ConfirmDialog";
import { useEffect, useState, useCallback } from "react";
import { ArrowLeft, FolderKanban, Plus, Trash2, Edit3, Scale, ShieldAlert, Cpu, Globe2, ChartNoAxesCombined, PackageSearch } from "lucide-react";
import { fetchTopics } from "../api";
import type { Topic } from "../types";

interface Category {
  id: string; name: string; description: string | null;
  created_at: string | null; updated_at: string | null;
}

const BASE = "/api/v1";

const CATEGORY_VISUALS = [
  { tone: "blue", icon: Scale, keywords: ["policy", "政策", "法规", "regulation"] },
  { tone: "red", icon: ShieldAlert, keywords: ["custom", "海关", "执法", "风险", "sanction"] },
  { tone: "teal", icon: Globe2, keywords: ["trade", "贸易", "global", "国际"] },
  { tone: "amber", icon: ChartNoAxesCombined, keywords: ["market", "市场", "price", "价格", "finance"] },
  { tone: "green", icon: PackageSearch, keywords: ["product", "商品", "commodity", "产业"] },
  { tone: "violet", icon: Cpu, keywords: ["tech", "技术", "digital", "科技"] },
] as const;

function categoryVisual(category: Category, index: number) {
  const value = `${category.id} ${category.name}`.toLowerCase();
  return CATEGORY_VISUALS.find((visual) => visual.keywords.some((keyword) => value.includes(keyword)))
    ?? CATEGORY_VISUALS[index % CATEGORY_VISUALS.length];
}

export function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);
  const [editing, setEditing] = useState<Category | null>(null);
  const [activeCategory, setActiveCategory] = useState<Category | null>(null);
  const [categoryTopics, setCategoryTopics] = useState<Topic[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${BASE}/categories`);
      if (!resp.ok) throw new Error(await resp.text());
      setCategories(await resp.json());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: `删除类别 "${id}"？关联的主题将变为未分类。` });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try {
      const resp = await fetch(`${BASE}/categories/${id}`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await resp.text());
      setCategories((p) => p.filter((c) => c.id !== id));
    } catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
    setConfirmDelete(null);
  };

  const openCategoryTopics = async (category: Category) => {
    setActiveCategory(category);
    setTopicsLoading(true);
    try {
      const topics = await fetchTopics();
      setCategoryTopics(topics.filter((topic) => topic.category_id === category.id));
    } catch (e) {
      setCategoryTopics([]);
      setError(e instanceof Error ? e.message : "加载主题失败");
    }
    setTopicsLoading(false);
  };

  if (loading) return <div className="loading">加载类别...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  if (activeCategory) {
    return (
      <div className="page category-topic-view">
        <div className="page-header">
          <div>
            <button type="button" className="btn btn-ghost btn-sm category-back-button" onClick={() => setActiveCategory(null)}>
              <ArrowLeft size={16} /> 返回采集类别
            </button>
            <h2>{activeCategory.name}</h2>
            <p className="text-muted">该类别下的采集主题，共 {categoryTopics.length} 个。</p>
          </div>
        </div>

        {topicsLoading ? <div className="loading">加载主题...</div> : categoryTopics.length === 0 ? (
          <div className="empty-state">
            <FolderKanban size={26} />
            <h3>该类别尚未关联主题</h3>
            <p>请在主题管理中编辑主题，并将其归入“{activeCategory.name}”。</p>
          </div>
        ) : (
          <div className="category-topic-list" aria-label={`${activeCategory.name} 的主题列表`}>
            {categoryTopics.map((topic) => (
              <article key={topic.id} className="category-topic-row">
                <div className="category-topic-row-main">
                  <strong>{topic.name}</strong>
                  <span>{topic.description || "未填写主题说明"}</span>
                  {topic.keywords.length > 0 && (
                    <div className="category-topic-keywords">
                      {topic.keywords.slice(0, 6).map((keyword) => <span key={keyword}>{keyword}</span>)}
                    </div>
                  )}
                </div>
                <div className="category-topic-row-stats">
                  <span className={topic.is_active ? "chip chip--green" : "chip"}>{topic.is_active ? "启用" : "停用"}</span>
                  <strong>{topic.total_items_collected.toLocaleString()}</strong>
                  <span>已采集</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>采集类别</h2>
          <p className="text-muted">树状结构顶层：类别 → 主题 → 批次 → 条目</p>
        </div>
      </div>

      <div className="category-tile-grid">
        {categories.map((category, index) => {
          const visual = categoryVisual(category, index);
          const Icon = visual.icon;
          return (
            <article
              key={category.id}
              className={`category-tile category-tile--${visual.tone} category-tile--browse`}
              tabIndex={0}
              onDoubleClick={() => void openCategoryTopics(category)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  void openCategoryTopics(category);
                }
              }}
              aria-label={`双击查看 ${category.name} 下的主题`}
            >
              <div className="category-tile-pattern" aria-hidden="true">
                {Array.from({ length: 9 }, (_, dotIndex) => <i key={dotIndex} />)}
              </div>
              <div className="category-tile-topline">
                <span className="category-tile-icon"><Icon size={25} /></span>
                <div className="category-tile-actions">
                  <button type="button" className="btn-icon" title={`编辑 ${category.name}`} onClick={(event) => { event.stopPropagation(); setEditing(category); }} onDoubleClick={(event) => event.stopPropagation()}><Edit3 size={14} /></button>
                  <button type="button" className="btn-icon category-tile-delete" title={`删除 ${category.name}`} onClick={(event) => { event.stopPropagation(); handleDelete(category.id); }} onDoubleClick={(event) => event.stopPropagation()}><Trash2 size={14} /></button>
                </div>
              </div>
              <div className="category-tile-copy">
                <h3>{category.name}</h3>
                <span>{category.id}</span>
                <p>{category.description || "用于组织主题、批次和采集条目"}</p>
              </div>
            </article>
          );
        })}
        {Array.from({ length: categories.length < 9 ? 9 - categories.length : 1 }, (_, index) => (
          <button key={`add-category-${index}`} type="button" className="category-tile category-tile--add" onClick={() => setShowCreate(true)}>
            <span className="category-tile-add-icon"><Plus size={30} /></span>
            <strong>新建类别</strong>
            <span>添加新的采集主题分组</span>
          </button>
        ))}
      </div>

      {(showCreate || editing) && (
        <CategoryForm
          category={editing}
          onSave={async (data) => {
            const isNew = !editing;
            const resp = isNew
              ? await fetch(`${BASE}/categories`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
              : await fetch(`${BASE}/categories/${editing.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
            if (!resp.ok) { alert(await resp.text()); return; }
            setShowCreate(false); setEditing(null); await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

function CategoryForm({ category, onSave, onClose }: {
  category: Category | null; onSave: (data: { id: string; name: string; description?: string }) => Promise<void>; onClose: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [id, setId] = useState(category?.id ?? "");
  const [name, setName] = useState(category?.name ?? "");
  const [desc, setDesc] = useState(category?.description ?? "");

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--config" onClick={(e) => e.stopPropagation()}>
        <h3>{category ? "编辑类别" : "新建类别"}</h3>
        <div className="form-grid">
          <label>ID <input value={id} onChange={(e) => setId(e.target.value)} disabled={!!category} placeholder="trade-policy" /></label>
          <label>名称 <input value={name} onChange={(e) => setName(e.target.value)} placeholder="贸易政策" /></label>
          <label className="span-2">描述 <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="贸易政策、关税调整、自贸协定" /></label>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={async () => {
            setSaving(true); try { await onSave({ id, name, description: desc || undefined }); }
            catch (e) { alert("保存失败"); } setSaving(false);
          }} disabled={saving || !id || !name}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
