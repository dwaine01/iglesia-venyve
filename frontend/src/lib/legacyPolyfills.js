/* Navegadores viejos: el navegador interno de tabletas Amazon Fire con Fire OS 5 y otros
 * Android antiguos. Sin estas funciones el panel entero no arranca y la pantalla queda en
 * blanco (por ejemplo, `Object.fromEntries` llegó en Chrome 73). Solo se agregan si faltan;
 * en navegadores modernos no cambia nada. Sin paquetes externos. Va importado PRIMERO en index.js. */
/* eslint-disable no-extend-native, func-names */

const define = (target, name, value) => {
  if (target && !(name in target)) {
    Object.defineProperty(target, name, { value, configurable: true, writable: true, enumerable: false });
  }
};

if (typeof globalThis === 'undefined') {
  // eslint-disable-next-line no-restricted-globals
  (typeof window !== 'undefined' ? window : self).globalThis = typeof window !== 'undefined' ? window : self;
}

define(Object, 'entries', (object) => Object.keys(object).map((key) => [key, object[key]]));
define(Object, 'values', (object) => Object.keys(object).map((key) => object[key]));
define(Object, 'fromEntries', (entries) => {
  const result = {};
  Array.from(entries, (pair) => { result[pair[0]] = pair[1]; return null; });
  return result;
});
// Chrome 54: axios lo usa al cargarse; sin esto el panel no arranca en Android 7 / Fire OS 5.
define(Object, 'getOwnPropertyDescriptors', (object) => {
  const result = {};
  const keys = Object.getOwnPropertyNames(object).concat(Object.getOwnPropertySymbols ? Object.getOwnPropertySymbols(object) : []);
  keys.forEach((key) => { result[key] = Object.getOwnPropertyDescriptor(object, key); });
  return result;
});
define(Object, 'hasOwn', (object, key) => Object.prototype.hasOwnProperty.call(object, key));

const pad = (value, length, filler, atStart) => {
  const text = String(value);
  const fill = filler === undefined ? ' ' : String(filler);
  if (text.length >= length || !fill) return text;
  let extra = '';
  while (extra.length < length - text.length) extra += fill;
  extra = extra.slice(0, length - text.length);
  return atStart ? extra + text : text + extra;
};
define(String.prototype, 'padStart', function (length, filler) { return pad(this, length, filler, true); });
define(String.prototype, 'padEnd', function (length, filler) { return pad(this, length, filler, false); });
define(String.prototype, 'trimStart', function () { return String(this).replace(/^\s+/, ''); });
define(String.prototype, 'trimEnd', function () { return String(this).replace(/\s+$/, ''); });
define(String.prototype, 'replaceAll', function (search, replacement) {
  if (search instanceof RegExp) return String(this).replace(search, replacement);
  return String(this).split(String(search)).join(typeof replacement === 'function' ? replacement(String(search)) : String(replacement));
});

define(String.prototype, 'matchAll', function (pattern) {
  const flags = pattern.flags === undefined ? 'g' : (pattern.flags.indexOf('g') < 0 ? `${pattern.flags}g` : pattern.flags);
  const regex = new RegExp(pattern.source, flags);
  const text = String(this);
  const found = [];
  let match = regex.exec(text);
  while (match) {
    found.push(match);
    if (match[0] === '') regex.lastIndex += 1;
    match = regex.exec(text);
  }
  return found[Symbol.iterator]();
});

const at = function (index) {
  const length = this.length;
  const position = Math.trunc(index) || 0;
  const real = position < 0 ? length + position : position;
  return real < 0 || real >= length ? undefined : this[real];
};
define(Array.prototype, 'at', at);
define(String.prototype, 'at', at);
define(Array.prototype, 'flat', function (depth) {
  const level = depth === undefined ? 1 : Number(depth);
  const flatten = (list, remaining) => list.reduce((all, item) => all.concat(Array.isArray(item) && remaining > 0 ? flatten(item, remaining - 1) : [item]), []);
  return flatten(this, level);
});
define(Array.prototype, 'flatMap', function (callback, thisArg) { return Array.prototype.map.call(this, callback, thisArg).flat(1); });
define(Array.prototype, 'findLast', function (callback, thisArg) {
  for (let index = this.length - 1; index >= 0; index -= 1) if (callback.call(thisArg, this[index], index, this)) return this[index];
  return undefined;
});
define(Array.prototype, 'findLastIndex', function (callback, thisArg) {
  for (let index = this.length - 1; index >= 0; index -= 1) if (callback.call(thisArg, this[index], index, this)) return index;
  return -1;
});

if (typeof Promise !== 'undefined') {
  define(Promise.prototype, 'finally', function (callback) {
    return this.then((value) => Promise.resolve(callback()).then(() => value), (error) => Promise.resolve(callback()).then(() => { throw error; }));
  });
  define(Promise, 'allSettled', (items) => Promise.all(Array.from(items, (item) => Promise.resolve(item).then(
    (value) => ({ status: 'fulfilled', value }), (reason) => ({ status: 'rejected', reason }),
  ))));
}

// Chrome 61: scrollTo/scrollBy en elementos y con { top, left } (antes tumbaba el registro de las tabletas).
if (typeof Element !== 'undefined') {
  const scrollArgs = (args, element) => {
    const first = args[0];
    if (first && typeof first === 'object') {
      return [first.left === undefined ? element.scrollLeft : first.left, first.top === undefined ? element.scrollTop : first.top];
    }
    return [Number(first) || 0, Number(args[1]) || 0];
  };
  define(Element.prototype, 'scrollTo', function (...args) {
    const [left, top] = scrollArgs(args, this);
    this.scrollLeft = left;
    this.scrollTop = top;
  });
  define(Element.prototype, 'scrollBy', function (...args) {
    const first = args[0];
    const left = first && typeof first === 'object' ? first.left || 0 : Number(first) || 0;
    const top = first && typeof first === 'object' ? first.top || 0 : Number(args[1]) || 0;
    this.scrollLeft += left;
    this.scrollTop += top;
  });
}
if (typeof window !== 'undefined' && typeof window.scrollTo === 'function' && !('scrollBehavior' in document.documentElement.style)) {
  const nativeScrollTo = window.scrollTo.bind(window);
  window.scrollTo = (first, second) => {
    if (first && typeof first === 'object') {
      nativeScrollTo(first.left === undefined ? window.pageXOffset : first.left, first.top === undefined ? window.pageYOffset : first.top);
    } else {
      nativeScrollTo(Number(first) || 0, Number(second) || 0);
    }
  };
}

// Chrome 92: identificadores para no duplicar envíos.
if (typeof window !== 'undefined' && window.crypto && typeof window.crypto.getRandomValues === 'function' && typeof window.crypto.randomUUID !== 'function') {
  window.crypto.randomUUID = () => {
    const bytes = window.crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // eslint-disable-line no-bitwise
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // eslint-disable-line no-bitwise
    const hex = Array.from(bytes, (byte) => (`0${byte.toString(16)}`).slice(-2)).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  };
}

// Chrome 64: los menús y ventanas lo usan para medir. Sin él, se mide una vez al observar.
if (typeof window !== 'undefined' && typeof window.ResizeObserver !== 'function') {
  window.ResizeObserver = class LegacyResizeObserver {
    constructor(callback) { this.callback = callback; this.items = []; }

    observe(target) {
      this.items.push(target);
      setTimeout(() => {
        if (this.items.indexOf(target) < 0) return;
        const rect = target.getBoundingClientRect();
        const box = [{ inlineSize: rect.width, blockSize: rect.height }];
        this.callback([{ target, contentRect: rect, borderBoxSize: box, contentBoxSize: box }], this);
      }, 0);
    }

    unobserve(target) { this.items = this.items.filter((item) => item !== target); }

    disconnect() { this.items = []; }
  };
}

if (typeof window !== 'undefined' && typeof window.queueMicrotask !== 'function') {
  window.queueMicrotask = (callback) => Promise.resolve().then(callback);
}
