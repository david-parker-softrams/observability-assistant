# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.4.0...logai-v0.5.0) (2026-06-16)


### Features

* chat input history navigation (Up/Down arrows) ([#23](https://github.com/david-parker-softrams/observability-assistant/issues/23)) ([4cff78f](https://github.com/david-parker-softrams/observability-assistant/commit/4cff78f2a3b5054bec56db99ebd1da6576b10c09))

## [0.4.0](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.3.2...logai-v0.4.0) (2026-02-27)


### Features

* dynamic context window scaling and remove result caching ([#21](https://github.com/david-parker-softrams/observability-assistant/issues/21)) ([09ef085](https://github.com/david-parker-softrams/observability-assistant/commit/09ef085fee20dee279eb7687c2a49e20ecab1831))

## [0.3.2](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.3.1...logai-v0.3.2) (2026-02-25)


### Bug Fixes

* correct remaining stale model and URL references in docs and code ([58135a6](https://github.com/david-parker-softrams/observability-assistant/commit/58135a60e673ba88e907d5fbba6f6480d2479326))
* sync .env.example and docs with actual settings defaults ([70dd366](https://github.com/david-parker-softrams/observability-assistant/commit/70dd366f1e68b170674fb3e65c26ca02c5263ee7))

## [0.3.1](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.3.0...logai-v0.3.1) (2026-02-25)


### Bug Fixes

* reduce chunk size defaults and teach agent to summarize-as-you-go ([#16](https://github.com/david-parker-softrams/observability-assistant/issues/16)) ([ffdd757](https://github.com/david-parker-softrams/observability-assistant/commit/ffdd7577fd54e1a8df3546e536f86b02cdd4e1ba))

## [0.3.0](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.2.1...logai-v0.3.0) (2026-02-25)


### Features

* integrate MCP server for CloudWatch tool calls ([dabed2f](https://github.com/david-parker-softrams/observability-assistant/commit/dabed2f2c22954c67c80c5dfea4972209d086bec))


### Bug Fixes

* handle MCP Insights results format in result cache ([#15](https://github.com/david-parker-softrams/observability-assistant/issues/15)) ([03520f7](https://github.com/david-parker-softrams/observability-assistant/commit/03520f7d967fbb43fdc4092569db785884ab4c5b))
* pass num_ctx as top-level kwarg to litellm, not as options dict ([#14](https://github.com/david-parker-softrams/observability-assistant/issues/14)) ([9090582](https://github.com/david-parker-softrams/observability-assistant/commit/90905821abf7a1f406e3076ed0790be8d5162ba2))

## [0.2.1](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.2.0...logai-v0.2.1) (2026-02-24)


### Bug Fixes

* remove unnecessary startup tip popup ([#10](https://github.com/david-parker-softrams/observability-assistant/issues/10)) ([f66bbd4](https://github.com/david-parker-softrams/observability-assistant/commit/f66bbd4328d1930e2a82ec9fb8225cca97b29ef1))

## [0.2.0](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.1.0...logai-v0.2.0) (2026-02-24)


### Features

* replace --debug with structured --loglevel system (DEBUG/INFO/WARNING/ERROR) ([#7](https://github.com/david-parker-softrams/observability-assistant/issues/7)) ([6966415](https://github.com/david-parker-softrams/observability-assistant/commit/696641598c69757d9176a18e8575b893277d5492))

## [0.1.0](https://github.com/david-parker-softrams/observability-assistant/compare/logai-v0.0.1...logai-v0.1.0) (2026-02-23)


### Features

* Add adjustable time frame selector to log preview modal ([2ddbb92](https://github.com/david-parker-softrams/observability-assistant/commit/2ddbb92df5187eb2387fca3f69cce00cbb5239f0))
* Add agent guidance for cached results to prevent freeze behavior ([3c3fb54](https://github.com/david-parker-softrams/observability-assistant/commit/3c3fb5456d80f8194e543c230f2cc0d52134c2be))
* add agent self-direction improvements and tool execution sidebar ([5ff6004](https://github.com/david-parker-softrams/observability-assistant/commit/5ff600466da78f07974366c63327b0f420d9fb9f))
* add automated semantic versioning and release system ([819ebef](https://github.com/david-parker-softrams/observability-assistant/commit/819ebef20f82fb3ac6737a77427492ac63b658f7))
* add automatic CloudWatch log group pre-loading at startup ([508a844](https://github.com/david-parker-softrams/observability-assistant/commit/508a84445cc1b34496d858115449a2bd57dca221))
* Add automatic JSON pretty-printing to expanded log messages ([0cf9474](https://github.com/david-parker-softrams/observability-assistant/commit/0cf947409360fd1a3075d063f5d13e6fec60810b))
* Add cache corruption prevention and auto-cleanup ([c7103b2](https://github.com/david-parker-softrams/observability-assistant/commit/c7103b2e3321df689642c0ab3817dbd34062ebd4))
* Add cache metrics recording to fix status bar display ([8dceede](https://github.com/david-parker-softrams/observability-assistant/commit/8dceedec440f16fe0bf29ff9c1fb6923de5b726d))
* Add comprehensive context window management ([9b5397e](https://github.com/david-parker-softrams/observability-assistant/commit/9b5397eb1bf316dfc03c1f6d2340a54480e6c7f0))
* Add comprehensive logging configuration with --debug and --log-file options ([d1480d3](https://github.com/david-parker-softrams/observability-assistant/commit/d1480d3a2796b19355db8d990017d4e53c81d3e3))
* Add externalized model configuration system with YAML support ([4c140cb](https://github.com/david-parker-softrams/observability-assistant/commit/4c140cbfd184710f406c78cd1535192e0afe69b3))
* Add intelligent context management system to prevent context overflow ([1f2a4d8](https://github.com/david-parker-softrams/observability-assistant/commit/1f2a4d8eec354d2caeca7162df85d1af76e2ac66))
* Add log preview feature with double-click log group viewing ([a5512d8](https://github.com/david-parker-softrams/observability-assistant/commit/a5512d8051229387f9438b8ac6d4fada42b427ed))
* Add new models, fix tool calling config, improve caching, fix LSP errors, and enhance TUI usability ([37c3e8d](https://github.com/david-parker-softrams/observability-assistant/commit/37c3e8d805275a70f88ad66c336b6694679fd4e9))
* add text selection and copy/paste to chat and context modal ([4b9b7bf](https://github.com/david-parker-softrams/observability-assistant/commit/4b9b7bfda3a1c172013f554160f0b37c183c5f2b))
* Add toggle button to load last 100 entries in log preview ([3a7c907](https://github.com/david-parker-softrams/observability-assistant/commit/3a7c907fc323d88b9d718930c4d147c0d5c9e5c9))
* add toggleable log groups sidebar to TUI ([7ec297e](https://github.com/david-parker-softrams/observability-assistant/commit/7ec297e6e28dc4298b6c47d0f5fef907b992ecb1))
* **cli:** add --aws-profile and --aws-region arguments ([38931d4](https://github.com/david-parker-softrams/observability-assistant/commit/38931d476bdbe36a6cc4fd6b761e5c9900d6929a))
* **cloudwatch:** Use configurable timeouts and retry settings ([7f05bfe](https://github.com/david-parker-softrams/observability-assistant/commit/7f05bfe33ea195fcc7245f2df4f1d4ea62d9531c))
* **config:** Add Phase 2 configuration settings for externalization ([c30c97c](https://github.com/david-parker-softrams/observability-assistant/commit/c30c97ceac5d5af92627cd278721735a9cbbbd97))
* enhance Context Viewer with full context display and independent scrolling ([6170d18](https://github.com/david-parker-softrams/observability-assistant/commit/6170d186c73549a58f51b4fa6824f79668a36e74))
* **github-copilot:** Use configurable retry, timeout, and cache settings ([66ea70e](https://github.com/david-parker-softrams/observability-assistant/commit/66ea70e9b46d4baef36f3b47f1a5fa504e4bbe50))
* **github-oauth:** Use configurable OAuth and polling settings ([14c2e1a](https://github.com/david-parker-softrams/observability-assistant/commit/14c2e1af1fccade064311a4695737dc20fab29f0))
* improve log group sidebar UX and add testing infrastructure ([6cfc069](https://github.com/david-parker-softrams/observability-assistant/commit/6cfc069c641df8229953c6dcaa84713e34ee286e))
* **llm:** enable Ollama tool calling support with validation ([4112528](https://github.com/david-parker-softrams/observability-assistant/commit/411252807410a4c8ec835f8e1730034811908825))
* Restore status indicator with animated spinner ([78e9c3c](https://github.com/david-parker-softrams/observability-assistant/commit/78e9c3c65ae4af41f821a0f11c718378b0ba1c05))
* test release automation ([4254ff9](https://github.com/david-parker-softrams/observability-assistant/commit/4254ff9ef7cb811aff22362b5c4c371c43e80884))
* **tools-orchestrator-ui:** Use configurable limits, delays, and timeouts ([5b97d73](https://github.com/david-parker-softrams/observability-assistant/commit/5b97d73d3bfdb2e5bf28bb6c3f07bb70492d99e8))


### Bug Fixes

* Add comprehensive cache debug logging and fix expiration off-by-one bug ([b0b8ad7](https://github.com/david-parker-softrams/observability-assistant/commit/b0b8ad76fe918647ed665b567dc9c72f67ad7d42))
* Add proper spacing to StatusFooter between shortcuts and status ([7478f5e](https://github.com/david-parker-softrams/observability-assistant/commit/7478f5e796c94b666b4b3da969885de7ed16027f))
* Add spacing between individual shortcuts in StatusFooter ([93ac4c8](https://github.com/david-parker-softrams/observability-assistant/commit/93ac4c89dc4c974c20fb65cbe52680e2ba7d11f3))
* **aws:** prioritize AWS profile over environment credentials ([7224b63](https://github.com/david-parker-softrams/observability-assistant/commit/7224b63976969f575f62142450c57b6743b7be8d))
* Cache Manager now respects user .env settings ([b8593a4](https://github.com/david-parker-softrams/observability-assistant/commit/b8593a4ac1876cac92d70dafeff51b80fd4efa28))
* change log preview callbacks from async to sync with call_later ([759403f](https://github.com/david-parker-softrams/observability-assistant/commit/759403f1313b1611270752ef93a3dd9b1fa3a601))
* Combine cache guidance and user context in Add to Context feature ([620defd](https://github.com/david-parker-softrams/observability-assistant/commit/620defd845e1a226e9dd20985762859548c471a7))
* Correct CSS layout to make header and time frame controls visible ([8a594e2](https://github.com/david-parker-softrams/observability-assistant/commit/8a594e2d3459a51955d295797921825b105591e5))
* Correct Qwen3 context window and skip empty cache lookups ([7017726](https://github.com/david-parker-softrams/observability-assistant/commit/7017726843003d0518a8e890a5b7ac84964b1987))
* Eliminate cache initialization race condition ([81767b4](https://github.com/david-parker-softrams/observability-assistant/commit/81767b4c031573cfc5efa166559868d244133e02))
* Handle Blank object in StatusFooter to prevent startup crash ([12e4f29](https://github.com/david-parker-softrams/observability-assistant/commit/12e4f296a3250c3074dac75c34182b7462d9e94d))
* isolate clickable area in status footer to context info only ([7d7f8c4](https://github.com/david-parker-softrams/observability-assistant/commit/7d7f8c422924d8449a9d95540b7f5052a79dd05f))
* **llm:** prevent sending tools to Ollama provider to avoid infinite loop ([111306d](https://github.com/david-parker-softrams/observability-assistant/commit/111306db3c6cf989d36ce0bbf030f1701b9f93e3))
* merge context injection into system prompt to ensure agent visibility ([8692862](https://github.com/david-parker-softrams/observability-assistant/commit/8692862e05166195edb5026ccbcea9ba28f3d5c4))
* Prevent debug logs from appearing in TUI ([38a1ddd](https://github.com/david-parker-softrams/observability-assistant/commit/38a1ddd5575fba894cfeb8c4fd4bb1e0bd11f824))
* Prevent LLM from truncating cache_id in fetch calls ([59e4274](https://github.com/david-parker-softrams/observability-assistant/commit/59e4274565eddb5ce716f3a619dc0335ecafb1c7))
* Refactor StatusFooter to inherit from Widget to eliminate rendering conflict ([f09e38e](https://github.com/david-parker-softrams/observability-assistant/commit/f09e38e2c341d0290cf97d3f7a353b282cb33b05))
* Remove duplicate ctrl+q quit binding and fix isinstance syntax ([1665118](https://github.com/david-parker-softrams/observability-assistant/commit/1665118bddd57123d72fdcbaa71ca438c760e1ae))
* Remove invalid :active pseudo-class from log groups sidebar CSS ([5666c1c](https://github.com/david-parker-softrams/observability-assistant/commit/5666c1c925c318fe7df4ace387fda5f1c0b76625))
* Remove invalid cursor CSS property from log groups sidebar ([2a4f5b8](https://github.com/david-parker-softrams/observability-assistant/commit/2a4f5b800e12db37a6b92db73a74287e6a6924e2))
* Remove unnecessary notification popups on panel resize ([eca4ea1](https://github.com/david-parker-softrams/observability-assistant/commit/eca4ea1e71ed80dfbf74179924ffc649e86234aa))
* rename release-please config file (remove leading dot) ([31fc9d0](https://github.com/david-parker-softrams/observability-assistant/commit/31fc9d0fbd4a9de86fae34eda4b7465e63ee73c5))
* reorder messages to place context injection before user message ([6a6e2c1](https://github.com/david-parker-softrams/observability-assistant/commit/6a6e2c1562f0e096f088642736168ea985298110))
* Restore clickable keyboard shortcuts in StatusFooter ([7ed4e34](https://github.com/david-parker-softrams/observability-assistant/commit/7ed4e343bafffa88aac05f4f0997a33d4c8c7ea8))
* Restore status bar visibility by merging with Footer ([9825fca](https://github.com/david-parker-softrams/observability-assistant/commit/9825fcad0fc88aa898780c74a61f01f76a3fcf9c))
* Suppress LiteLLM console logging to prevent TUI pollution ([3be6c43](https://github.com/david-parker-softrams/observability-assistant/commit/3be6c43903e50024522228a69cf2acb10057f7f6))
* teach agent to recognize and prioritize user-provided context logs ([d6703d0](https://github.com/david-parker-softrams/observability-assistant/commit/d6703d0fc2338f91dc67be8083f564460b097a89))
* **tui:** add explicit heights to message widgets to prevent blank screen ([5ba5e97](https://github.com/david-parker-softrams/observability-assistant/commit/5ba5e97fdac336f713fcd25a80680edf4d4ebe0a))
* **tui:** properly initialize ChatScreen using push_screen in on_mount ([604bd39](https://github.com/david-parker-softrams/observability-assistant/commit/604bd3916cf9857a896740e2248c5d997cb53586))
* **tui:** resolve blank screen issue with async on_mount and CSS path ([4e3d1f1](https://github.com/david-parker-softrams/observability-assistant/commit/4e3d1f14e4ff62aa79ac6df7f2cabf1df955213d))
* **tui:** resolve layout conflicts causing blank screen ([938366f](https://github.com/david-parker-softrams/observability-assistant/commit/938366f87cba5179a4d3693edfea5b7346c7ef62))
* update GitHub Actions workflow permissions to allow PR creation ([2326462](https://github.com/david-parker-softrams/observability-assistant/commit/23264620d21c5e71815620bb18ef5eea12f6562c))
* use callback pattern for modal result in log preview ([b0ae572](https://github.com/david-parker-softrams/observability-assistant/commit/b0ae572c06296154e750975187fefd90d0c5eb5d))


### Reverts

* rollback TextArea implementation, restore Static widgets ([5650d73](https://github.com/david-parker-softrams/observability-assistant/commit/5650d73dfd3752a773e0e63d7f8f5d8c3f1c44cb))


### Documentation

* add comprehensive end-user documentation ([54bf0f3](https://github.com/david-parker-softrams/observability-assistant/commit/54bf0f3cc9f0aada557655737460ef206d3b67ba))
* add feature branch git workflow for team ([6d83e3b](https://github.com/david-parker-softrams/observability-assistant/commit/6d83e3be533826a5bda21b6e4d34ca4021557425))
* add mandatory feature development workflow for George (TPM) ([df7c686](https://github.com/david-parker-softrams/observability-assistant/commit/df7c686a2eb53e44b36b323ba55aab59bbafe391))
* Add PR review workflow documentation ([#1](https://github.com/david-parker-softrams/observability-assistant/issues/1)) ([8d9c67b](https://github.com/david-parker-softrams/observability-assistant/commit/8d9c67b06392ee7e8166ffb2e2bba6ec8220d989))
* Add session notes and Textual layout best practices ([abb25aa](https://github.com/david-parker-softrams/observability-assistant/commit/abb25aa32abf05571c93651fe522bea8f0275c98))
* Emphasize critical importance of git pull before creating branches ([#2](https://github.com/david-parker-softrams/observability-assistant/issues/2)) ([d61a129](https://github.com/david-parker-softrams/observability-assistant/commit/d61a129dc2b85514506f2ec125f118b0d8be2b6b))
* Move high-value documentation from george-scratch to permanent locations ([99ddc5a](https://github.com/david-parker-softrams/observability-assistant/commit/99ddc5af3a892d1c24521bd468ac7430c43b4113))
* **phase2:** Add comprehensive Phase 2 verification and testing documentation ([f41c617](https://github.com/david-parker-softrams/observability-assistant/commit/f41c617f460e6cfba7ace4846e682b5a6fd94431))
* Reorganize documentation into structured hierarchy ([4f8aed9](https://github.com/david-parker-softrams/observability-assistant/commit/4f8aed9f7d38b1e7a82565e163810d751dfd67d7))

## [Unreleased]

### Changed
- **Context window scaling**: Ollama provider no longer hardcodes a 32,768-token context window. The system now auto-detects the correct context window size from the model registry at runtime. Users can still override this with `LOGAI_OLLAMA_NUM_CTX`.
- **Tool result pass-through**: Large tool results are no longer cached and replaced with a truncated preview. All tool results now pass through to the model in full.
- **Emergency pruning threshold**: The emergency pruning threshold is now percentage-based (`LOGAI_EMERGENCY_PRUNE_THRESHOLD_PCT`, default `4`%) instead of an absolute token count.

### Added
- **Context utilization warnings**: Users now see a toast notification when context window utilization reaches 85%, 90%, and 95%. Each tier fires at most once per conversation session.
- New setting `LOGAI_EMERGENCY_PRUNE_THRESHOLD_PCT` (float, default `4.0`, range `1–20`) replaces `LOGAI_EMERGENCY_PRUNE_THRESHOLD`.

### Deprecated
- `LOGAI_ENABLE_RESULT_CACHING` — result caching has been removed; this setting is accepted but has no effect.
- `LOGAI_CACHE_LARGE_RESULTS_THRESHOLD` — same as above.
- `LOGAI_MAX_RESULT_TOKENS` — same as above.
- `LOGAI_EMERGENCY_PRUNE_THRESHOLD` (absolute token count) — replaced by `LOGAI_EMERGENCY_PRUNE_THRESHOLD_PCT`.
