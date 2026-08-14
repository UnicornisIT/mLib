"use client";

import {
  Boxes,
  Camera,
  Clock3,
  LayoutGrid,
  ListFilter,
  MapPin,
  PackageOpen,
  PencilRuler,
  Plus,
  Search,
  Settings2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CollectionBulkBar } from "@/components/CollectionBulkBar";
import { CollectionDialog } from "@/components/CollectionDialog";
import { CollectionFieldsDialog } from "@/components/CollectionFieldsDialog";
import { CollectionItemCard } from "@/components/CollectionItemCard";
import { CollectionItemDetailsDialog } from "@/components/CollectionItemDetailsDialog";
import { CollectionItemDialog } from "@/components/CollectionItemDialog";
import { FriendlySelect } from "@/components/FriendlySelect";
import { api } from "@/lib/api";
import type {
  CollectCollection,
  CollectionItem,
  CollectionItemPage,
  CollectionsDashboard,
  CollectionTag,
} from "@/lib/types";

export default function CollectionsPage() {
  const [collections, setCollections] = useState<CollectCollection[]>([]);
  const [itemsPage, setItemsPage] = useState<CollectionItemPage | null>(null);
  const [dashboard, setDashboard] = useState<CollectionsDashboard | null>(null);
  const [tags, setTags] = useState<CollectionTag[]>([]);
  const [activeCollectionId, setActiveCollectionId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [tagId, setTagId] = useState("");
  const [sort, setSort] = useState("updated");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [openItem, setOpenItem] = useState<CollectionItem | null>(null);
  const [editItem, setEditItem] = useState<CollectionItem | null>(null);
  const [itemDialogOpen, setItemDialogOpen] = useState(false);
  const [collectionDialogOpen, setCollectionDialogOpen] = useState(false);
  const [editCollection, setEditCollection] = useState<CollectCollection | null>(null);
  const [fieldsOpen, setFieldsOpen] = useState(false);
  const [error, setError] = useState("");
  const activeCollection = collections.find((entry) => entry.id === activeCollectionId) || null;

  const loadCollections = useCallback(async () => {
    const result = await api<CollectCollection[]>("/collections");
    setCollections(result);
    setActiveCollectionId((current) => current && result.some((collection) => collection.id === current) ? current : null);
    return result;
  }, []);
  const loadTags = useCallback(async () => { const result = await api<CollectionTag[]>("/collections/tags"); setTags(result); return result; }, []);
  const loadItems = useCallback(async () => {
    const params = new URLSearchParams({ sort });
    if (activeCollectionId) params.set("collection_id", activeCollectionId);
    if (query.trim()) params.set("q", query.trim());
    if (location) params.set("location", location);
    if (tagId) params.set("tag_id", tagId);
    const result = await api<CollectionItemPage>(`/collections/items?${params}`);
    setItemsPage(result); return result;
  }, [activeCollectionId, location, query, sort, tagId]);
  const loadAll = useCallback(async () => {
    try {
      const [, , stats] = await Promise.all([loadCollections(), loadTags(), api<CollectionsDashboard>("/collections/dashboard")]);
      setDashboard(stats); setError("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось открыть collectLib"); }
  }, [loadCollections, loadTags]);

  useEffect(() => { const timer = window.setTimeout(() => void loadAll(), 0); return () => window.clearTimeout(timer); }, [loadAll]);
  useEffect(() => { const timer = window.setTimeout(() => void loadItems().catch((caught) => setError(caught instanceof Error ? caught.message : "Не удалось загрузить предметы")), 220); return () => window.clearTimeout(timer); }, [loadItems]);

  const refresh = async () => {
    await Promise.all([loadCollections(), loadItems(), api<CollectionsDashboard>("/collections/dashboard").then(setDashboard)]);
  };
  const updateOpenItem = (item: CollectionItem) => { setOpenItem(item); setItemsPage((current) => current ? { ...current, items: current.items.map((entry) => entry.id === item.id ? item : entry) } : current); };
  const toggleSelected = (id: string) => setSelectedIds((current) => current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]);
  const collectionMap = useMemo(() => new Map(collections.map((collection) => [collection.id, collection])), [collections]);
  const addItem = () => { if (!collections.length) { setEditCollection(null); setCollectionDialogOpen(true); return; } setEditItem(null); setItemDialogOpen(true); };

  return (
    <div className="collect-page">
      <header className="collect-nav">
        <nav aria-label="Разделы collectLib"><button className="active" type="button">Предметы</button><button type="button" onClick={() => document.getElementById("collect-collections")?.scrollIntoView({ behavior: "smooth" })}>Коллекции</button></nav>
        <button className="button primary collect-primary" type="button" onClick={addItem}><Plus size={17} />Добавить предмет</button>
      </header>

      <div className="service-page-content">
        <section className="collect-hero">
          <div className="collect-hero-copy"><span>Коллекции, которые можно потрогать</span><h1>Каждая вещь<br />на своём месте.</h1><p>Фотографируйте предметы с разных ракурсов, описывайте их своими полями и всегда знайте, где они находятся.</p><button className="button primary collect-primary" type="button" onClick={addItem}><Plus size={18} />{dashboard?.items ? "Добавить предмет" : "Начать коллекцию"}</button></div>
          <div className="collect-hero-art" aria-hidden="true"><i><Camera /></i><i><PackageOpen /></i><i><MapPin /></i><span /></div>
          {dashboard && <div className="collect-stats"><span><Boxes /><strong>{dashboard.collections}</strong><small>коллекций</small></span><span><PackageOpen /><strong>{dashboard.items}</strong><small>предметов</small></span><span><Camera /><strong>{dashboard.photos}</strong><small>фотографий</small></span><span><MapPin /><strong>{dashboard.locations}</strong><small>мест хранения</small></span></div>}
        </section>

        {error && <div className="form-error collect-page-error">{error}</div>}

        <section className="collect-collections-strip" id="collect-collections">
          <div className="collect-section-heading"><div><span>Структура библиотеки</span><h2>Коллекции</h2></div><button className="button collect-soft-button" type="button" onClick={() => { setEditCollection(null); setCollectionDialogOpen(true); }}><Plus size={16} />Добавить коллекцию</button></div>
          <div className="collect-collection-pills">
            <button className={!activeCollectionId ? "active" : ""} type="button" onClick={() => { setActiveCollectionId(null); setSelectedIds([]); }}><span className="collect-pill-icon all"><LayoutGrid /></span><strong>Все предметы</strong><small>{dashboard?.items || 0}</small></button>
            {collections.map((collection) => <button className={activeCollectionId === collection.id ? "active" : ""} type="button" key={collection.id} onClick={() => { setActiveCollectionId(collection.id); setSelectedIds([]); }}><span className="collect-pill-icon" style={{ background: collection.color }}><PackageOpen /></span><strong>{collection.name}</strong><small>{collection.item_count}</small></button>)}
          </div>
        </section>

        <section className="collect-library">
          <div className="collect-section-heading collect-library-heading">
            <div><span>{activeCollection ? "Выбранная коллекция" : "Вся ваша библиотека"}</span><h2>{activeCollection?.name || "Все предметы"}</h2>{activeCollection?.description && <p>{activeCollection.description}</p>}</div>
            {activeCollection && <div className="collect-collection-actions"><button className="button collect-soft-button" type="button" onClick={() => setFieldsOpen(true)}><PencilRuler size={15} />Что показывать</button><button className="button collect-soft-button" type="button" onClick={() => { setEditCollection(activeCollection); setCollectionDialogOpen(true); }}><Settings2 size={15} />О коллекции</button></div>}
          </div>

          <div className="collect-toolbar">
            <label className="collect-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название, место или отметка…" /></label>
            <FriendlySelect value={location} onChange={(value) => { setLocation(value); setSelectedIds([]); }} icon={MapPin} ariaLabel="Выбрать место" options={[{ value: "", label: "В любом месте" }, ...(itemsPage?.locations || []).map((value) => ({ value, label: value }))]} />
            <FriendlySelect value={tagId} onChange={(value) => { setTagId(value); setSelectedIds([]); }} icon={ListFilter} ariaLabel="Выбрать отметку" options={[{ value: "", label: "С любой отметкой" }, ...tags.map((tag) => ({ value: tag.id, label: tag.name }))]} />
            <FriendlySelect value={sort} onChange={setSort} icon={Clock3} ariaLabel="Выбрать порядок" options={[{ value: "updated", label: "Недавно менялись" }, { value: "created", label: "Недавно добавлены" }, { value: "name", label: "По названию" }, { value: "location", label: "По месту хранения" }]} />
          </div>

          {itemsPage === null ? <div className="collect-loading"><span className="loading-mark" /></div> : itemsPage.items.length ? <div className="collect-grid">{itemsPage.items.map((item) => <CollectionItemCard key={item.id} item={item} collection={collectionMap.get(item.collection_id)} selected={selectedIds.includes(item.id)} selectionMode={selectedIds.length > 0} onSelect={() => toggleSelected(item.id)} onOpen={() => setOpenItem(item)} />)}</div> : <div className="collect-empty"><span><PackageOpen size={34} /></span><h3>{query || location || tagId ? "Ничего не найдено" : activeCollection ? "В коллекции пока пусто" : "Создайте свою первую коллекцию"}</h3><p>{query || location || tagId ? "Попробуйте изменить запрос или фильтры." : "Добавьте предмет, загрузите фотографии и укажите, где он хранится."}</p><button className="button primary collect-primary" type="button" onClick={addItem}><Plus size={16} />Добавить предмет</button></div>}
        </section>
      </div>

      <CollectionBulkBar selectedIds={selectedIds} collections={collections} tags={tags} onClear={() => setSelectedIds([])} onDone={refresh} />
      {collectionDialogOpen && <CollectionDialog key={editCollection?.id || "new"} open collection={editCollection} onClose={() => setCollectionDialogOpen(false)} onSaved={() => { void loadAll(); }} onDeleted={() => { setActiveCollectionId(null); void refresh(); }} />}
      {fieldsOpen && <CollectionFieldsDialog open collection={activeCollection} onClose={() => setFieldsOpen(false)} onChanged={() => loadCollections().then(() => undefined)} />}
      {itemDialogOpen && <CollectionItemDialog key={editItem?.id || "new"} open item={editItem} collections={collections} tags={tags} locations={itemsPage?.locations || []} defaultCollectionId={activeCollectionId} onClose={() => setItemDialogOpen(false)} onSaved={(item) => { setOpenItem(item); void refresh(); }} onTagsChanged={loadTags} />}
      {openItem && <CollectionItemDetailsDialog item={openItem} collection={collectionMap.get(openItem.collection_id)} onClose={() => setOpenItem(null)} onEdit={() => { setEditItem(openItem); setItemDialogOpen(true); setOpenItem(null); }} onUpdated={updateOpenItem} onDeleted={() => { setOpenItem(null); void refresh(); }} />}
    </div>
  );
}
