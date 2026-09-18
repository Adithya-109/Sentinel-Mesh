import { useEffect } from "react";

/** Fades elements marked .reveal in as they scroll into view. */
export function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>(".reveal");
    if (!("IntersectionObserver" in window)) { els.forEach(e => e.classList.add("in")); return; }
    const io = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }),
      { threshold: 0.18 },
    );
    els.forEach(e => io.observe(e));
    return () => io.disconnect();
  }, []);
}

/** Turns on gentle scroll snapping for the page while it is mounted. */
export function useSnap() {
  useEffect(() => {
    document.documentElement.classList.add("snap");
    return () => document.documentElement.classList.remove("snap");
  }, []);
}
