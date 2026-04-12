/**
 * Safely splits a value by a separator.
 * Handles cases where value is already an array, null, undefined, or not a string.
 * @param {any} value - The object to split.
 * @param {string|RegExp} separator - The separator to use.
 * @returns {Array} - The resulting array or an empty array.
 */
export const safeSplit = (value, separator) => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') return value.split(separator);
  return [];
};
