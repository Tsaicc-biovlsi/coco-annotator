/**
 * Parent categories ("supercategory"). A category can have several parents;
 * older categories only have the single COCO ``supercategory`` string.
 */

/** "a, b、c" or a list -> unique trimmed names */
export function parseParents(value) {
  const items = Array.isArray(value) ? value : String(value || "").split(/[,，、;；\n]+/);
  const out = [];
  items.forEach(item => {
    const name = String(item || "").trim();
    if (name && !out.includes(name)) out.push(name);
  });
  return out;
}

export function parentsOf(category) {
  if (!category) return [];
  if (Array.isArray(category.supercategories) && category.supercategories.length) {
    return parseParents(category.supercategories);
  }
  return parseParents(category.supercategory);
}

const byName = (a, b) => a.localeCompare(b, undefined, { numeric: true });

/**
 * Categories grouped by parent: [{ parent, items }] sorted by parent name,
 * categories without a parent last (parent: null). With ``firstOnly`` a
 * category goes in its first parent's group only; otherwise in each.
 */
export function groupByParent(categories, { firstOnly = false } = {}) {
  const groups = new Map();
  const none = [];
  categories.forEach(c => {
    const parents = parentsOf(c);
    if (!parents.length) {
      none.push(c);
      return;
    }
    (firstOnly ? parents.slice(0, 1) : parents).forEach(p => {
      if (!groups.has(p)) groups.set(p, []);
      groups.get(p).push(c);
    });
  });
  const out = [...groups.keys()].sort(byName).map(parent => ({ parent, items: groups.get(parent) }));
  if (none.length) out.push({ parent: null, items: none });
  return out;
}

/** every parent name used by these categories, sorted */
export function allParents(categories) {
  const names = new Set();
  categories.forEach(c => parentsOf(c).forEach(p => names.add(p)));
  return [...names].sort(byName);
}

/** does the search text match the category or one of its parents */
export function matchesSearch(category, q) {
  if (!q) return true;
  q = q.toLowerCase();
  return (category.name || "").toLowerCase().includes(q) ||
    parentsOf(category).some(p => p.toLowerCase().includes(q));
}
