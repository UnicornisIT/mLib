import { SearchClient } from "./search-client";

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const params = await searchParams;
  return <SearchClient query={params.q ?? ""} />;
}

