export const INSTITUTION = Object.freeze({
  legalName: 'PRIMERA IGLESIA DEL NAZARENO',
  brandName: 'VEN Y VE',
  fullName: 'PRIMERA IGLESIA DEL NAZARENO VEN Y VE',
  tagline: 'UNA FAMILIA PARA LA ETERNIDAD',
  mission: 'CONOCIENDO A DIOS · HACIENDO FAMILIA · TRANSFORMANDO VIDAS',
  phone: '614-508-0303',
});

export const CR80 = Object.freeze({ width: 85.6, height: 53.98 });
export const LETTER_LANDSCAPE = Object.freeze({ width: 279.4, height: 215.9 });

export const testIdFor = (base, exportMode) => `${base}${exportMode ? '-export' : ''}`;