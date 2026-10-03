# Network allowlist for this project

Every host below was derived from the source, not from memory: `tfm_edge/data/*.py`,
`run_real_data.sh`, and the installed `huggingface_hub`. The preflight in
`run_real_data.sh` tests each one and names which is missing.

## Minimum to run the recommended (equity) configuration

| host | port | why | what breaks without it |
|---|---|---|---|
| `stooq.com` | 443 | US equity daily bars, keyless CSV | no price data at all |
| `huggingface.co` | 443 | model metadata and the `resolve` redirect | model will not load |
| `cas-bridge.xethub.hf.co` | 443 | **the actual weight bytes** | metadata downloads, then the weight fetch dies |

**The third line is the one people miss.** `huggingface_hub` ships with `hf_xet`
enabled, so weights are served from the Xet content CDN rather than from
`huggingface.co`. An allowlist containing only `huggingface.co` gets you a successful
metadata request followed by a failed download, which reads like a broken repo rather
than a firewall. Allow `*.xethub.hf.co` if wildcards are available, since the exact CAS
host is returned dynamically in an `X-Xet-Cas-Url` response header and may differ by
region.

If you cannot allow a wildcard or that host, skip Xet entirely:

```bash
export HF_HUB_DISABLE_XET=1
```

and allow these instead:

| host | port | why |
|---|---|---|
| `cdn-lfs.huggingface.co` | 443 | classic LFS weight CDN |
| `cdn-lfs-us-1.huggingface.co` | 443 | regional variant |
| `cdn-lfs-eu-1.huggingface.co` | 443 | regional variant |

## Optional

| host | port | why |
|---|---|---|
| `fapi.binance.com` | 443 | crypto perpetual bars, for the crypto config |
| `api.binance.com` | 443 | only if you set `data.market: spot` |
| `query1.finance.yahoo.com` | 443 | alternative equity source (`equity_source: yahoo`) |
| `query2.finance.yahoo.com` | 443 | Yahoo fails over to this one |

The crypto config is genuinely optional. Four years of perpetual history cannot prove a
plausible edge at any cost level, so it produces a measurement rather than a verdict.
The equity run is the one worth unblocking.

## Already permitted in a standard Claude Code environment

`pypi.org` and `files.pythonhosted.org` are usually reachable already, and are needed
for `pip install`. Verify with `./run_real_data.sh`, which checks before installing.

## Copy-paste forms

Bare list:

```
stooq.com
huggingface.co
cas-bridge.xethub.hf.co
fapi.binance.com
```

Wildcard form, if your policy supports it:

```
stooq.com
*.huggingface.co
*.xethub.hf.co
*.binance.com
```

## Verifying it worked

```bash
./run_real_data.sh
```

The preflight prints one line per host. Any real HTTP code, including 403 or 404, means
the host is reachable. `000` means the connection never completed, which is a firewall,
proxy or DNS block rather than a bad URL.
