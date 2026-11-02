// Site search, shared by index.html (All Legislation) and agenda.html (Meetings).
// Every word of the query must appear, in any order, at the start of a word in the
// record's text. Hyphens count as spaces ("short term" finds "short-term") and curly
// apostrophes as straight ones. A plural ending is dropped ("grants" finds "grant"),
// and so is "-ion"/"-ions" when at least six letters remain, so "appropriation" also
// finds "appropriates" and "exemption" finds "exempt". Text in double quotes is
// matched as one phrase.
(function () {
  function norm(s) {
    return (s || '').toLowerCase()
      .replace(/[‘’]/g, "'")
      .replace(/[-‐-―]/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }
  function stem(w) {
    if (/ions?$/.test(w) && w.replace(/ions?$/, '').length >= 6) return w.replace(/ions?$/, '');
    if (w.length > 4 && /(?:[sxz]|ch|sh)es$/.test(w)) return w.slice(0, -2);
    if (w.length > 3 && /[^s']s$/.test(w)) return w.slice(0, -1);
    return w;
  }
  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  const START = '(?:^|[^a-z0-9])';
  let lastQ = null, lastParts = null;
  function compile(q) {
    if (q === lastQ) return lastParts;
    const n = norm(q).replace(/[“”]/g, '"');
    const parts = [];
    n.replace(/"([^"]+)"|([^\s"]+)/g, (m, phrase, word) => {
      const t = phrase ? phrase.trim() : stem(word);
      if (t) parts.push(new RegExp(START + esc(t)));
      return m;
    });
    lastQ = q;
    lastParts = parts.length ? parts : null;
    return lastParts;
  }
  function test(parts, text) {
    if (!parts) return true;
    const h = norm(text);
    return parts.every(re => re.test(h));
  }
  window.SiteSearch = { norm, stem, compile, test };
})();
