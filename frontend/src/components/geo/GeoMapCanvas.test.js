describe('GeoMapCanvas environment safety', () => {
  const originalStreet = process.env.REACT_APP_MAP_TILE_URL;
  const originalSatellite = process.env.REACT_APP_SATELLITE_TILE_URL;

  afterEach(() => {
    process.env.REACT_APP_MAP_TILE_URL = originalStreet;
    process.env.REACT_APP_SATELLITE_TILE_URL = originalSatellite;
    jest.resetModules();
  });

  test('keeps the existing street map available when satellite is not configured', () => {
    process.env.REACT_APP_MAP_TILE_URL = 'https://tiles.example/{z}/{x}/{y}.png';
    delete process.env.REACT_APP_SATELLITE_TILE_URL;
    expect(() => jest.isolateModules(() => require('./GeoMapCanvas'))).not.toThrow();
  });

  test('does not reintroduce clustered circles', () => {
    const source = require('fs').readFileSync(require.resolve('./GeoMapCanvas'), 'utf8');
    expect(source).not.toContain('clusterRadius');
    expect(source).not.toContain('geo-clusters');
    expect(source).toContain("id: 'geo-points'");
  });
});