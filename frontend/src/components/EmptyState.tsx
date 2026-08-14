import { Music2 } from "lucide-react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div>
        <div className="empty-icon"><Music2 size={26} /></div>
        <h3>{title}</h3>
        <p>{description}</p>
        {action}
      </div>
    </div>
  );
}

export function PageLoader({ rows = 6 }: { rows?: number }) {
  return (
    <div className="table-shell" aria-label="Загрузка">
      {Array.from({ length: rows }, (_, index) => <div className="skeleton skeleton-row" key={index} />)}
    </div>
  );
}

