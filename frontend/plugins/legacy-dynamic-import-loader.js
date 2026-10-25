// Navegadores viejos (Fire OS 5): la sintaxis `import(...)` (Chrome 63+) hace que el navegador rechace
// el archivo ENTERO y la página queda en blanco, aunque esa línea nunca se use. react-router trae una
// (`import(/* webpackIgnore: true */ route.module)`) para un modo que esta app no usa. Aquí se cambia
// por una equivalente que se arma al ejecutarse: en navegadores modernos hace lo mismo; en los viejos
// el archivo se puede leer y solo fallaría si se llamara (nunca se llama). Sin paquetes externos.
const IGNORED_IMPORT = /\bimport\(\s*(?:\/\*\s*@vite-ignore\s*\*\/\s*)?\/\*\s*webpackIgnore:\s*true\s*\*\/\s*(?:\/\*\s*@vite-ignore\s*\*\/\s*)?/g;

module.exports = function legacyDynamicImportLoader(source) {
  return source.replace(IGNORED_IMPORT, '(function (specifier) { return new Function("s", "return import(s)")(specifier); })(');
};
