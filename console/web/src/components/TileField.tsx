const TILES = Array.from({ length: 100 }, (_, i) => i);

/** A slowly drifting field of glossy deep-purple tiles, drawn entirely in CSS. */
export default function TileField() {
  return (
    <div className="tilefield" aria-hidden>
      <div className="tilefield-plane">
        <div className="tilefield-grid">{TILES.map(i => <div key={i} className="tile" />)}</div>
      </div>
    </div>
  );
}
