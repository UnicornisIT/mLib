"use client";

import { ArrowDown, ArrowUp, Edit3, Plus, Trash2, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import type { CollectCollection, CollectionField, CollectionFieldType } from "@/lib/types";
import { FriendlySelect } from "@/components/FriendlySelect";
import { useFeedback } from "@/providers/FeedbackProvider";

const fieldTypes: { value: CollectionFieldType; label: string }[] = [
  { value: "text", label: "Одна строка" }, { value: "long_text", label: "Несколько строк" },
  { value: "number", label: "Просто число" }, { value: "price", label: "Стоимость" },
  { value: "date", label: "Дата" }, { value: "rating", label: "Оценка от 0 до 5" },
  { value: "checkbox", label: "Ответ «да» или «нет»" }, { value: "select", label: "Выбор из списка" },
  { value: "url", label: "Ссылка" },
];

export function CollectionFieldsDialog({
  open,
  collection,
  onClose,
  onChanged,
}: {
  open: boolean;
  collection: CollectCollection | null;
  onClose: () => void;
  onChanged: () => Promise<void> | void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState<CollectionFieldType>("text");
  const [required, setRequired] = useState(false);
  const [showOnCard, setShowOnCard] = useState(false);
  const [options, setOptions] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const feedback = useFeedback();

  if (!open || !collection) return null;
  const fields = [...collection.fields].sort((a, b) => a.position - b.position);

  const add = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      await api(`/collections/${collection.id}/fields`, {
        method: "POST",
        body: { name: name.trim(), field_type: type, required, show_on_card: showOnCard, options: options.split("\n").map((value) => value.trim()).filter(Boolean) },
      });
      setName(""); setOptions(""); setRequired(false); setShowOnCard(false); await onChanged();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось добавить поле"); }
    finally { setSaving(false); }
  };
  const patch = async (field: CollectionField, body: object) => { await api(`/collections/fields/${field.id}`, { method: "PATCH", body }); await onChanged(); };
  const move = async (index: number, direction: -1 | 1) => {
    const other = fields[index + direction]; if (!other) return;
    await Promise.all([patch(fields[index], { position: other.position }), patch(other, { position: fields[index].position })]);
  };
  const remove = async (field: CollectionField) => {
    if (!await feedback.confirm({ title: "Удалить поле?", message: `Поле «${field.name}» и его значения у всех предметов будут удалены.`, confirmLabel: "Удалить поле", destructive: true })) return;
    await api(`/collections/fields/${field.id}`, { method: "DELETE" }); await onChanged();
  };
  const edit = async (field: CollectionField) => {
    const nextName = await feedback.prompt({ title: "Название поля", message: "Измените название строки в карточке предмета.", defaultValue: field.name, confirmLabel: "Сохранить" });
    if (nextName === null || !nextName.trim()) return;
    const body: { name: string; options?: string[] } = { name: nextName.trim() };
    if (field.field_type === "select") {
      const nextOptions = await feedback.prompt({ title: "Варианты выбора", message: "Перечислите варианты через запятую.", defaultValue: field.options.join(", "), confirmLabel: "Сохранить", allowEmpty: true });
      if (nextOptions === null) return;
      body.options = nextOptions.split(",").map((value) => value.trim()).filter(Boolean);
    }
    await patch(field, body);
  };

  return (
    <div className="modal-backdrop collect-modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="modal collect-fields-modal" role="dialog" aria-modal="true" aria-labelledby="fields-dialog-title">
        <div className="collect-modal-header"><div><span>{collection.name}</span><h2 id="fields-dialog-title">Содержимое карточки</h2></div><button type="button" onClick={onClose} aria-label="Закрыть"><X size={19} /></button></div>
        <div className="collect-fields-layout">
          <div className="collect-field-list">
            <p>Выберите, что вы хотите записывать о предметах. Порядок строк можно менять стрелками.</p>
            {fields.length ? fields.map((field, index) => (
              <div className="collect-field-row" key={field.id}>
                <span><strong>{field.name}</strong><small>{fieldTypes.find((entry) => entry.value === field.field_type)?.label}</small><span className="collect-field-toggles"><label><input type="checkbox" checked={field.required} onChange={(event) => void patch(field, { required: event.target.checked })} />Просить заполнить</label><label><input type="checkbox" checked={field.show_on_card} onChange={(event) => void patch(field, { show_on_card: event.target.checked })} />Видно в списке</label></span></span>
                <div><button type="button" onClick={() => void edit(field)} aria-label="Редактировать"><Edit3 size={15} /></button><button type="button" onClick={() => void move(index, -1)} disabled={index === 0} aria-label="Выше"><ArrowUp size={15} /></button><button type="button" onClick={() => void move(index, 1)} disabled={index === fields.length - 1} aria-label="Ниже"><ArrowDown size={15} /></button><button type="button" className="danger" onClick={() => void remove(field)} aria-label="Удалить"><Trash2 size={15} /></button></div>
              </div>
            )) : <div className="collect-fields-empty">Добавьте первое поле справа.</div>}
          </div>
          <form className="collect-field-create" onSubmit={add}>
            <h3><Plus size={17} />Добавить строку</h3>
            <label className="field"><span>Что записываем?</span><input className="input" required value={name} onChange={(event) => setName(event.target.value)} placeholder="Например, Год выпуска" /></label>
            <label className="field"><span>Как будем заполнять?</span><FriendlySelect className="friendly-select-field" value={type} onChange={(value) => setType(value as CollectionFieldType)} ariaLabel="Способ заполнения" options={fieldTypes} /></label>
            {type === "select" && <label className="field"><span>Варианты — по одному в строке</span><textarea className="textarea" required rows={5} value={options} onChange={(event) => setOptions(event.target.value)} placeholder={"Новое\nХорошее\nТребует ремонта"} /></label>}
            <label className="collect-check"><input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} /><span>Просить заполнить</span></label>
            <label className="collect-check"><input type="checkbox" checked={showOnCard} onChange={(event) => setShowOnCard(event.target.checked)} /><span>Показывать в списке предметов</span></label>
            {error && <div className="form-error">{error}</div>}
            <button className="button primary collect-primary" disabled={saving || !name.trim()}>{saving ? "Добавляем…" : "Добавить в карточку"}</button>
          </form>
        </div>
      </div>
    </div>
  );
}
