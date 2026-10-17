export const LEVELS = ['No Travel', 'Severe', 'High', 'Moderate', 'Low', 'No data']

export function slug(level) {
  return (level || 'No data').toLowerCase().replace(' ', '-')
}
