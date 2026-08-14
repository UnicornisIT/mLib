import { TracksClient } from "./tracks-client";

export default async function TracksPage({ searchParams }: { searchParams: Promise<{ genre?: string }> }) {
  const params = await searchParams;
  return <TracksClient genre={params.genre} />;
}

