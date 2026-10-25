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
