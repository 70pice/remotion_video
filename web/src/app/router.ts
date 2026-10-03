import { useEffect, useState } from "react";

// A small hash router keeps local deployment independent of server path rewrites.
export function useRoute() {
  const [path, setPath] = useState(() => location.hash.slice(1) || "/");
  useEffect(() => {
    const update = () => setPath(location.hash.slice(1) || "/");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return path;
}

export function navigate(path: string) {
  location.hash = path;
}
