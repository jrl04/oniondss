import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import L from 'leaflet';
import type { GeoJsonObject } from 'geojson';
import 'leaflet/dist/leaflet.css';
import './field-map.css';

type Field = { id: number; code: string; name: string; farmer: string; geometry: GeoJsonObject | null };
type RasterResponse = { tile_url?: string; detail?: string };

// Approximate province viewport, including the northern coastline.
const province = L.latLngBounds([17.69, 120.40], [18.66, 121.00]);
const fieldStyle = { color: '#155647', weight: 2, fillOpacity: 0.12 };

function createFieldLayer(field: Field) {
  try {
    if (!field.geometry) return null;
    const layer = L.geoJSON(field.geometry, {
      filter: feature => ['Point', 'Polygon', 'MultiPolygon'].includes(feature.geometry?.type),
      style: fieldStyle,
      pointToLayer: (_, point) => L.circleMarker(point, { ...fieldStyle, radius: 7, fillOpacity: 0.85 }),
    });
    if (!layer.getBounds().isValid()) return null;
    const popup = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = [field.code, field.name].filter(Boolean).join(' · ');
    popup.append(title, document.createElement('br'), field.farmer);
    return layer.bindPopup(popup);
  } catch {
    return null;
  }
}

function FieldMap({ fields, colors, ndviUrl }: { fields: Field[]; colors: string[]; ndviUrl: string }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map>();
  const layers = useRef(new Map<number, L.GeoJSON>());
  const [mapped, setMapped] = useState<ReadonlySet<number>>(new Set());
  const [query, setQuery] = useState('');
  const [basemapFailed, setBasemapFailed] = useState(false);
  const [raster, setRaster] = useState<L.TileLayer>();
  const [status, setStatus] = useState('Connecting to Earth Engine…');
  const [visible, setVisible] = useState(true);
  const [opacity, setOpacity] = useState(75);

  useEffect(() => {
    const instance = L.map(container.current!, { maxZoom: 19, zoomSnap: 0.25 });
    map.current = instance;
    instance.fitBounds(province, { padding: [16, 16] });
    const basemap = L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
      referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: '&copy; <a href="https://stadiamaps.com/attribution/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    });
    let loadedTile = false;
    basemap.on('loading', () => { loadedTile = false; });
    basemap.on('tileload', () => { loadedTile = true; });
    basemap.on('tileerror', ({ tile }: L.TileErrorEvent) => {
      tile.style.visibility = 'hidden';
    });
    basemap.on('load', () => setBasemapFailed(!loadedTile));
    basemap.addTo(instance);
    instance.createPane('ndvi').style.zIndex = '350';
    const fieldLayers = new Map<number, L.GeoJSON>();
    for (const field of fields) {
      const layer = createFieldLayer(field);
      if (layer) fieldLayers.set(field.id, layer.addTo(instance));
    }
    layers.current = fieldLayers;
    setMapped(new Set(fieldLayers.keys()));
    return () => {
      instance.remove();
      map.current = undefined;
    };
  }, [fields]);

  useEffect(() => {
    const controller = new AbortController();
    async function loadRaster() {
      try {
        const response = await fetch(ndviUrl, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        });
        if (response.redirected) throw new Error('Sign in again to load NDVI.');
        const result: RasterResponse = await response.json();
        if (!response.ok || !result.tile_url) {
          throw new Error(result.detail || 'Earth Engine did not return a raster.');
        }
        if (controller.signal.aborted) return;
        setRaster(L.tileLayer(result.tile_url, {
          pane: 'ndvi',
          attribution: 'NDVI &copy; Google Earth Engine',
        }).on('loading', () => setStatus('Loading NDVI tiles…'))
          .on('tileload', () => setStatus('Earth Engine NDVI'))
          .on('tileerror', () => setStatus('An NDVI tile failed to load.')));
        setStatus('Earth Engine NDVI');
      } catch (error) {
        if (!controller.signal.aborted) {
          setStatus(error instanceof SyntaxError || !(error instanceof Error)
            ? 'The NDVI response could not be loaded.'
            : error.message);
        }
      }
    }
    void loadRaster();
    return () => controller.abort();
  }, [ndviUrl]);

  useEffect(() => {
    if (!map.current || !raster) return;
    if (visible) raster.addTo(map.current);
    else raster.remove();
  }, [raster, visible]);

  useEffect(() => {
    raster?.setOpacity(opacity / 100);
  }, [raster, opacity]);

  const matches = fields.filter(field => [field.code, field.name, field.farmer]
    .some(value => value.toLowerCase().includes(query.trim().toLowerCase())));

  function showField(id: number) {
    const layer = layers.current.get(id);
    if (!layer || !map.current) return;
    map.current.fitBounds(layer.getBounds(), { padding: [24, 24], maxZoom: 17 });
    layer.openPopup();
  }

  return (
    <div className="workspace">
      <aside aria-label="Map controls">
        <section className="panel">
          <div className="section-heading"><h2>Registered fields</h2><span>{mapped.size} mapped</span></div>
          <label htmlFor="field-search">Search by field or farmer</label>
          <input id="field-search" type="search" value={query} onChange={event => setQuery(event.target.value)} />
          <ul className="fields">
            {matches.map(field => (
              <li key={field.id}>
                <button className="field" disabled={!mapped.has(field.id)} onClick={() => showField(field.id)}>
                  <strong>{[field.code, field.name].filter(Boolean).join(' · ')}</strong>
                  <span>{field.farmer}{mapped.has(field.id) ? '' : ' · No saved location'}</span>
                </button>
              </li>
            ))}
          </ul>
          {!matches.length && <p className="muted">{fields.length ? 'No fields match your search.' : 'No registered fields yet.'}</p>}
          {mapped.size > 0 && <button className="zoom-fields" onClick={() => {
            const bounds = L.latLngBounds([]);
            for (const layer of layers.current.values()) bounds.extend(layer.getBounds());
            map.current?.fitBounds(bounds, { padding: [24, 24], maxZoom: 17 });
          }}>Zoom to all fields</button>}
        </section>
        <section className="panel">
          <h2>NDVI raster</h2>
          <label className="toggle"><input type="checkbox" checked={visible} disabled={!raster} onChange={event => setVisible(event.target.checked)} /> Show NDVI</label>
          <p className="muted" role="status">{visible ? status : 'NDVI layer hidden'}</p>
          <label htmlFor="opacity">Opacity <span>{opacity}%</span></label>
          <input id="opacity" type="range" min="0" max="100" value={opacity} disabled={!raster} onChange={event => setOpacity(Number(event.target.value))} />
          <div className="legend" aria-hidden="true" style={{ background: `linear-gradient(90deg, ${colors.map(color => '#' + color).join(', ')})` }} />
          <div className="scale"><span>−1</span><span>0</span><span>1</span></div>
        </section>
      </aside>
      <section className="map-panel" aria-label="Ilocos Norte field map">
        <div className="map-toolbar">
          <div><strong>Ilocos Norte</strong><span>Philippines</span></div>
          <button onClick={() => map.current?.fitBounds(province, { padding: [16, 16] })}>Reset to Ilocos Norte</button>
        </div>
        {basemapFailed && <p className="basemap-status" role="status">Basemap tiles are unavailable. For local development, open the app at localhost or 127.0.0.1.</p>}
        <div className="map" ref={container} aria-label="Interactive map" />
      </section>
    </div>
  );
}

const mount = document.getElementById('field-map-app');
if (mount) {
  const fields: Field[] = JSON.parse(document.getElementById('field-records')!.textContent!);
  const colors: string[] = JSON.parse(document.getElementById('ndvi-colors')!.textContent!);
  createRoot(mount).render(<FieldMap fields={fields} colors={colors} ndviUrl={mount.dataset.ndviUrl!} />);
}
