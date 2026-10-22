"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { PageLoader } from "@/components/EmptyState";
import { SearchClient } from "./search-client";

// Read on the client: typing in the top bar updates the query without a server round trip per letter.
function SearchFromUrl() {
  return <SearchClient query={useSearchParams().get("q")?.trim() ?? ""} />;
}

export default function SearchPage() {
  return <Suspense fallback={<div className="content-page"><PageLoader /></div>}><SearchFromUrl /></Suspense>;
}
