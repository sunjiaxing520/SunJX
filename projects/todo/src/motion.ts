import type { RefObject } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

/** Scoped, interruptible entrances. Server updates never replay page animations. */
export function useEntrance(
  root: RefObject<HTMLElement | null>,
  kind: "page" | "dialog" | "panel" | "task" | "login",
  dependencies: unknown[] = [],
) {
  useGSAP(
    () => {
      if (!root.current) return;
      const media = gsap.matchMedia();
      media.add(
        "(prefers-reduced-motion: no-preference)",
        () => {
          const node = root.current!;
          const mobile = window.matchMedia("(max-width: 760px)").matches;
          const duration = mobile ? 0.22 : 0.32;
          const defaults = {
            duration,
            ease: "power2.out",
            clearProps: "transform,opacity",
          };
          if (kind === "page" || kind === "login") {
            const targets =
              kind === "login"
                ? node.querySelectorAll(".login-intro, .login-card")
                : node.querySelectorAll(
                    ":scope > .page-heading, :scope > .daily-summary, :scope > .quick-add, :scope > .projects-grid, :scope > .balance-card, :scope > .settings-card, :scope > .project-banner",
                  );
            if (targets.length)
              gsap.timeline({ defaults }).from(targets, {
                y: mobile ? 6 : 10,
                opacity: 0.65,
                stagger: { each: 0.035, amount: 0.12 },
              });
          } else if (kind === "task") {
            const rect = node.getBoundingClientRect();
            if (rect.top < innerHeight && rect.bottom > 0) {
              gsap.from(node, { ...defaults, x: 6, opacity: 0.6 });
              const check = node.querySelector<HTMLInputElement>(".task-check");
              if (check?.checked)
                gsap.from(check, {
                  ...defaults,
                  scale: 0.75,
                  ease: "back.out(1.5)",
                });
            }
          } else if (kind === "panel") {
            gsap.from(node, { ...defaults, x: mobile ? 12 : 24, opacity: 0.7 });
          } else {
            gsap.from(node, {
              ...defaults,
              y: mobile ? 14 : 8,
              scale: mobile ? 1 : 0.98,
              opacity: 0.7,
            });
          }
        },
        root,
      );
      return () => media.revert();
    },
    { scope: root, dependencies, revertOnUpdate: true },
  );
}
