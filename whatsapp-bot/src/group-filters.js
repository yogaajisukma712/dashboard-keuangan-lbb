function normalizeGroupName(value) {
  return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

function parseExcludedGroupNames(rawValue) {
  const seen = new Set();
  return String(rawValue || '')
    .split(/[\n,]+/)
    .map((item) => item.trim().replace(/\s+/g, ' '))
    .filter((item) => {
      if (!item || seen.has(item)) {
        return false;
      }
      seen.add(item);
      return true;
    });
}

function isExcludedGroupName(groupName, excludedGroupNames = []) {
  const normalizedGroupName = normalizeGroupName(groupName);
  if (!normalizedGroupName) return false;
  return excludedGroupNames.some(
    (item) => normalizeGroupName(item) === normalizedGroupName,
  );
}

module.exports = {
  isExcludedGroupName,
  normalizeGroupName,
  parseExcludedGroupNames,
};
