const EMOJI_REGEX = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu;

export function formatProductName(raw) {
  if (!raw || typeof raw !== 'string') return '';

  const cleaned = raw.replace(EMOJI_REGEX, '').replace(/_/g, ' ').trim();

  return cleaned
    .split(/(\s+|-|\/)/)
    .map(part => {
      if (!part || /^\s+$/.test(part) || part === '-' || part === '/') return part;
      if (/^\d/.test(part)) return part;
      return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
    })
    .join('')
    .replace(/\s+/g, ' ')
    .trim();
}

export function stripEmojis(str) {
  if (!str || typeof str !== 'string') return '';
  return str.replace(EMOJI_REGEX, '').trim();
}

export default formatProductName;
