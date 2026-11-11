import { useEffect, useState } from 'react'
import App from './App.jsx'
import Districts from './districts/Districts.jsx'

// Top-level tabs. Hash routing so district links can be shared/bookmarked:
//   #/                       statewide (the original live dashboard)
//   #/districts/GA           district table
//   #/districts/GA/house/56  one district
//   #/districts/GA/targets   2028 target list
function useHash() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const on = () => setHash(window.location.hash)
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return hash
}

export default function Root() {
  const hash = useHash()
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  const onDistricts = parts[0] === 'districts'
  return (
    <>
      <nav className="tabs-top">
        <a href="#/" className={onDistricts ? '' : 'on'}>Statewide</a>
        <a href="#/districts/GA" className={onDistricts ? 'on' : ''}>Districts · GA, NC, SC &amp; OH</a>
      </nav>
      {onDistricts ? <Districts parts={parts.slice(1)} /> : <App />}
    </>
  )
}
