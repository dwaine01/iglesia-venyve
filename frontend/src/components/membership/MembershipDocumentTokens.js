export const membershipDocumentTokens = Object.freeze({
  '--vv-navy': '#022e5a',
  '--vv-blue': '#0798c8',
  '--vv-green': '#61b33b',
  '--vv-white': '#ffffff',
  '--vv-off-white': '#f7f9f8',
  '--vv-charcoal': '#101d35',
  '--vv-sans': '"Plus Jakarta Sans", sans-serif',
  '--vv-serif': '"Cormorant Garamond", serif',
});

export const memberNameSize = (name = '', format = 'card') => {
  const length = name.trim().length;
  if (format === 'certificate') {
    if (length > 65) return '.34in';
    if (length > 48) return '.4in';
    if (length > 36) return '.52in';
    return '.72in';
  }
  if (length > 60) return '2.2mm';
  if (length > 45) return '2.25mm';
  if (length > 38) return '3.1mm';
  if (length > 28) return '4mm';
  return '5.1mm';
};

export const membershipNumberSize = (value = '', format = 'card') => {
  const length = String(value).length;
  if (format === 'certificate') return length > 18 ? '.075in' : length > 12 ? '.14in' : length > 9 ? '.18in' : '.23in';
  if (format === 'verification') return length > 18 ? '1.9mm' : length > 12 ? '2.5mm' : length > 9 ? '3mm' : '3.9mm';
  return length > 18 ? '1.55mm' : length > 12 ? '2mm' : length > 9 ? '2.5mm' : '3.25mm';
};