const HUES = [250, 30, 155, 290, 80, 200, 0, 60, 330, 120, 25, 180];

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export function catColor(cat: string | null): string {
  if (!cat || cat === 'Income') return 'var(--pos)';
  const hue = HUES[hashStr(cat) % HUES.length];
  return `oklch(0.62 0.12 ${hue})`;
}

export default function CatSwatch({ cat, size = 22 }: { cat: string | null; size?: number }) {
  const c = cat || 'Other';
  const color = catColor(c);
  const letter = c.slice(0, 1).toUpperCase();
  return (
    <span style={{
      width: size, height: size, borderRadius: 6, flexShrink: 0,
      background: `color-mix(in oklch, ${color} 18%, var(--bg-elev))`,
      color, display: 'grid', placeItems: 'center',
      fontSize: size * 0.55, fontWeight: 700, letterSpacing: 0,
    }}>
      {letter}
    </span>
  );
}
