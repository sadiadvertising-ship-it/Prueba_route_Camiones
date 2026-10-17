import { slug } from './levels.js'

export default function Level({ level }) {
  return (
    <span className={`level ${slug(level)}`}>
      <i />
      {level || 'No data'}
    </span>
  )
}
