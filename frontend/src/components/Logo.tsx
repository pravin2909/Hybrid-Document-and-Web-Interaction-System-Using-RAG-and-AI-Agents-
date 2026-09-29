interface Props {
  size?: number;
  className?: string;
}

/**
 * Helios mark — an original swirling camera-aperture / sun icon as inline SVG.
 * Eight twisted crescent blades (orange over a warm-yellow accent edge) rotate
 * around an open center, forming a pinwheel iris.
 */
const ORANGE = "M94.17 33.93 A47 47 0 0 1 94.17 66.07 L71.81 64.16 A26 26 0 0 0 75.81 53.17 Z";
const YELLOW = "M94.81 32.8 A48 48 0 0 1 94.81 67.2 L67.62 64.78 A23 23 0 0 0 72.5 54.78 Z";
const ANGLES = [0, 45, 90, 135, 180, 225, 270, 315];

export function Logo({ size = 28, className }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={className} role="img" aria-label="Helios">
      <g>
        {ANGLES.map((a) => (
          <path key={`y${a}`} d={YELLOW} fill="#F9A825" transform={`rotate(${a} 50 50)`} />
        ))}
      </g>
      <g>
        {ANGLES.map((a) => (
          <path key={`o${a}`} d={ORANGE} fill="#E85D26" transform={`rotate(${a} 50 50)`} />
        ))}
      </g>
    </svg>
  );
}
