"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section className="content-page system-state-page">
      <div className="empty-state">
        <div>
          <div className="eyebrow">Неожиданная ошибка</div>
          <h1>Что-то пошло не так</h1>
          <p>Попробуйте обновить этот экран. Ваши данные не были удалены.</p>
          <button className="button primary" type="button" onClick={reset}>Попробовать снова</button>
        </div>
      </div>
    </section>
  );
}
