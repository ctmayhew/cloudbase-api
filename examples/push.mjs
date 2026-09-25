// Send one track to Cloudbase as a test jump, with retries.
//
//   CLOUDBASE_TOKEN=cb_pat_... node push.mjs sample-track.csv
//
// Node 18+ (built-in fetch). Drop `isSimulated` once you're sending real jumps.
import { readFile } from 'node:fs/promises'

const URL = 'https://api.getcloudbase.com/jumps/import-gps-csv'
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export async function pushTrack(token, csv, deviceType, deviceId) {
  const body = JSON.stringify({ deviceType, deviceId, isSimulated: true, csv })

  for (let attempt = 0; attempt < 5; attempt++) {
    let res
    try {
      res = await fetch(URL, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body,
      })
    } catch {
      await sleep(2 ** attempt * 1000) // network blip; retrying is safe
      continue
    }
    // Every 200 is final, including matchResult "skipped".
    if (res.ok) return res.json()
    if (res.status === 401) throw new Error('Token rejected: ask the user to connect Cloudbase again.')
    if (res.status === 429 || res.status >= 500) {
      await sleep(2 ** attempt * 1000) // back off, then retry the same track
      continue
    }
    // 400 / 413: the file itself is the problem, so retrying won't help.
    throw new Error(`Rejected (${res.status}): ${await res.text()}`)
  }
  throw new Error('Gave up after 5 attempts.')
}

const [, , file] = process.argv
const result = await pushTrack(process.env.CLOUDBASE_TOKEN, await readFile(file, 'utf8'), 'flysight', 'flysight:EXAMPLE')
console.log(result) // { jumpId: '…', matchResult: 'created' }
