# SwitchBot API Quota

[日本語](README.ja.md)

Observe the remaining SwitchBot OpenAPI request allowance in Home Assistant. This
unofficial custom integration samples the server's `X-RateLimit-Remaining` response
header once per hour, and records when an increase is first observed.

It uses the credentials of an existing **SwitchBot Cloud** integration. You do not
need to enter or store another copy of your token and secret. It does not control
devices or change SwitchBot Cloud polling.

## Installation

Requires Home Assistant **2026.11.0 or later** and an already configured
[SwitchBot Cloud](https://www.home-assistant.io/integrations/switchbot_cloud/)
account. SwitchBot Bluetooth alone does not provide the required cloud credentials.

### HACS / Marketplace custom repository

1. Open HACS (or Marketplace), then **Custom repositories**.
2. Add `https://github.com/Yamar50/ha-switchbot-api-quota`, type **Integration**.
3. Download **SwitchBot API Quota** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → SwitchBot API Quota**.
5. Select your existing SwitchBot Cloud entry and submit.

This repository can be added manually; publication here does **not** mean it has
been accepted into the default HACS catalog.

### Manual installation

Copy `custom_components/switchbot_quota` into your Home Assistant
`config/custom_components/` directory, restart, then follow steps 4–5 above.

### Existing private/manual installation

Back up your configuration and replace only `custom_components/switchbot_quota`.
Keep the existing integration entry. The domain, unique IDs, suggested entity IDs,
and persisted storage format are unchanged. Do not delete and recreate the entry:
that would discard its saved polling deadline and observation window. Existing
entity names set by the user remain under HA's control.

## Sensors and history

| Suggested entity ID | Meaning |
| --- | --- |
| `sensor.switchbot_api_remaining` | Remaining requests reported by the server |
| `sensor.switchbot_api_last_increase` | Time at which a larger remaining count was first observed |

Actual IDs may differ if you renamed them or monitor more than one Cloud entry.
Names are translated into English and Japanese. The count unit remains `回`
(Japanese for a count of occurrences) in every language to preserve statistics
compatibility with the original installation.

Open the remaining-count sensor to see its history. It has
`state_class: measurement`, so HA Recorder can keep long-term statistics when this
entity is included. Your existing Recorder retention and exclusion settings apply;
the integration does not change them.

The increase sensor starts as `unknown`. Its attributes include:

- `increase_window_start`: the previous successful observation.
- `last_increase_observed_at`: the observation that found the larger value.
- `remaining_before_increase` / `remaining_after_increase`: the compared values.
- `increases_observed`: the number of increases observed by this entry.

The replenishment happened somewhere within that observation window, normally
about one hour. A failed request or stopped HA instance widens the window. If a
reset and sufficient consumption both occur between samples, the next value can
be equal or lower and the reset will **not** be detected. This is an observation
tool, not an exact reset-time detector or a count of HA's own API requests.

## Request budget and failures

- One `GET https://api.switch-bot.com/v1.1/devices` request at initial setup, then
  one per hour: approximately **24 additional requests per day per monitored
  Cloud entry**. The monitoring request itself consumes allowance.
- The last attempt is saved **before** network I/O. Reloads, restarts and manual
  `homeassistant.update_entity` calls within the next hour reuse the saved state.
- Failures do not trigger immediate retries. The next attempt is one hour later.
- Missing/invalid headers, network failures and rejected authentication make the
  remaining-count sensor `unavailable`, never an invented zero. The last good
  value is retained internally for the next comparison.
- HTTP 429 is accepted only when it contains a valid remaining-count header;
  an actual server-reported zero is displayed as zero.
- The increase timestamp remains available during a current request failure.
- No requests follow redirects. The device-list body is not deserialized, saved,
  or logged. Tokens and secrets are not copied into this integration's config or
  storage.

Remaining-count attributes expose `observed_at`, `last_attempt_at`,
`next_attempt_at`, `http_status`, `server_date`, and a sanitized `last_error`.
Attribute timestamps include a UTC offset; HA renders timestamp sensors in the
configured time zone.

The quota header is **not a documented contractual field** of the
[SwitchBot API specification](https://github.com/OpenWonderLabs/SwitchBotAPI).
It was observed on a real account and independently reported in
[SwitchBotAPI issue #518](https://github.com/OpenWonderLabs/SwitchBotAPI/issues/518).
It may change or disappear. Do not assume a fixed daily reset time or allowance.

## Maintenance and removal

Update credentials through the original SwitchBot Cloud integration. This observer
reads its current credentials at each scheduled request. If the source entry is
removed, the observer reports failure; create a new observer for a replacement
Cloud entry when needed.

Disable the **SwitchBot API Quota** entry to stop monitoring. To remove it, delete
that entry, remove this custom integration's files and restart HA. Leave the
original SwitchBot Cloud entry in place if you still use it. Removing the observer
deletes its private sampling state, not HA Recorder history.

## Validation and development

The original implementation was verified on **Home Assistant Core 2026.11.0**
running on a SwitchBot AI Hub on 2026-11-11: a real sample, Recorder history,
stored observations, and reload/manual-update throttling were checked. This does
not establish compatibility with every HA installation or future API behavior.

On 2026-11-13, read-only inspection also confirmed ongoing hourly samples and
recorded increases on the deployed implementation. All 18 publication tests passed
with HA 2026.11.0 and Python 3.14.10.

Publication tests use fake HTTP, storage, clock and scheduler with real HA Python
libraries; they consume no SwitchBot API allowance. The polling and observation
logic is unchanged from the deployed implementation. Public packaging adds HACS
metadata, documentation, translations and original counter artwork.

```sh
# Pure observation tests, without Home Assistant:
python -m unittest discover -s tests/switchbot_quota -p test_model.py -v

# Runtime and entity tests, with Python 3.14 on Linux:
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests/switchbot_quota -v
```

CI also runs Home Assistant hassfest and HACS validation. Contributions should
preserve the one-hour guard, failure semantics and credential/privacy boundaries.
Do not put real tokens, configuration exports, household device lists or local
paths in issues or pull requests.

## License

MIT; see [LICENSE](LICENSE). Developed with assistance from OpenAI Codex.
Not affiliated with or endorsed by SwitchBot or Home Assistant. The included
counter icon is original project artwork, not the SwitchBot logo.
