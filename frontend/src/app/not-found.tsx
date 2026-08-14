import Link from "next/link";

export default function NotFound() {
  return (
    <section className="content-page system-state-page">
      <div className="empty-state">
        <div>
          <div className="eyebrow">Ошибка 404</div>
          <h1>Страница не найдена</h1>
          <p>Возможно, она была удалена или адрес изменился.</p>
          <Link className="button primary" href="/">Вернуться на главную</Link>
        </div>
      </div>
    </section>
  );
}
