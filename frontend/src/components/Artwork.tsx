"use client";

import { Music2 } from "lucide-react";
import Image from "next/image";
import { artworkUrl } from "@/lib/api";

export function Artwork({
  id,
  alt,
  size = 256,
  className = "",
}: {
  id?: string | null;
  alt: string;
  size?: 64 | 256 | 512;
  className?: string;
}) {
  const source = artworkUrl(id, size);
  if (!source) {
    return (
      <div className={`artwork-placeholder ${className}`} aria-label={`Обложка: ${alt}`}>
        <Music2 size={Math.max(18, Math.round(size / 8))} strokeWidth={1.5} />
      </div>
    );
  }
  return <Image className={`artwork ${className}`} src={source} alt={alt} width={size} height={size} unoptimized />;
}
