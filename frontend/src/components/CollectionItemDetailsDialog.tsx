"use client";

import { Camera, Check, Edit3, Images, MapPin, PackageOpen, Star, Trash2, X } from "lucide-react";
import Image from "next/image";
import { useState } from "react";
import { api, collectionPhotoUrl } from "@/lib/api";
import type { CollectCollection, CollectionItem } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";

function displayValue(type: string, value: unknown) {
  if (type === "checkbox") return value ? "Да" : "Нет";
  if (type === "price" && typeof value === "number") return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value);
  if (type === "rating") return `${value} / 5`;
  return String(value ?? "—");
}

export function CollectionItemDetailsDialog({
  item,
  collection,
  onClose,
  onEdit,
  onUpdated,
  onDeleted,
}: {
  item: CollectionItem;
  collection: CollectCollection | undefined;
  onClose: () => void;
  onEdit: () => void;
  onUpdated: (item: CollectionItem) => void;
  onDeleted: () => void;
}) {
  const [activePhotoId, setActivePhotoId] = useState((item.photos.find((photo) => photo.is_cover) || item.photos[0])?.id || null);
  const [working, setWorking] = useState(false);
  const feedback = useFeedback();
  const fields = [...(collection?.fields || [])].sort((a, b) => a.position - b.position).filter((field) => item.custom_values[field.id] !== undefined);
  const activePhoto = item.photos.find((photo) => photo.id === activePhotoId);

  const removeItem = async () => {
    if (!await feedback.confirm({ title: "Удалить предмет?", message: `«${item.name}» и все его фотографии будут удалены без возможности восстановления.`, confirmLabel: "Удалить предмет", destructive: true })) return;
    setWorking(true); await api(`/collections/items/${item.id}`, { method: "DELETE" }); onDeleted();
  };
  const setCover = async () => {
    if (!activePhoto || activePhoto.is_cover) return;
    setWorking(true);
    try { onUpdated(await api<CollectionItem>(`/collections/photos/${activePhoto.id}/cover`, { method: "POST" })); }
    finally { setWorking(false); }
  };
  const removePhoto = async () => {
    if (!activePhoto || !await feedback.confirm({ title: "Удалить фотографию?", message: "Фотография будет удалена без возможности восстановления.", confirmLabel: "Удалить фотографию", destructive: true })) return;
    setWorking(true);
    try {
      const updated = await api<CollectionItem>(`/collections/photos/${activePhoto.id}`, { method: "DELETE" });
      setActivePhotoId(updated.photos[0]?.id || null); onUpdated(updated);
    } finally { setWorking(false); }
  };

  return (
    <div className="modal-backdrop collect-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal collect-detail-modal" role="dialog" aria-modal="true" aria-labelledby="collect-detail-title">
        <button className="collect-detail-close" type="button" onClick={onClose} aria-label="Закрыть"><X size={19} /></button>
        <section className="collect-detail-gallery">
          <div className="collect-detail-main-photo" style={{ background: collection?.color }}>
            {activePhoto ? <Image src={collectionPhotoUrl(activePhoto.id, "full")} alt={`Фотография «${item.name}»`} fill unoptimized sizes="(max-width: 700px) 100vw, 55vw" /> : <span><PackageOpen size={64} strokeWidth={1.2} /><small>Фотографии пока не добавлены</small></span>}
            {activePhoto?.is_cover && <i><Check size={13} />Обложка</i>}
          </div>
          {item.photos.length > 0 && <div className="collect-detail-thumbs">{item.photos.map((photo) => <button type="button" className={photo.id === activePhotoId ? "active" : ""} key={photo.id} onClick={() => setActivePhotoId(photo.id)}><Image src={collectionPhotoUrl(photo.id)} alt="" fill unoptimized sizes="80px" />{photo.is_cover && <Star size={12} fill="currentColor" />}</button>)}</div>}
          {activePhoto && <div className="collect-photo-actions"><button className="button" type="button" disabled={working || activePhoto.is_cover} onClick={() => void setCover()}><Star size={15} />Сделать обложкой</button><button className="button danger-subtle" type="button" disabled={working} onClick={() => void removePhoto()}><Trash2 size={15} />Удалить фото</button></div>}
        </section>
        <section className="collect-detail-copy">
          <div className="collect-detail-kicker"><span style={{ background: collection?.color }} /><small>{item.collection_name}</small></div>
          <h2 id="collect-detail-title">{item.name}</h2>
          <div className="collect-detail-facts">
            {item.location && <span><MapPin size={15} /><i>Место</i><strong>{item.location}</strong></span>}
            <span><PackageOpen size={15} /><i>Количество</i><strong>{item.quantity}</strong></span>
            <span><Images size={15} /><i>Фотографии</i><strong>{item.photos.length}</strong></span>
          </div>
          {item.description && <p className="collect-detail-description">{item.description}</p>}
          {fields.length > 0 && <div className="collect-detail-fields">{fields.map((field) => <div key={field.id}><small>{field.name}</small><strong>{displayValue(field.field_type, item.custom_values[field.id])}</strong></div>)}</div>}
          {item.tags.length > 0 && <div className="collect-detail-tags">{item.tags.map((tag) => <span key={tag.id} style={{ borderColor: tag.color }}><i style={{ background: tag.color }} />{tag.name}</span>)}</div>}
          <div className="collect-detail-actions"><button className="button primary collect-primary" type="button" onClick={onEdit}><Edit3 size={16} />Редактировать</button><button className="button danger-subtle" type="button" disabled={working} onClick={() => void removeItem()}><Trash2 size={16} />Удалить предмет</button><button className="button" type="button" onClick={onEdit}><Camera size={16} />Добавить ракурсы</button></div>
        </section>
      </div>
    </div>
  );
}
