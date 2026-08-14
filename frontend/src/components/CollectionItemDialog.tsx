"use client";

import { Camera, MapPin, Plus, Tag as TagIcon, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { FriendlySelect } from "@/components/FriendlySelect";
import type {
  CollectCollection,
  CollectionField,
  CollectionFieldValue,
  CollectionItem,
  CollectionTag,
} from "@/lib/types";

function initialValues(item: CollectionItem | null): Record<string, CollectionFieldValue> {
  return item ? { ...item.custom_values } : {};
}

function FieldInput({ field, value, onChange }: { field: CollectionField; value: CollectionFieldValue | undefined; onChange: (value: CollectionFieldValue) => void }) {
  if (field.field_type === "checkbox") return <label className="collect-check collect-dynamic-check"><input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} /><span>{field.name}{field.required ? " *" : ""}</span></label>;
  if (field.field_type === "long_text") return <label className="field collect-wide"><span>{field.name}{field.required ? " *" : ""}</span><textarea className="textarea" rows={3} required={field.required} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} /></label>;
  if (field.field_type === "select") return <label className="field"><span>{field.name}{field.required ? " *" : ""}</span><FriendlySelect className="friendly-select-field" value={String(value ?? "")} onChange={onChange} ariaLabel={`Выбрать: ${field.name}`} options={[{ value: "", label: "Пока не выбрано" }, ...field.options.map((option) => ({ value: option, label: option }))]} /></label>;
  const type = field.field_type === "date" ? "date" : field.field_type === "url" ? "url" : ["number", "price", "rating"].includes(field.field_type) ? "number" : "text";
  return <label className="field"><span>{field.name}{field.required ? " *" : ""}</span><input className="input" type={type} required={field.required} min={field.field_type === "rating" ? 0 : undefined} max={field.field_type === "rating" ? 5 : undefined} step={["price", "rating"].includes(field.field_type) ? "0.01" : field.field_type === "number" ? "any" : undefined} value={String(value ?? "")} onChange={(event) => onChange(type === "number" ? (event.target.value === "" ? null : Number(event.target.value)) : event.target.value)} /></label>;
}

export function CollectionItemDialog({
  open,
  item,
  collections,
  tags,
  locations,
  defaultCollectionId,
  onClose,
  onSaved,
  onTagsChanged,
}: {
  open: boolean;
  item: CollectionItem | null;
  collections: CollectCollection[];
  tags: CollectionTag[];
  locations: string[];
  defaultCollectionId: string | null;
  onClose: () => void;
  onSaved: (item: CollectionItem) => void;
  onTagsChanged: () => Promise<CollectionTag[]>;
}) {
  const photoInput = useRef<HTMLInputElement>(null);
  const [collectionId, setCollectionId] = useState(item?.collection_id || defaultCollectionId || collections[0]?.id || "");
  const [name, setName] = useState(item?.name || "");
  const [description, setDescription] = useState(item?.description || "");
  const [quantity, setQuantity] = useState(String(item?.quantity || 1));
  const [location, setLocation] = useState(item?.location || "");
  const [values, setValues] = useState<Record<string, CollectionFieldValue>>(initialValues(item));
  const [selectedTags, setSelectedTags] = useState<string[]>(item?.tags.map((tag) => tag.id) || []);
  const [newTag, setNewTag] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const previews = useMemo(() => photos.map((photo) => ({ name: photo.name, url: URL.createObjectURL(photo) })), [photos]);
  const selectedCollection = collections.find((collection) => collection.id === collectionId);

  useEffect(() => () => previews.forEach((preview) => URL.revokeObjectURL(preview.url)), [previews]);
  if (!open) return null;

  const selectCollection = (next: string) => { setCollectionId(next); if (next !== item?.collection_id) setValues({}); };
  const createTag = async () => {
    if (!newTag.trim()) return;
    try {
      const tag = await api<CollectionTag>("/collections/tags", { method: "POST", body: { name: newTag.trim(), color: "#8b6f5d" } });
      await onTagsChanged(); setSelectedTags((current) => [...current, tag.id]); setNewTag("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось добавить тег"); }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const body = {
        collection_id: collectionId,
        name: name.trim(),
        description: description.trim() || null,
        quantity: Number(quantity),
        location: location.trim() || null,
        tag_ids: selectedTags,
        custom_values: values,
      };
      let saved = await api<CollectionItem>(item ? `/collections/items/${item.id}` : "/collections/items", { method: item ? "PATCH" : "POST", body });
      if (photos.length) {
        const data = new FormData(); photos.forEach((photo) => data.append("files", photo));
        saved = await api<CollectionItem>(`/collections/items/${saved.id}/photos`, { method: "POST", body: data });
      }
      onSaved(saved); onClose();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось сохранить предмет"); }
    finally { setSaving(false); }
  };

  return (
    <div className="modal-backdrop collect-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <form className="modal collect-item-modal" role="dialog" aria-modal="true" aria-labelledby="item-dialog-title" onSubmit={submit}>
        <div className="collect-modal-header"><div><span>collectLib · карточка предмета</span><h2 id="item-dialog-title">{item ? "Редактирование" : "Новый предмет"}</h2></div><button type="button" onClick={onClose} aria-label="Закрыть"><X size={19} /></button></div>
        <div className="collect-item-form-body">
          <aside className="collect-photo-picker">
            <input ref={photoInput} hidden type="file" multiple accept="image/jpeg,image/png,image/webp,image/avif" onChange={(event) => setPhotos(Array.from(event.target.files || []))} />
            <button type="button" className="collect-photo-drop" onClick={() => photoInput.current?.click()}><Camera size={27} /><strong>{photos.length ? `${photos.length} фото выбрано` : item?.photos.length ? "Добавить ракурсы" : "Добавить фотографии"}</strong><small>Первый снимок станет обложкой. До 20 файлов.</small></button>
            {previews.length > 0 && <div className="collect-photo-previews">{previews.map((preview, index) => <span key={`${preview.name}-${index}`} style={{ backgroundImage: `url(${preview.url})` }} title={preview.name}>{index === 0 && !item?.photos.length ? <i>Обложка</i> : null}</span>)}</div>}
            {item?.photos.length ? <p>У предмета уже {item.photos.length} фото. Управлять обложкой и удалять снимки можно в просмотре карточки.</p> : null}
          </aside>
          <div className="collect-item-fields">
            <label className="field collect-wide"><span>В какую коллекцию добавить? *</span><FriendlySelect className="friendly-select-field" value={collectionId} onChange={selectCollection} ariaLabel="Выбрать коллекцию" options={collections.map((collection) => ({ value: collection.id, label: collection.name }))} /></label>
            <label className="field collect-wide"><span>Название *</span><input className="input" required maxLength={500} value={name} onChange={(event) => setName(event.target.value)} placeholder="Название предмета" /></label>
            <label className="field"><span>Количество</span><input className="input" type="number" min="1" max="1000000" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
            <label className="field"><span><MapPin size={13} />Местоположение</span><input className="input" list="collect-location-options" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Комната · стеллаж · полка" /><datalist id="collect-location-options">{locations.map((value) => <option key={value} value={value} />)}</datalist></label>
            <label className="field collect-wide"><span>Описание</span><textarea className="textarea" rows={4} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Состояние, история или важные заметки" /></label>
            {selectedCollection?.fields.length ? <div className="collect-dynamic-fields collect-wide"><h3>Поля коллекции</h3><div>{[...selectedCollection.fields].sort((a, b) => a.position - b.position).map((field) => <FieldInput key={field.id} field={field} value={values[field.id]} onChange={(value) => setValues((current) => ({ ...current, [field.id]: value }))} />)}</div></div> : null}
            <div className="collect-tag-picker collect-wide"><span><TagIcon size={13} />Отметки</span><div className="collect-tag-options">{tags.map((tag) => <label key={tag.id} style={{ borderColor: selectedTags.includes(tag.id) ? tag.color : undefined }}><input type="checkbox" checked={selectedTags.includes(tag.id)} onChange={(event) => setSelectedTags((current) => event.target.checked ? [...current, tag.id] : current.filter((id) => id !== tag.id))} /><i style={{ background: tag.color }} />{tag.name}</label>)}</div><div className="collect-new-tag"><input className="input" value={newTag} onChange={(event) => setNewTag(event.target.value)} placeholder="Новая отметка" /><button className="button collect-soft-button" type="button" onClick={() => void createTag()} disabled={!newTag.trim()}><Plus size={15} />Добавить</button></div></div>
            {error && <div className="form-error collect-wide">{error}</div>}
          </div>
        </div>
        <div className="collect-modal-footer"><button className="button" type="button" onClick={onClose} disabled={saving}>Отмена</button><button className="button primary collect-primary" type="submit" disabled={saving || !name.trim() || !collectionId}>{saving ? "Сохраняем…" : item ? "Сохранить изменения" : "Добавить предмет"}</button></div>
      </form>
    </div>
  );
}
