import { Check, Images, MapPin, PackageOpen } from "lucide-react";
import Image from "next/image";
import { collectionPhotoUrl } from "@/lib/api";
import type { CollectCollection, CollectionItem } from "@/lib/types";

function valueLabel(value: unknown) {
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  return String(value ?? "");
}

export function CollectionItemCard({
  item,
  collection,
  selected,
  selectionMode,
  onSelect,
  onOpen,
}: {
  item: CollectionItem;
  collection: CollectCollection | undefined;
  selected: boolean;
  selectionMode: boolean;
  onSelect: () => void;
  onOpen: () => void;
}) {
  const cover = item.photos.find((photo) => photo.is_cover) || item.photos[0];
  const cardFields = (collection?.fields || [])
    .filter((field) => field.show_on_card && item.custom_values[field.id] !== undefined)
    .slice(0, 2);
  const open = () => selectionMode ? onSelect() : onOpen();

  return (
    <article className={`collect-item-card ${selected ? "selected" : ""}`}>
      <button className="collect-card-poster" type="button" onClick={open} aria-label={`Открыть «${item.name}»`}>
        {cover ? (
          <Image src={collectionPhotoUrl(cover.id)} alt={`Фотография «${item.name}»`} fill unoptimized sizes="(max-width: 640px) 46vw, 260px" />
        ) : (
          <span className="collect-card-placeholder" style={{ background: collection?.color }}>
            <PackageOpen size={42} strokeWidth={1.35} />
            <small>{item.collection_name}</small>
          </span>
        )}
        <span className="collect-card-shade" />
        {item.photos.length > 1 && <span className="collect-photo-count"><Images size={13} />{item.photos.length}</span>}
        {item.quantity > 1 && <span className="collect-quantity">×{item.quantity}</span>}
        <span className={`collect-select-mark ${selectionMode ? "visible" : ""}`} onClick={(event) => { event.stopPropagation(); onSelect(); }}>
          {selected ? <Check size={16} /> : null}
        </span>
        <span className="collect-card-caption">
          <small>{item.collection_name}</small>
          <strong>{item.name}</strong>
        </span>
      </button>
      <div className="collect-card-copy">
        {item.location && <span className="collect-location"><MapPin size={13} />{item.location}</span>}
        {cardFields.map((field) => <span key={field.id}><small>{field.name}</small>{valueLabel(item.custom_values[field.id])}</span>)}
        {item.tags.length > 0 && <div className="collect-card-tags">{item.tags.slice(0, 3).map((tag) => <i key={tag.id} style={{ borderColor: tag.color }}>{tag.name}</i>)}</div>}
      </div>
    </article>
  );
}
