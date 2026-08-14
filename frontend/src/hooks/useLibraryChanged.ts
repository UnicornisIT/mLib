"use client";

import { useEffect } from "react";

export function useLibraryChanged(callback: () => void) {
  useEffect(() => {
    window.addEventListener("mlib:library-changed", callback);
    return () => window.removeEventListener("mlib:library-changed", callback);
  }, [callback]);
}

