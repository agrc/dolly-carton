# Changelog

## [1.0.6](https://github.com/agrc/dolly-carton/compare/v1.0.5...v1.0.6) (2025-09-24)


### Bug Fixes

* get new gis connection when counting features in service ([cff15c1](https://github.com/agrc/dolly-carton/commit/cff15c1e99875c92c6b38c13553589b40afbcf49))

## [1.0.5](https://github.com/agrc/dolly-carton/compare/v1.0.4...v1.0.5) (2025-09-23)


### Bug Fixes

* disable cache when verifying feature counts after updating feature service ([29a7570](https://github.com/agrc/dolly-carton/commit/29a7570dcca8d637733a2ea3ccec42335e304f3c))
* use native logging in GCP ([9faef88](https://github.com/agrc/dolly-carton/commit/9faef888217378c52aa05e9aed945847fe0bcc12))

## [1.0.4](https://github.com/agrc/dolly-carton/compare/v1.0.3...v1.0.4) (2025-09-22)


### Features

* add AGOL item links to Slack summary report ([c0f5442](https://github.com/agrc/dolly-carton/commit/c0f5442b308162608f1a023940f293fd571acab2))
* make item_id parameter required in add_table methods ([4b417f3](https://github.com/agrc/dolly-carton/commit/4b417f3f065c29f94057d1a3dea48e93960542d5))


### Bug Fixes

* resolve Docker build SSL certificate issues in CI environments ([bebd4bd](https://github.com/agrc/dolly-carton/commit/bebd4bd2f52fc08724419fcfafd2905f64d4a713))


### Documentation

* Create GitHub Copilot instructions with agent testing restrictions and firewall guidance ([#26](https://github.com/agrc/dolly-carton/issues/26)) ([c3a442a](https://github.com/agrc/dolly-carton/commit/c3a442a2257e7a334a6f0241aa5876bcd1c8d19d))
* update copilot instructions to reflect resolved Docker build issues ([915e1a9](https://github.com/agrc/dolly-carton/commit/915e1a9f5b15cb0f41106aa9f66b7ff00b6a4db4))

## [1.0.3](https://github.com/agrc/dolly-carton/compare/v1.0.2...v1.0.3) (2025-08-26)


### Features

* switch to table-level change detection ([eef712c](https://github.com/agrc/dolly-carton/commit/eef712c0a69bd8bfd106dbfacc5f733cf275c559)), closes [#7](https://github.com/agrc/dolly-carton/issues/7)


### Bug Fixes

* update table hashes after each successful operation ([007293d](https://github.com/agrc/dolly-carton/commit/007293d9ee4be81d7a362fce2a6043a7a1e32da9))

## [1.0.2](https://github.com/agrc/dolly-carton/compare/v1.0.1...v1.0.2) (2025-08-21)


### Bug Fixes

* bump run job memory ([14556ad](https://github.com/agrc/dolly-carton/commit/14556ad8b2181c66883164cc79247ec119a0c4ef))

## [1.0.1](https://github.com/agrc/dolly-carton/compare/v1.0.0...v1.0.1) (2025-08-20)


### Bug Fixes

* skip updated tables not hosted by UGRC ([8a503f3](https://github.com/agrc/dolly-carton/commit/8a503f3a574243e11d7d0535859c4399e437e463))

## 1.0.0 (2025-08-14)


### Features

* add cleanup command for development feature services ([524feb5](https://github.com/agrc/dolly-carton/commit/524feb530051e9c0dc8c9024fa3fe6d6f1968409))
* add duration logging to main process ([1ceccb7](https://github.com/agrc/dolly-carton/commit/1ceccb73cea7a089700e7980d0122238a7bd9a79))
* add global errors to summary report ([6f63e6e](https://github.com/agrc/dolly-carton/commit/6f63e6e827563384793ad2eff259c29299981efa)), closes [#9](https://github.com/agrc/dolly-carton/issues/9)
* add optional tables CLI param ([e11a5c3](https://github.com/agrc/dolly-carton/commit/e11a5c347452ad7223d9323df2b2b8baee7eb84e)), closes [#3](https://github.com/agrc/dolly-carton/issues/3)
* add slack message posting ([a011afc](https://github.com/agrc/dolly-carton/commit/a011afc6b64cc2791fcb72baa3602018c6776e88)), closes [#2](https://github.com/agrc/dolly-carton/issues/2)
* add stack trace to error logs where it makes sense ([1fd4d0a](https://github.com/agrc/dolly-carton/commit/1fd4d0a6347f31e929ab1d1a34779f0a96e5fe33))
* add support for coded-value and range domains ([a1fa5d9](https://github.com/agrc/dolly-carton/commit/a1fa5d9d8fbce0566fa5ae36a02fe702e5b2fc8d)), closes [#4](https://github.com/agrc/dolly-carton/issues/4)
* add tests for get_service_from_title and enhance to handle additional edge cases ([6e4118e](https://github.com/agrc/dolly-carton/commit/6e4118e722954c0857ce97a731d6935eae1133ac))
* handle max character limit for slack blocks ([39aa782](https://github.com/agrc/dolly-carton/commit/39aa78252a3fe7e753eb288c1c590dae4cc89180))
* implement state management via firestore in prod ([78911c2](https://github.com/agrc/dolly-carton/commit/78911c2b9c3bef943ebf51eb59a6b682d7f74fd4))
* implement summary report in logs ([8d3fb68](https://github.com/agrc/dolly-carton/commit/8d3fb68366bfa5b2baaa697d6d01acd73127a7ad)), closes [#2](https://github.com/agrc/dolly-carton/issues/2)
* mark new feature services as authoritative in prod ([db5b837](https://github.com/agrc/dolly-carton/commit/db5b837bee94d64db1349b799ffc44dd1fe1720e))


### Bug Fixes

* add test tag for dev environment fgdb uploads ([7957d3f](https://github.com/agrc/dolly-carton/commit/7957d3f86a3b2554936aaef787e5f641983db270))
* don't cleanup .gitkeep file ([3087546](https://github.com/agrc/dolly-carton/commit/30875465a9bb3c5de7532f13d8b43a902f4b50d0))
* execute dolly process when dockerfile starts in prod ([e5c0f09](https://github.com/agrc/dolly-carton/commit/e5c0f095e4d5abb59ef11696d7b0ba60fceef3a4))
* fix agol items lookup query field order ([060175e](https://github.com/agrc/dolly-carton/commit/060175e17841c95a2e25398a007f33e496312a3b))
* fix fgdb and table/layer names ([1be0035](https://github.com/agrc/dolly-carton/commit/1be0035b23e7c484b1301bfb9501d7055deda6a4))
* fix skip cleaning up .gitkeep file ([d7c018b](https://github.com/agrc/dolly-carton/commit/d7c018b593fecbbc0c2fad52953b856c6df73673))
* ignore casing for geometry type values ([366cc33](https://github.com/agrc/dolly-carton/commit/366cc33a7b3a06427261a2008c6e2143588e4daf))
* include dev_mocks.json in package data ([f98c895](https://github.com/agrc/dolly-carton/commit/f98c89559b7f09cbf3d78b171cfa13b6a1f185d5))
* local secrets path ([b10c175](https://github.com/agrc/dolly-carton/commit/b10c175a31bfbf899d84a0b8c0067e7818407e96))
* more consistent table naming within FGDBs ([4b745ce](https://github.com/agrc/dolly-carton/commit/4b745ce14f04112731440343d22c9b7657c411d2))
* more durable update query ([102ce8d](https://github.com/agrc/dolly-carton/commit/102ce8d13f6928f44a55b7c3919a2f52ef7e7d37))
* prevent exceptions from short-circuting the entire process ([2b86a3d](https://github.com/agrc/dolly-carton/commit/2b86a3d93223763b79932946ed6314cf6838096f))
* raise on unknown geometry types ([186e54f](https://github.com/agrc/dolly-carton/commit/186e54f2a1f946684ceb8e6c3d3af95ffac078a1))
* remove and replace tags that are removed by auditor ([659530e](https://github.com/agrc/dolly-carton/commit/659530e5120c43b2455667e7094c2cd668a47828))
* replace get method with direct access ([9f631cc](https://github.com/agrc/dolly-carton/commit/9f631cc216c03fd4c1c22c18008c8ef4a8df3625))
* secrets path in gcp ([b702106](https://github.com/agrc/dolly-carton/commit/b702106e2ed46eaefe04cb92408e2d50c47e48f7))
* set output coordinate system ([71df682](https://github.com/agrc/dolly-carton/commit/71df682d40b8c19de73434583bc4835b6baf52dc))
* simplify error reporting by only showing counts if there are items ([94711e1](https://github.com/agrc/dolly-carton/commit/94711e129a9fdb1aecc7dd37fc23b1c5816c3bf4))
* simplify logging and remove cloud logging package ([297f670](https://github.com/agrc/dolly-carton/commit/297f670ba40ca23729897c53dbf0365a3fc1b1af))
* summary report refinements ([94b931b](https://github.com/agrc/dolly-carton/commit/94b931bc51eb10577964e8752c3de9732dfc33e1))
* throw if APP_ENVIRONMENT is not defined ([165107d](https://github.com/agrc/dolly-carton/commit/165107dffc6a725a1aa38534df740dd06949bb31))
* throw key errors if there are missing secrets ([ead6033](https://github.com/agrc/dolly-carton/commit/ead6033b49aafa1151b075d74192c25ca22b4fd2))
* use open-sgid convention for service and table name ([c1aab3f](https://github.com/agrc/dolly-carton/commit/c1aab3f7ae447feda7536ab35347612879bcba3f))


### Dependencies

* **docker:** bump osgeo/gdal in the docker-dependencies group ([70c8f12](https://github.com/agrc/dolly-carton/commit/70c8f12b563a8d3614a8b2c98742c219ae269870))


### Documentation

* add note about how this project is triggered ([42af62e](https://github.com/agrc/dolly-carton/commit/42af62eccab681a325c2fd0587837ea069042510))
* flesh out more complete readme ([f48dbaf](https://github.com/agrc/dolly-carton/commit/f48dbaf47f8157af75a53a028020942dbe00db85))
