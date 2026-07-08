# Changelog

## [1.2.0](https://github.com/VforVitorio/marginalia/compare/v1.1.4...v1.2.0) (2026-07-08)


### Features

* **api:** restore the GET /api/scan endpoint ([bdcfda0](https://github.com/VforVitorio/marginalia/commit/bdcfda0e98d39252830d60daeae22e0863a9a9eb))
* **api:** restore the GET /api/scan endpoint ([08d3872](https://github.com/VforVitorio/marginalia/commit/08d38723545ab550bda37ada4bd8d7fb3e42c85c)), closes [#135](https://github.com/VforVitorio/marginalia/issues/135)
* **export:** persist vault path and strategies after export ([c3289ad](https://github.com/VforVitorio/marginalia/commit/c3289ad1f5f15f688875c19a62d84a3dc431df01))
* **export:** persist vault path and strategies after export ([c406333](https://github.com/VforVitorio/marginalia/commit/c406333e9669ed3e9122fb2a88e3d2a7176f54b1)), closes [#146](https://github.com/VforVitorio/marginalia/issues/146)
* **landing:** add per-OS install buttons that copy the command ([1220938](https://github.com/VforVitorio/marginalia/commit/122093855fb7597ee2cc651a32ec2d31ea28b557))
* **landing:** per-OS install buttons that copy the command ([3820b9f](https://github.com/VforVitorio/marginalia/commit/3820b9f5e49c387f2cfb0889f4047749957a2ab6))
* **providers:** let users pick a cloud model, not just the default ([ef43f47](https://github.com/VforVitorio/marginalia/commit/ef43f4755a79178118013c488879f92519c05d43))
* **providers:** let users pick a cloud model, not just the default ([4abf139](https://github.com/VforVitorio/marginalia/commit/4abf1392d4a8558b0766b7b47306fba9078b52b4))


### Bug Fixes

* **api:** make provider status and OCR failures honest ([a245154](https://github.com/VforVitorio/marginalia/commit/a245154d73c895393221575fc0d63372cd018cdb))
* **api:** make provider status and OCR failures honest ([0f41bf0](https://github.com/VforVitorio/marginalia/commit/0f41bf0da8de23d5444c81d6f65b3529e8330e53)), closes [#139](https://github.com/VforVitorio/marginalia/issues/139)
* **api:** make the OCR SSE stream robust to slow and hung engines ([722130a](https://github.com/VforVitorio/marginalia/commit/722130aabaff0f87dccb027ad5d65f10ab88ba7d))
* **api:** make the OCR SSE stream robust to slow and hung engines ([8a0d9f0](https://github.com/VforVitorio/marginalia/commit/8a0d9f060c6f699cd802a160be5024179c77fa7d))
* **api:** run PDF rasterization off the event loop ([6408cd1](https://github.com/VforVitorio/marginalia/commit/6408cd148c207d188dcbb6d7388fb11e49cd03a1))
* **api:** run PDF rasterization off the event loop ([193bb68](https://github.com/VforVitorio/marginalia/commit/193bb689ee3a05fedbd807292c3cc496a93a9d40))
* **deps:** bump vitest to 3.2.7 to close critical RCE advisory ([4d2cfd8](https://github.com/VforVitorio/marginalia/commit/4d2cfd83ef8bb23690fda7ac7e3cc16708da7a8a))
* **deps:** bump vitest to 3.2.7 to close critical RCE advisory ([dda98b7](https://github.com/VforVitorio/marginalia/commit/dda98b7151f7db72af846a17df6e0c9002879416))
* **deps:** pin frontend dev-deps to peer-compatible majors ([b607abc](https://github.com/VforVitorio/marginalia/commit/b607abc60c56d285b034e7b5a919b5ffc465c43a))
* **deps:** pin frontend dev-deps to peer-compatible majors ([ef317bb](https://github.com/VforVitorio/marginalia/commit/ef317bbc3b1682115cf4ee04171f0b4ced506442))
* **export:** merge wikilinks index instead of overwriting it ([65ee35d](https://github.com/VforVitorio/marginalia/commit/65ee35df250d59041e9de75929eb3359f1eef77b))
* **export:** merge wikilinks index instead of overwriting it ([a761bd5](https://github.com/VforVitorio/marginalia/commit/a761bd5592d9d709324a4776b51f6731211c4ae3))
* **export:** use a realpath containment barrier CodeQL recognizes ([27b2f8e](https://github.com/VforVitorio/marginalia/commit/27b2f8e36405a6c254447f0c6668f49f3f958d4d))
* **frontend:** add error boundary, fix header merge order, document contract types ([39151c9](https://github.com/VforVitorio/marginalia/commit/39151c9b18af740fcff80a4464087e5e1b8c671a))
* **frontend:** error boundary, header merge order, contract type docs ([3ac138f](https://github.com/VforVitorio/marginalia/commit/3ac138fa35eadd890bef83109d11429f06441469))
* **frontend:** refresh, empty and busy states for the provider picker ([ad2e8a5](https://github.com/VforVitorio/marginalia/commit/ad2e8a5e91126954578c50cbe9c5403b4a35db0f))
* **frontend:** refresh, empty and busy states for the provider picker ([2ac0cf0](https://github.com/VforVitorio/marginalia/commit/2ac0cf018a4d2e6fa7cd1bd78826b9a471791981))
* **frontend:** stop streaming re-renders from re-parsing done pages ([773b75c](https://github.com/VforVitorio/marginalia/commit/773b75cf9ccbda65e4c5b724125506a74d22d02e))
* **frontend:** stop streaming re-renders from re-parsing done pages ([7b69f25](https://github.com/VforVitorio/marginalia/commit/7b69f25c4308fa861b395307172a1cee6ffce443))
* **models-admin:** surface Ollama pull progress and failures ([5f7945d](https://github.com/VforVitorio/marginalia/commit/5f7945d1a3a2ddb2f038a9297419bdd32d4af819))
* **models-admin:** surface Ollama pull progress and failures ([85d1af5](https://github.com/VforVitorio/marginalia/commit/85d1af5f61fd05a47462e9260816397e1da43122))
* **persistence:** anchor config paths and make on-disk writes atomic ([50f52c3](https://github.com/VforVitorio/marginalia/commit/50f52c3cfb249edafa3be2a133391906bf62c10f))
* **persistence:** anchor config paths and make on-disk writes atomic ([90754d3](https://github.com/VforVitorio/marginalia/commit/90754d3a734e5b41ed5b92dd4ecf01ae0a80f325))
* **review:** stop dropping edits in the auto-save path ([648cad0](https://github.com/VforVitorio/marginalia/commit/648cad04111de2e189d5061fcf1b60dea05dc79e))
* **review:** stop dropping edits in the auto-save path ([a032c57](https://github.com/VforVitorio/marginalia/commit/a032c5756b5ddab8ef9cb68d04fb9c8fc42e2d42)), closes [#133](https://github.com/VforVitorio/marginalia/issues/133)
* **stream:** resume instead of re-OCRing, reset on disconnect, guard reruns ([3c67627](https://github.com/VforVitorio/marginalia/commit/3c676278d538e9e9c78ffbab293e65e67ce69579))
* **stream:** resume instead of re-OCRing, reset on disconnect, guard reruns ([dc09055](https://github.com/VforVitorio/marginalia/commit/dc0905525add95ab0fae9cc36e7ba9a810120bcb)), closes [#134](https://github.com/VforVitorio/marginalia/issues/134)


### Documentation

* **backlog:** note domain feature ideas + untapped Scribe PDF signal ([0b0d5ae](https://github.com/VforVitorio/marginalia/commit/0b0d5aefea5fe196742a0380feb42db61f25580a))
* **backlog:** note domain feature ideas + untapped Scribe PDF signal ([9c8c22e](https://github.com/VforVitorio/marginalia/commit/9c8c22e1c21de15741b0c789d038be1fa5c5b93c))
* **readme:** finalize the README ([1ffd373](https://github.com/VforVitorio/marginalia/commit/1ffd373817830a2a799893c60a18e4187c0054e6))
* **readme:** finalize the README ([e0d543b](https://github.com/VforVitorio/marginalia/commit/e0d543b5d31af5d88476b0abed591e69dd5f184a))
* **research:** add backend + frontend/architecture audit reports ([9d7a6a0](https://github.com/VforVitorio/marginalia/commit/9d7a6a059c271326797d2481616c91cd66882e72))
* **research:** add backend + frontend/architecture audit reports ([1f8a8a8](https://github.com/VforVitorio/marginalia/commit/1f8a8a828f84736166d29e04a316680faf77a0d5))

## [1.1.4](https://github.com/VforVitorio/marginalia/compare/v1.1.3...v1.1.4) (2026-07-05)


### Documentation

* **demo:** add 8:5 video poster stills (EN/ES) ([cf87c33](https://github.com/VforVitorio/marginalia/commit/cf87c330cd5db99f0ca0f63396bfbd5b648e69ec))
* **demo:** add 8:5 video poster stills (EN/ES) ([31fd150](https://github.com/VforVitorio/marginalia/commit/31fd150bc5b65cea4667c6ed226712211801dc46))
* **demo:** add landing page hero screenshots (EN/ES) ([8b1ed45](https://github.com/VforVitorio/marginalia/commit/8b1ed4579aaecc0c84738d4cdc79543e8594867e))
* **demo:** add landing page hero screenshots (EN/ES) ([4666b48](https://github.com/VforVitorio/marginalia/commit/4666b48b8a2139ff1b2f38b39036ab7de1d0c8d3))

## [1.1.3](https://github.com/VforVitorio/marginalia/compare/v1.1.2...v1.1.3) (2026-06-29)


### Bug Fixes

* **landing:** smooth author bio (from computer vision to LLM behavior) ([d6098e9](https://github.com/VforVitorio/marginalia/commit/d6098e9c04e655f526efaac9404710616da6d59f))
* **landing:** smooth author bio (from computer vision to LLM behavior) ([ade1bf8](https://github.com/VforVitorio/marginalia/commit/ade1bf8a960fe1bd7380def067fd5da7e0e11522))

## [1.1.2](https://github.com/VforVitorio/marginalia/compare/v1.1.1...v1.1.2) (2026-06-28)


### Documentation

* **landing:** normalize author bio to canonical wording ([cbfdfd2](https://github.com/VforVitorio/marginalia/commit/cbfdfd256654ae03f017557c2d3015b2dbde0bc6))
* **landing:** normalize author bio to canonical wording ([362e64c](https://github.com/VforVitorio/marginalia/commit/362e64c64b8d26d8c7ddeee9867174dae709760c))

## [1.1.1](https://github.com/VforVitorio/marginalia/compare/v1.1.0...v1.1.1) (2026-06-27)


### Documentation

* **landing:** terminal install boxes with copy button ([d27f282](https://github.com/VforVitorio/marginalia/commit/d27f2829bea4906df635f5bc1b760ff434d255c7))
* **landing:** terminal-style install boxes with copy button ([f3ad2a6](https://github.com/VforVitorio/marginalia/commit/f3ad2a6ac5ad5caaf97555d7aef162bbc5c582b8))
* **landing:** wrap install command + honours wording ([4b9f06c](https://github.com/VforVitorio/marginalia/commit/4b9f06c60f914384fd5949ab037e7deb31c3d12a))
* **landing:** wrap install command + refine EN honours wording ([517b0f6](https://github.com/VforVitorio/marginalia/commit/517b0f6511ddd16829c69f2c3ddb6bf72bc631bb))

## [1.1.0](https://github.com/VforVitorio/marginalia/compare/v1.0.0...v1.1.0) (2026-06-27)


### Features

* **install:** one-command installer (no Node) + landing install/version ([64152ce](https://github.com/VforVitorio/marginalia/commit/64152ce7bb57e36853e8c5245ee54e0de169a111))
* **install:** one-command installer + landing install/version badge ([457be18](https://github.com/VforVitorio/marginalia/commit/457be18aed46b9ca672a291da4faff02e5a6390c))


### Documentation

* **landing:** EN 'Distinction' wording + working-while-studying note ([43bfea3](https://github.com/VforVitorio/marginalia/commit/43bfea3dfe4f7faecde0b4b6440ae7dd11515743))
* **landing:** English distinction wording + working-while-studying note ([9f328a8](https://github.com/VforVitorio/marginalia/commit/9f328a8ef81f482fa9d9bb97e06a3b9a43aca5a5))
* **landing:** SVG icons + Meet the author ([ab11a4b](https://github.com/VforVitorio/marginalia/commit/ab11a4b2fb30015409303a9e86ab4d71837034e6))
* **landing:** SVG icons, Meet the author section, drop CF beacon ([fd50a86](https://github.com/VforVitorio/marginalia/commit/fd50a86a97a291bebfe2fcb9cb0b10a86b1e4712))
* product landing page (GitHub Pages) + README FAQ ([8a55545](https://github.com/VforVitorio/marginalia/commit/8a5554559fa95c6d512adcb664044f30c58fcf71))
* product landing page (GitHub Pages) + README FAQ ([afcba4a](https://github.com/VforVitorio/marginalia/commit/afcba4aa46cbf933aca20726c044512856db0453))

## [1.0.0](https://github.com/VforVitorio/marginalia/compare/v0.1.0...v1.0.0) (2026-06-24)


### Features

* **api:** FastAPI routers, model admin, and static frontend serving ([2f491d0](https://github.com/VforVitorio/marginalia/commit/2f491d05c3eb4995efeea15af5ad55976408a667))
* **api:** FastAPI routers, model admin, and static frontend serving ([27d575a](https://github.com/VforVitorio/marginalia/commit/27d575a3a57ae862d4ec750b5663a0dfeed6f4f4))
* **api:** GET /api/providers/status (reachable / loaded models / next-step hint) ([d28a5ff](https://github.com/VforVitorio/marginalia/commit/d28a5ff722dcf63a7f2d4022dade16c3c24c01dd))
* **api:** provider status endpoint (reachable / models / state) ([a4a0f4b](https://github.com/VforVitorio/marginalia/commit/a4a0f4b94f650ab480c7f564061bfff44afde4b5))
* **export:** choose a target folder for loose drag-and-drop notebooks ([a91390d](https://github.com/VforVitorio/marginalia/commit/a91390d60d6d9b9e57fd714abc41ffe346e010cc))
* **export:** choose a target folder for loose drag-and-drop notebooks ([8e59695](https://github.com/VforVitorio/marginalia/commit/8e596950d52aea448901d85d3f66165c6f0fcd23))
* **frontend:** clickable step indicator + Back button ([6d66552](https://github.com/VforVitorio/marginalia/commit/6d665525483d648e03a5910d5749dd612940576a))
* **frontend:** clickable step indicator and Back button on Review ([bc0c24d](https://github.com/VforVitorio/marginalia/commit/bc0c24d56c8aff96a2c4405d6ba08a9c140f981f))
* **frontend:** Import-Review-Export flow (Vite/React/Tailwind/GSAP) ([7a20059](https://github.com/VforVitorio/marginalia/commit/7a20059019ed9957a64300bd901453a0142dd3ca))
* **frontend:** Import-Review-Export flow (Vite/React/Tailwind/GSAP) ([ffebed1](https://github.com/VforVitorio/marginalia/commit/ffebed1e2915bbcbaaaefc2b61ce80a30ff53759))
* **import/export:** vault + scan-folder path suggestions ([bbd473b](https://github.com/VforVitorio/marginalia/commit/bbd473b47b2d0644c9d271688cf92e747f953365))
* **ingest:** render Scribe PDFs to page images and scan folders ([4dcb9c2](https://github.com/VforVitorio/marginalia/commit/4dcb9c25f254b661956172b3f3d3b09562b0e302))
* **ingest:** render Scribe PDFs to page images and scan folders ([32a806f](https://github.com/VforVitorio/marginalia/commit/32a806f5af27f6861f87cfa0286eff0edf8991dd))
* **jobs:** on-disk job store and OCR orchestration with SSE events ([2aa8fa6](https://github.com/VforVitorio/marginalia/commit/2aa8fa6ce5a05b725b7eb4e1358aca17f96c930f))
* **jobs:** on-disk job store and OCR orchestration with SSE events ([c8e7ced](https://github.com/VforVitorio/marginalia/commit/c8e7cede750fedbb17cb7b3d4873176c076b9d7f))
* **ocr:** config, OCR engine seam, and provider adapters ([a9a5a66](https://github.com/VforVitorio/marginalia/commit/a9a5a66f844e1556f19cdbd26f8776979ce79ad8))
* **ocr:** Obsidian-tuned system prompt + model-quality disclaimer ([c19e6d0](https://github.com/VforVitorio/marginalia/commit/c19e6d0f74197f2f004fd7842c2d6fd7cb4e5a3d))
* **ocr:** Obsidian-tuned system prompt + model-quality disclaimer ([537a8c1](https://github.com/VforVitorio/marginalia/commit/537a8c1662d347be7132a27797866c7515edbf64))
* **ocr:** render diagrams as Mermaid and tabular data as Markdown tables ([36a74f2](https://github.com/VforVitorio/marginalia/commit/36a74f23340c3bf7144d962532041d9ed463eb4f))
* **onboarding:** Guide button to reopen + clearer step copy ([f765f19](https://github.com/VforVitorio/marginalia/commit/f765f19312ae27e712c8aba193b736aa5e788390))
* **picker:** in-app setup guidance for LM Studio and Ollama ([6a38ec0](https://github.com/VforVitorio/marginalia/commit/6a38ec0f1d93fae362d172dda65f85fedbad49a6))
* **picker:** in-app setup guidance for LM Studio and Ollama ([b092343](https://github.com/VforVitorio/marginalia/commit/b0923435223c2cd8b7b76a9c7b3422c78c671e8b))
* **providers:** pull an Ollama model from the picker ([44b68b4](https://github.com/VforVitorio/marginalia/commit/44b68b496d737376792c78cb50b06bdb67f71e7b))
* **providers:** real status, headless LM Studio loading, cloud key entry ([37cea37](https://github.com/VforVitorio/marginalia/commit/37cea37d43b766fdde6060e66ff5f428f3a96539))
* **providers:** real status, headless LM Studio loading, cloud key entry ([ceb0555](https://github.com/VforVitorio/marginalia/commit/ceb05559650db195ddc2dc38543579f3320f3ffa))
* **review:** gate export on OCR error, add Stop button, log failures ([e5a3390](https://github.com/VforVitorio/marginalia/commit/e5a33908b8cce8004ed81673724aeb031a539c06))
* **review:** gate export on OCR error, add Stop button, log OCR failures ([7607186](https://github.com/VforVitorio/marginalia/commit/76071866dd8b49ea1b02428eb2c2bdbcbc7c6574))
* **review:** inline Markdown editor with KaTeX preview ([61b8c87](https://github.com/VforVitorio/marginalia/commit/61b8c873d918539b1e8b35beac33a5c53b1ac1b2))
* **review:** inline Markdown editor with KaTeX preview ([1eb18d4](https://github.com/VforVitorio/marginalia/commit/1eb18d4746df05838755afa9542359664bf00103))
* **run:** one-command setup-and-run + `marginalia` console script ([f605821](https://github.com/VforVitorio/marginalia/commit/f605821050fe51e95af2d5f52cebef873b0b4984)), closes [#58](https://github.com/VforVitorio/marginalia/issues/58)
* **run:** one-command setup-and-run + marginalia console script ([b0e7ca0](https://github.com/VforVitorio/marginalia/commit/b0e7ca0c18e739aab0fe87e095cba95122bef96e))
* **structure:** mirror/wikilinks mapper and Jinja2 vault export ([20270b4](https://github.com/VforVitorio/marginalia/commit/20270b47e34fc4d1dd4c37f92615348091a72302))
* **structure:** mirror/wikilinks mapper and Jinja2 vault export ([f1e5a2b](https://github.com/VforVitorio/marginalia/commit/f1e5a2b5fc0bc7c6159f2984021b7de38849cef5))
* **structure:** navigable folder-index tree; drop root index.md ([796d4f8](https://github.com/VforVitorio/marginalia/commit/796d4f8412ef72295e032948cf101611359f7b5b))
* **structure:** navigable folder-index tree; drop root index.md ([4c6b1bf](https://github.com/VforVitorio/marginalia/commit/4c6b1bfcd1ead1ba9e1a1a69b786ce34181ab577))
* **ui:** onboarding Guide button, path suggestions, Ollama pull ([d266a30](https://github.com/VforVitorio/marginalia/commit/d266a307386e1466dc93bdf29180261c4e7710d9))


### Bug Fixes

* **api:** type-clean provider status construction (mypy) ([74da398](https://github.com/VforVitorio/marginalia/commit/74da39869fc35eddfa4e2abccb719737c24b1bdc))
* **ci:** clear the scanner gates — select_autoescape + ignore dev-only osv advisories ([4d92c2c](https://github.com/VforVitorio/marginalia/commit/4d92c2cb623493bf78e6fc4b3029b3addf223346))
* **ci:** move osv ignore config next to frontend/package-lock.json ([6318b83](https://github.com/VforVitorio/marginalia/commit/6318b8305488dd09310375339522a65e0a516b67))
* **ci:** osv ignore config must sit next to the frontend lockfile ([e4bd655](https://github.com/VforVitorio/marginalia/commit/e4bd6553d37146864b5567df8de49b61e9dd0b05))
* **export:** reject note paths that escape the vault (path traversal) ([a8318d9](https://github.com/VforVitorio/marginalia/commit/a8318d95f55ee0daaf2e708ff6004afea4dc250b))
* **export:** reject note paths that escape the vault (path traversal) ([1ce41a3](https://github.com/VforVitorio/marginalia/commit/1ce41a325583e683ce90fede2eac8f5eb8d0cbe9))
* **layout:** responsive header — wrap step indicator on mobile ([#39](https://github.com/VforVitorio/marginalia/issues/39)) ([59ff776](https://github.com/VforVitorio/marginalia/commit/59ff7763e5e69c4158cc79b9ebe72507f54e8217))
* **layout:** responsive header for mobile ([#39](https://github.com/VforVitorio/marginalia/issues/39)) ([9a213de](https://github.com/VforVitorio/marginalia/commit/9a213deb3ea11960f8bf265d9c7dff1b213fdcee))
* **providers:** real Claude auth probe + robust LM Studio loading + selectable rows ([4411ffb](https://github.com/VforVitorio/marginalia/commit/4411ffb70f851a07a2196c419e84a0b7dd7a4ddc))
* **providers:** real Claude auth, robust LM Studio loading, selectable rows, Mermaid prompt ([9544328](https://github.com/VforVitorio/marginalia/commit/9544328f732b013e1200498be250d25c7c1317dd))
* **review:** 1-based page indices + no auto-jump (editor now works) ([8524ed7](https://github.com/VforVitorio/marginalia/commit/8524ed74fcb4cc37b300c16e7fd5aca45b349b77))
* **review:** align page indices to 1-based + stop auto-jumping the view ([b07474e](https://github.com/VforVitorio/marginalia/commit/b07474e38e26ee7c3b14e3b60be1e100f3be2429))
* **review:** larger source image on big screens ([#39](https://github.com/VforVitorio/marginalia/issues/39)) ([cc71ef3](https://github.com/VforVitorio/marginalia/commit/cc71ef3943030aa498c3fc0a96f207535179259a))
* **review:** let the source page use more height on large screens ([8a52885](https://github.com/VforVitorio/marginalia/commit/8a528851cc2ded94a45bec4abd8bf6c8539ea877)), closes [#39](https://github.com/VforVitorio/marginalia/issues/39)
* **review:** page labels off by one (2-14 instead of 1-13) ([12105ef](https://github.com/VforVitorio/marginalia/commit/12105efebedfd09c0c0c391291255f00e64c9233))
* **review:** page labels were off by one (showed 2-14 for 13 pages) ([12dd5d5](https://github.com/VforVitorio/marginalia/commit/12dd5d5cb80730547b4124ae54a0807527ef370c))
* **security:** job_id validation, export vault confinement, no exception leakage ([9ef0506](https://github.com/VforVitorio/marginalia/commit/9ef05062eddbc1ba3a7829c614fe74f78b69899d))
* **security:** validate job_id, confine exports to the vault, stop leaking exceptions ([55ea7bc](https://github.com/VforVitorio/marginalia/commit/55ea7bcdf33c650536f8b5a7eb0007c701fbedcd))
* **security:** write exports through the validated path so CodeQL sees the guard ([d2a8e0e](https://github.com/VforVitorio/marginalia/commit/d2a8e0e00feb75c26376a96c1bac6387bf35cbb5))


### Performance Improvements

* **markdown:** raw streaming render + fix nested-interactive preview ([2bec48e](https://github.com/VforVitorio/marginalia/commit/2bec48e59a46905bc5775d802f1dfcbfa06eb9a0))
* **markdown:** render raw text while OCR streams; fix nested-interactive preview ([4327421](https://github.com/VforVitorio/marginalia/commit/43274211d569fb75afabdb9d56d51afcd4498a5d)), closes [#63](https://github.com/VforVitorio/marginalia/issues/63) [#66](https://github.com/VforVitorio/marginalia/issues/66)
* **review:** memoize page tabs; reliable Saving indicator; progressbar role ([6afb017](https://github.com/VforVitorio/marginalia/commit/6afb017ad8917b381fbdd5e3e17911e257210421)), closes [#68](https://github.com/VforVitorio/marginalia/issues/68) [#69](https://github.com/VforVitorio/marginalia/issues/69) [#70](https://github.com/VforVitorio/marginalia/issues/70)
* **review:** memoize tabs + reliable Saving indicator + progressbar a11y ([ee82c2e](https://github.com/VforVitorio/marginalia/commit/ee82c2e95d88c5d98a62be3b09ae36be2ac32f5d))


### Reverts

* **security:** drop export vault confinement (CodeQL false positives) ([2bc5bf2](https://github.com/VforVitorio/marginalia/commit/2bc5bf25592819d8f679f4326bbc212cf86e2ffe))


### Documentation

* add logo to README, roadmap/sprint plan, and OCR system-prompt section ([abdc17b](https://github.com/VforVitorio/marginalia/commit/abdc17b54546ab8dbef9a004febe448ddca1b5e0))
* **backlog:** park post-MVP ideas (myClippings, Scribe-native angle, packaging) ([19519b2](https://github.com/VforVitorio/marginalia/commit/19519b2e5d1470f239013026fccc90a6bb7c21a9))
* **backlog:** park post-MVP ideas (myClippings, Scribe-native, packaging) ([7ab5bd7](https://github.com/VforVitorio/marginalia/commit/7ab5bd778de82ef1d6fb33f963ae2c486054156a))
* **demo:** tighten demo pacing ([e2438c7](https://github.com/VforVitorio/marginalia/commit/e2438c78bebbfe29a05dfd7ca1c0b8ca13dc565d))
* **demo:** tighten demo pacing ([c502be4](https://github.com/VforVitorio/marginalia/commit/c502be4abc8433b4bc495a92c0c7dccf97b6e177))
* **demo:** v3 — rendered result + inline edit, fast-forwarded OCR ([7ffe595](https://github.com/VforVitorio/marginalia/commit/7ffe5951a3e9ddc37858511642e161787ca934b5))
* **demo:** v3 — show the rendered result + inline edit, fast-forward OCR ([1b5bce2](https://github.com/VforVitorio/marginalia/commit/1b5bce281e22d2082a9294060716f1972a30dd22)), closes [#9](https://github.com/VforVitorio/marginalia/issues/9)
* logo in README, roadmap/sprint plan, system-prompt section ([4f0882c](https://github.com/VforVitorio/marginalia/commit/4f0882c8ea283ad5bc7556bf6b2794966c98aff6))
* **readme:** add demo GIF + video hero ([84649ef](https://github.com/VforVitorio/marginalia/commit/84649eff7a77c6557311e197d91f91bbb42ca7d3))
* **readme:** add demo GIF + video hero ([09254f3](https://github.com/VforVitorio/marginalia/commit/09254f3db804ef82b720c0e772420861bffa9254))
* **readme:** bring it current for launch ([6d4c08f](https://github.com/VforVitorio/marginalia/commit/6d4c08fc07d4ad9de6184d7d7bb737346177b79a))
* **readme:** drop the play emoji from the demo video link ([81ea8ee](https://github.com/VforVitorio/marginalia/commit/81ea8ee3fe340bf5477a9b5ab226bfe59888d888))
* **readme:** polish for launch (status, getting-started, platform, demo link) ([fade50b](https://github.com/VforVitorio/marginalia/commit/fade50b0750d260cb907924aca850b355f839094))
* **roadmap:** sprint + PR plan incl. LM Studio headless loading ([24fa0c2](https://github.com/VforVitorio/marginalia/commit/24fa0c27342c3a5e531fe3a3c835c73ae621d345))
* **roadmap:** sprint + PR plan with LM Studio headless-loading approach ([eed3bf3](https://github.com/VforVitorio/marginalia/commit/eed3bf302ba90ce3e064d0d1785234b10dbd789e))


### Miscellaneous Chores

* release marginalia 1.0.0 ([0ca1bbb](https://github.com/VforVitorio/marginalia/commit/0ca1bbbd5fa18fbcf0ae2347f6ad59e7c2b49d5e))
