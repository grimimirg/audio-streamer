/**
 * Icon markup for scripts.
 *
 * The geometry lives in the SVG sprite that base.html emits (see
 * templates/components/icons.html); this only builds a reference to it, so an
 * icon changed in the sprite changes everywhere at once.
 */

/**
 * Build the markup for one icon.
 *
 * @param {string} name - Symbol name without the "i-" prefix, e.g. "play"
 * @param {string} [cls] - Extra classes, e.g. "icon-lg"
 * @returns {string} SVG markup, safe to insert with innerHTML
 */
function icon(name, cls = '') {
    return `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

/**
 * Show an icon followed by a message in an element.
 *
 * The message is added as a text node rather than as markup, so a value that
 * came from the server - a directory path, a filename - cannot inject HTML.
 *
 * @param {HTMLElement} element - Element to fill
 * @param {string} name - Symbol name without the "i-" prefix
 * @param {string} text - Message to show after the icon
 */
function setStatus(element, name, text) {
    if (!element) return;
    element.innerHTML = icon(name);
    element.appendChild(document.createTextNode(` ${text}`));
}
