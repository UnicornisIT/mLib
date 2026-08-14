"use client";

import { FormEvent, useState } from "react";
import { Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { CollectCollection } from "@/lib/types";
import { useFeedback } from "@/providers/FeedbackProvider";

const colors = ["#b96842", "#496f62", "#526a91", "#80619b", "#a45462", "#8a733f", "#4e747e", "#755b4b"];

export function CollectionDialog({
  open,
  collection,
  onClose,
  onSaved,
  onDeleted,
}: {
  open: boolean;
  collection?: CollectCollection | null;
  onClose: () => void;
  onSaved: (collection: CollectCollection) => void;
  onDeleted?: () => void;
}) {
  const [name, setName] = useState(collection?.name || "");
  const [description, setDescription] = useState(collection?.description || "");
  const [color, setColor] = useState(collection?.color || colors[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const feedback = useFeedback();

  if (!open) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      const saved = await api<CollectCollection>(collection ? `/collections/${collection.id}` : "/collections", {
        method: collection ? "PATCH" : "POST",
        body: { name: name.trim(), description: description.trim() || null, color },
      });
      onSaved(saved); onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить коллекцию");
    } finally { setSaving(false); }
  };
  const remove = async () => {
    if (!collection || !await feedback.confirm({ title: "Удалить коллекцию?", message: `«${collection.name}», все предметы и фотографии в ней будут удалены без возможности восстановления.`, confirmLabel: "Удалить коллекцию", destructive: true })) return;
    setSaving(true); setError("");
    try { await api(`/collections/${collection.id}`, { method: "DELETE" }); onDeleted?.(); onClose(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось удалить коллекцию"); }
    finally { setSaving(false); }
  };

  return (
    <div className="modal-backdrop collect-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <form className="modal collect-small-modal" role="dialog" aria-modal="true" aria-labelledby="collection-dialog-title" onSubmit={submit}>
        <div className="collect-modal-header"><div><span>collectLib · коллекция</span><h2 id="collection-dialog-title">{collection ? "О коллекции" : "Новая коллекция"}</h2></div><button type="button" onClick={onClose} aria-label="Закрыть"><X size={19} /></button></div>
        <div className="collect-modal-body">
          <label className="field"><span>Название *</span><input className="input" required maxLength={255} value={name} onChange={(event) => setName(event.target.value)} placeholder="Например, Виниловые пластинки" /></label>
          <label className="field"><span>Описание</span><textarea className="textarea" rows={4} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Что входит в эту коллекцию" /></label>
          <fieldset className="collect-color-field"><legend>Цвет коллекции</legend><div>{colors.map((value) => <button key={value} type="button" className={color === value ? "active" : ""} style={{ background: value }} onClick={() => setColor(value)} aria-label={`Выбрать цвет ${value}`} />)}</div></fieldset>
          {error && <div className="form-error">{error}</div>}
        </div>
        <div className="collect-modal-footer">{collection && <button className="button danger-subtle collect-delete-collection" type="button" onClick={() => void remove()} disabled={saving}><Trash2 size={15} />Удалить</button>}<button className="button" type="button" onClick={onClose}>Отмена</button><button className="button primary collect-primary" type="submit" disabled={saving || !name.trim()}>{saving ? "Сохраняем…" : "Сохранить"}</button></div>
      </form>
    </div>
  );
}
