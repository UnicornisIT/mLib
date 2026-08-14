"use client";

import { ArrowRight, BookOpenText, Clapperboard, Gamepad2, Heart, Music2, PackageOpen } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type ServiceState = "checking" | "available" | "unavailable";
type ServiceStatuses = { music: ServiceState; movie: ServiceState; books: ServiceState; games: ServiceState; wishes: ServiceState; collections: ServiceState };
type ServiceStatusResponse = { music: { status: ServiceState }; movie: { status: ServiceState }; books: { status: ServiceState }; games: { status: ServiceState }; wishes: { status: ServiceState }; collections: { status: ServiceState } };

const statusLabels: Record<ServiceState, string> = {
  checking: "Проверяем",
  available: "Доступно",
  unavailable: "Недоступно",
};

function ServiceStatus({ status }: { status: ServiceState }) {
  return <span className={`service-status ${status === "available" ? "ready" : status}`} aria-live="polite"><span />{statusLabels[status]}</span>;
}

export default function HomePage() {
  const [statuses, setStatuses] = useState<ServiceStatuses>({ music: "checking", movie: "checking", books: "checking", games: "checking", wishes: "checking", collections: "checking" });

  useEffect(() => {
    let active = true;
    const check = () => {
      void api<ServiceStatusResponse>("/services/status")
        .then((result) => {
          if (active) setStatuses({ music: result.music.status, movie: result.movie.status, books: result.books.status, games: result.games.status, wishes: result.wishes.status, collections: result.collections.status });
        })
        .catch(() => {
          if (active) setStatuses({ music: "unavailable", movie: "unavailable", books: "unavailable", games: "unavailable", wishes: "unavailable", collections: "unavailable" });
        });
    };
    check();
    const interval = window.setInterval(check, 60_000);
    window.addEventListener("online", check);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("online", check);
    };
  }, []);

  return (
    <section className="hub-page">
      <div className="hub-intro">
        <div className="eyebrow">Ваше пространство mLib</div>
        <h1>Что откроем сегодня?</h1>
        <p>Музыка, фильмы, книги, игры и желания живут в одном месте и остаются под вашим контролем.</p>
      </div>

      <div className="service-grid">
        <Link href="/music" className="service-card music-service-card">
          <div className="service-card-topline">
            <span className="service-card-icon"><Music2 size={25} /></span>
          </div>
          <div className="service-card-copy">
            <span className="service-overline">Личная фонотека</span>
            <h2>music<span>Lib</span></h2>
            <p>Слушайте треки, собирайте плейлисты и управляйте своей музыкальной коллекцией.</p>
          </div>
          <div className="service-card-footer">
            <span className="service-card-action">Открыть музыку <ArrowRight size={18} /></span>
            <ServiceStatus status={statuses.music} />
          </div>
          <div className="music-card-art" aria-hidden="true"><i /><i /><i /><i /></div>
        </Link>

        <Link href="/movie" className="service-card movie-service-card">
          <div className="service-card-topline">
            <span className="service-card-icon"><Clapperboard size={25} /></span>
          </div>
          <div className="service-card-copy">
            <span className="service-overline">Личный кинотрекер</span>
            <h2>movie<span>Lib</span></h2>
            <p>Находите фильмы и сериалы, отмечайте просмотренное и следите за прогрессом эпизодов.</p>
          </div>
          <div className="service-card-footer">
            <span className="service-card-action">Открыть фильмы <ArrowRight size={18} /></span>
            <ServiceStatus status={statuses.movie} />
          </div>
          <div className="movie-card-art" aria-hidden="true"><i /><i /><i /></div>
        </Link>

        <Link href="/books" className="service-card books-service-card">
          <div className="service-card-topline">
            <span className="service-card-icon"><BookOpenText size={25} /></span>
          </div>
          <div className="service-card-copy">
            <span className="service-overline">Личная книжная полка</span>
            <h2>book<span>Lib</span></h2>
            <p>Храните электронные и аудиокниги, добавляйте свои обложки и собирайте красивую библиотеку.</p>
          </div>
          <div className="service-card-footer">
            <span className="service-card-action">Открыть книги <ArrowRight size={18} /></span>
            <ServiceStatus status={statuses.books} />
          </div>
          <div className="books-card-art" aria-hidden="true"><i /><i /><i /></div>
        </Link>

        <Link href="/games" className="service-card games-service-card">
          <div className="service-card-topline">
            <span className="service-card-icon"><Gamepad2 size={25} /></span>
          </div>
          <div className="service-card-copy">
            <span className="service-overline">Личная игротека</span>
            <h2>game<span>Lib</span></h2>
            <p>Собирайте игры по платформам, отмечайте прохождение, время, оценки и достижения.</p>
          </div>
          <div className="service-card-footer">
            <span className="service-card-action">Открыть игры <ArrowRight size={18} /></span>
            <ServiceStatus status={statuses.games} />
          </div>
          <div className="games-card-art" aria-hidden="true"><i /><i /><i /><i /></div>
        </Link>

        <Link href="/wishes" className="service-card wishes-service-card">
          <div className="service-card-topline">
            <span className="service-card-icon"><Heart size={25} /></span>
          </div>
          <div className="service-card-copy">
            <span className="service-overline">Общая очередь желаний</span>
            <h2>wish<span>Lib</span></h2>
            <p>Сохраняйте, что хотите посмотреть, прочитать, послушать или купить — всё в одном списке.</p>
          </div>
          <div className="service-card-footer">
            <span className="service-card-action">Открыть желания <ArrowRight size={18} /></span>
            <ServiceStatus status={statuses.wishes} />
          </div>
          <div className="wishes-card-art" aria-hidden="true"><i /><i /><i /><i /></div>
        </Link>

        <Link href="/collections" className="service-card collections-service-card">
          <div className="service-card-topline">
            <span className="service-card-icon"><PackageOpen size={25} /></span>
          </div>
          <div className="service-card-copy">
            <span className="service-overline">Ваши вещи по местам</span>
            <h2>collect<span>Lib</span></h2>
            <p>Собирайте предметы в коллекции, добавляйте свои фотографии, поля, теги и точное местоположение.</p>
          </div>
          <div className="service-card-footer">
            <span className="service-card-action">Открыть коллекции <ArrowRight size={18} /></span>
            <ServiceStatus status={statuses.collections} />
          </div>
          <div className="collections-card-art" aria-hidden="true"><i /><i /><i /><i /></div>
        </Link>
      </div>
    </section>
  );
}
