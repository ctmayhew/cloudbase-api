# Cloudbase Ingest API

Send skydiving jumps from your app, device or service into a jumper's [Cloudbase](https://getcloudbase.com) logbook.

**Status:** v1, live at `https://api.getcloudbase.com`. The machine-readable spec is [`openapi.yaml`](openapi.yaml).

---

## How it works

You send the GPS track a device recorded for one jump. Cloudbase does the rest: it works out the exit, opening and freefall numbers, finds the dropzone, numbers the jump, and checks it against everything else the jumper has logged (their manifest sync, watch, phone and other devices), so one physical jump never shows up twice.

You don't need to compute freefall time, jump numbers, dropzones or anything else. Send the track and read back what happened to it.

The API is **write-only**. A token can add jumps to one person's logbook and do nothing else: it can't read the logbook, change settings or delete anything.

## 1. Get a token

Each jumper creates their own token and gives it to your app.

1. In Cloudbase they open **Connections → API tokens**: on the web at [getcloudbase.com/connections](https://getcloudbase.com/connections), or in the iOS/Android app under **Me → Connections**.
2. They name the token after your app and tap **Generate**.
3. Cloudbase shows the token once. It looks like `cb_pat_` followed by 48 hex characters. They copy it into your app.
4. They can revoke it from the same screen at any time, and it stops working immediately.

An account can hold up to 10 active tokens.

**Storing tokens:** keep one token per user, encrypt it at rest, and never log it. If you get a `401`, the token has been revoked: stop sending with it and ask the user to connect again.

## 2. Send a jump

```http
POST https://api.getcloudbase.com/jumps/import-gps-csv
Authorization: Bearer cb_pat_…
Content-Type: application/json
```

```json
{
  "deviceType": "flysight",
  "deviceId": "flysight:0A1B2C3D",
  "csv": "time,lat,lon,hMSL,velN,velE,velD,hAcc,vAcc,sAcc,heading,cAcc,gpsFix,numSV\n,(deg),(deg),(m),(m/s),(m/s),(m/s),(m),(m),(m/s),(deg),(deg),,\n2026-06-06T10:15:00.000Z,52.1000359,-1.1999942,4000.000,20.00,2.00,0.00,2.100,3.400,0.45,5.7,1.8,3,16\n…"
}
```

| Field | Required | Notes |
|---|---|---|
| `csv` | yes | The device's track file, as a string. See [section 3](#3-the-track-format). |
| `deviceType` | yes | The device that recorded the track: `flysight` or `skytrax`. Always send it. |
| `deviceId` | recommended | A stable id for the physical device, e.g. `flysight:<serial>`. Use the same value on every upload from that device. |
| `isSimulated` | no | `true` marks a test upload. See [section 7](#7-testing). Leave it out for real jumps. |

Send **one jump per request**, soon after it's recorded. Runnable examples, each with retry handling: [`push.sh`](examples/push.sh) (curl), [`push.py`](examples/push.py) (Python) and [`push.mjs`](examples/push.mjs) (Node).

### Which devices

v1 accepts tracks recorded by **FlySight** (1 and 2) and **SkyTrax** devices. Cloudbase uses `deviceType` to decide how much to trust a track: it knows how accurate each device's GPS is and how its altitude behaves. So don't label another device's track as `flysight` just because you've converted it to the same file format. If your device isn't listed, [get in touch](#10-support) and we'll add it properly.

## 3. The track format

The FlySight CSV format: a header row, a units row, then one row per GPS sample. FlySight 1 and FlySight 2 files are accepted as the device writes them.

| # | Column | Units | Notes |
|---|---|---|---|
| 0 | `time` | ISO 8601, UTC | Absolute time of each sample. |
| 1 | `lat` | degrees | WGS84. |
| 2 | `lon` | degrees | WGS84. |
| 3 | `hMSL` | **metres** | Height above mean sea level. |
| 4 | `velN` | m/s | North velocity. |
| 5 | `velE` | m/s | East velocity. |
| 6 | `velD` | m/s | Down velocity, positive when descending. |
| 7 | `hAcc` | metres | Horizontal accuracy. |
| 8 | `vAcc` | metres | Vertical accuracy. |
| 9 | `sAcc` | m/s | Speed accuracy. |
| 10 | `heading` | degrees | |
| 11 | `cAcc` | degrees | Heading accuracy. |
| 12 | `gpsFix` | | Fix type. Rows below 2 (no real fix) are dropped. |
| 13 | `numSV` | | Satellites used. |
| 14 | baro altitude (optional) | metres | Extra barometric channel, used only as a cross-check. |

- **Units must be SI** (metres, m/s). A file whose units row says `ft` or `mph` is rejected rather than risk a silent 3.28× error.
- Send the **whole recording**. Cloudbase finds the jump inside it and trims the rest.
- The track has to contain at least 10 usable GPS samples and look like a skydive: enough altitude lost, with a freefall in it. Anything else is rejected with a `400`.

A complete synthetic example is [`examples/sample-track.csv`](examples/sample-track.csv). It's an invented jump, not real data.

## 4. The response

A `200` means Cloudbase accepted the track. `matchResult` says what it did with it:

```json
{ "jumpId": "8f3c1e90-2a4b-4c77-9e21-0b9d6e5a1f42", "matchResult": "created" }
```

| `matchResult` | Meaning | `jumpId` |
|---|---|---|
| `created` | Nothing matched, so a new jump was created. | the new jump |
| `merged` | The track was added to a jump the user already had, e.g. one from their manifest. May include `matchConfidence`. | the existing jump |
| `pending_review` | It might match an existing jump, so it's waiting in the user's inbox for them to decide. | empty string |
| `skipped` | Nothing to do. `skipReason` says why. | the existing jump, or empty |

| `skipReason` | Meaning |
|---|---|
| `duplicate` | This track was already imported. |
| `pending_duplicate` | This track is already waiting in the user's inbox. |
| `suppressed` | The user deleted the jump this track made, so Cloudbase won't bring it back. |

**Jump numbers are not returned.** For tracks, the logbook number is assigned when the jump is confirmed, in date order, so it isn't known at import time.

**Treat every `200` as done**, including `skipped`. Don't re-send a track because it was skipped.

Future versions may add fields to the response and new values to `matchResult`, `matchConfidence` or `skipReason`. Ignore fields you don't recognise, and treat an unknown `matchResult` as success.

## 5. Retries and duplicates

The upload is safe to retry. The same track sent twice (same device type and exit time) comes back as `skipped` / `duplicate` and changes nothing. So if a request times out, send it again.

The same physical jump can also reach Cloudbase from somewhere else, such as the jumper's watch or manifest. That's normal, and handled by matching: you'll get `merged` or `pending_review` instead of `created`.

## 6. Errors and limits

| Status | Meaning | What to do |
|---|---|---|
| `400` | The body is malformed, the CSV isn't a usable track, or it isn't a skydive. The body has an `error` message. | Don't retry the same file. |
| `401` | The token is missing, wrong or revoked. | Stop, and ask the user to connect again. |
| `413` | The request is over 40 MB. | A single jump is far below this. Send one jump per request. |
| `429` | Over 300 requests a minute for this token. | Back off and retry. |
| `5xx` | Something failed on our side. | Retry with exponential backoff. |

## 7. Testing

Set `"isSimulated": true` while you build. The jump is created and marked as simulated, and it's kept out of the user's stats. Test on your own Cloudbase account, then drop the flag when you go live.

## 8. Your responsibilities

- Only send jumps the user has asked you to send to Cloudbase.
- Keep tokens secret: encrypted at rest, never in logs, URLs, client-side code or source control.
- When a user disconnects Cloudbase in your app, delete their token.

## 9. Versioning

This is v1. Adding optional request fields, response fields or enum values doesn't count as a breaking change (see [section 4](#4-the-response)). Anything that would break a correct v1 client ships as a new version, announced in advance in [`CHANGELOG.md`](CHANGELOG.md).

## 10. Support

Questions, bugs and device requests: [open an issue on GitHub](https://github.com/ctmayhew/cloudbase-api/issues), or email [support@getcloudbase.com](mailto:support@getcloudbase.com).

**Security issues:** email [support@getcloudbase.com](mailto:support@getcloudbase.com) with "Security" in the subject, and please don't post the details publicly.
