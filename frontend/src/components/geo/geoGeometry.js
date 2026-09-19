export const pointInPolygon = (coordinates, geometry) => {
  const [longitude, latitude] = coordinates || [];
  const ring = geometry?.coordinates?.[0] || [];
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x1, y1] = ring[index]; const [x2, y2] = ring[previous];
    const crosses = (y1 > latitude) !== (y2 > latitude);
    if (crosses && longitude < ((x2 - x1) * (latitude - y1)) / (y2 - y1) + x1) inside = !inside;
  }
  return inside;
};

export const zoneGeometry = (zones, zoneId) => zones?.features?.find((item) => item.properties?.feature_type === 'zone' && item.properties?.zone === zoneId)?.geometry || null;

export const closedPolygon = (coordinates) => ({
  type: 'Polygon', coordinates: [[...(coordinates || []), coordinates?.[0]]],
});