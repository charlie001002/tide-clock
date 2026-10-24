# Two Hand Tide Clock (Gullane and North Berwick)

A full-screen tide clock for an old iPad (Safari 16), based on Leith harmonic constants (TICON-4)
with Fidra secondary-port differences. It shows a Sun hand (S2) and Moon hand (M2), the predicted
tide, live air-pressure correction, and a **traffic light** for each location.

Live page: https://charlie001002.github.io/tide-clock/

## Traffic lights

| Light | When |
|---|---|
| Red | A tracked Scottish Water overflow is overflowing now (`OF - Overflowing`), or a Met Office warning for the area is in force |
| Amber | A tracked overflow ended less than 48 h ago, or wave height or swell is above 1.0 m now or in the next 3 h |
| Green | All clear |
| Grey | No data |

A dashed ring means some data is missing or stale. Tap a light for the detail page.

Tracked overflows (editable in Settings):
- Gullane: GULLANE WWTW CSO (Firth of Forth). Gullane Loan Cottage CSO is not tracked: it discharges to the Peffer Burn.
- North Berwick: NORTH BERWICK WESTER DUNES WWPS CSO; NORTH BERWICK, FIDRA SPS CSO; NORTH BERWICK, 1 MELBOURNE ROAD CSO; NORTH BERWICK, TANTALLON TERRACE CSO.

This shows overflow events, not a bathing-water quality reading.

## Settings

The ⚙ button opens Settings: thresholds, which warnings count, tracked overflows, chart level
markers (label, height, location), location coordinates, tide offsets, refresh intervals and the
status URL. They are saved in the browser's localStorage on that device, with "Reset to defaults".
The defaults live in the `DEFAULTS` object near the top of the script in `index.html`.

## Data

| Source | How |
|---|---|
| Scottish Water near-real-time overflows (`api.scottishwater.co.uk/overflow-event-monitoring/v1/near-real-time`) | No CORS, so fetched hourly by the workflow into `status.json` |
| Met Office warnings RSS, Dumfries, Galloway, Lothian & Borders (`.../WarningsRSS/Region/dg`) | No CORS, so fetched hourly by the workflow into `status.json` |
| Open-Meteo Marine (wave and swell) | Fetched directly by the page |
| Open-Meteo (air pressure) | Fetched directly by the page |

## Files

- `index.html`: the whole page (single file, no external libraries)
- `status.json`: written by the workflow; schema in `status.schema.json`
- `scripts/fetch_status.py`: standard-library Python that builds `status.json`. Keeps the tracked assets, every East Lothian asset and anything within 25 km
- `.github/workflows/update-status.yml`: hourly cron (and manual "Run workflow"); commits `status.json` only when the data changed

## Notes

- GitHub pauses scheduled workflows in a public repo after 60 days without repository activity.
  The hourly commits normally count as activity; if it ever stops, open Actions and re-enable it.
- To run locally: `python3 scripts/fetch_status.py status.json`
- Approximate: check an official tide table before swimming or boating.
