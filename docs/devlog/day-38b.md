# Day 38 (addition) — Motion: the Overview as a galaxy, quiet movement everywhere

Requested after Phase 9: the "universe" theme looked static. Motion was added so it explains the system rather
than only decorating it.

## Done
- src/components/Constellation.tsx rewritten as a small galaxy. The API gateway (which receives every request)
  sits at the centre of a slowly turning spiral (two arms of faint stars, one turn in 4 minutes). The other
  services orbit it on tilted ellipses, inner orbits faster (70–142 s per revolution), slightly larger at the front
  of the orbit for depth. Dots travel from the centre to each service: requests flowing, faster for services with a
  larger share of the logs, in the service's health colour; none for a service without logs. Size, colour, halo and
  flare keep their meaning; the core glow breathes.
- Pointing at or focusing a service pauses the motion so it is easy to click; clicking still opens its anomalies.
- The loop uses requestAnimationFrame and moves planets, links and dots directly in the DOM, so React does not
  re-render 60 times a second; data reloads do not reset the orbits. Time steps are capped, so a hidden tab does not
  make planets jump.
- index.css, quiet motion on every page: the starfield twinkles and drifts (one tile in 6 minutes), a nebula drifts
  behind the pages, a shooting star crosses about every 23 s, the brand mark is a planet with an orbiting moon,
  pages and panels rise into place when opened, the active menu item carries a slow sheen, panels lift on hover.
  Labels in the galaxy have a dark outline so they stay readable over the spiral.
- Overview texts: "planets" instead of "stars", and a caption explaining the picture.
- Everything stops when the operating system asks for reduced motion (prefers-reduced-motion).

## Checked
- Preview at 1280 and 1536 px with sample data: planets move (about 11 px per second on the inner orbit), dots
  flow, the spiral turns, labels readable; 12-second recording.