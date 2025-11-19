# CHANGELOG

<!-- version list -->

## v4.0.2 (2025-11-19)

### Bug Fixes

- Product registry generation
  ([`2742a18`](https://github.com/Djelibeybi/lifx-async/commit/2742a184f805ba3863c376670c323f9d078766f3))


## v4.0.1 (2025-11-18)

### Bug Fixes

- **devices**: Prevent connection leaks in temporary device queries
  ([`0ee8d0c`](https://github.com/Djelibeybi/lifx-async/commit/0ee8d0cc211aa73eac32ebbe6516aa70e7158f29))


## v4.0.0 (2025-11-18)

### Features

- **devices**: Replace TileDevice with MatrixLight implementation
  ([`1b8bc39`](https://github.com/Djelibeybi/lifx-async/commit/1b8bc397495443ad857c96052de2694a4b350011))

### Breaking Changes

- **devices**: TileDevice class has been removed and replaced with MatrixLight


## v3.1.0 (2025-11-17)

### Features

- Remove connection pool in favor of lazy device-owned connections
  ([`11b3cb2`](https://github.com/Djelibeybi/lifx-async/commit/11b3cb24f51f3066cacc94d5ec2b2adb1bdf5ce1))


## v3.0.1 (2025-11-17)

### Bug Fixes

- Get_power() now returns an integer value not a boolean
  ([`3644bb9`](https://github.com/Djelibeybi/lifx-async/commit/3644bb9baf56593a8f4dceaac19689b3a0152384))


## v3.0.0 (2025-11-16)

### Features

- Convert discovery methods to async generators
  ([`0d41880`](https://github.com/Djelibeybi/lifx-async/commit/0d418800729b45869057b1f4dd86b4ceb7ef2fbe))

- Replace event-based request/response with async generators
  ([`fa50734`](https://github.com/Djelibeybi/lifx-async/commit/fa50734057d40ac968f2edb4ff7d6634fe5be798))

### Breaking Changes

- Internal connection architecture completely refactored


## v2.2.2 (2025-11-14)

### Bug Fixes

- **devices**: Replace hardcoded timeout and retry values with constants
  ([`989afe2`](https://github.com/Djelibeybi/lifx-async/commit/989afe20f116d287215ec7bf5e78baa766a5ac63))


## v2.2.1 (2025-11-14)

### Bug Fixes

- **network**: Resolve race condition in concurrent request handling
  ([`8bb7bc6`](https://github.com/Djelibeybi/lifx-async/commit/8bb7bc68bf1c8baad0c9d96ba3034e40176f50e3))


## v2.2.0 (2025-11-14)

### Features

- **network**: Add jitter to backoff and consolidate retry logic
  ([`0dfb1a2`](https://github.com/Djelibeybi/lifx-async/commit/0dfb1a2847330270c635f91c9b63577c7aad2598))


## v2.1.0 (2025-11-14)

### Features

- Add mac_address property to Device class
  ([`bd101a0`](https://github.com/Djelibeybi/lifx-async/commit/bd101a0af3eec021304d39de699e8ea0e59934c1))


## v2.0.0 (2025-11-14)

### Refactoring

- Simplify state caching and remove TTL system
  ([`fd15587`](https://github.com/Djelibeybi/lifx-async/commit/fd155873e9d9b56cdfa38cae3ec9bbdc9bfe283b))


## v1.3.1 (2025-11-12)

### Bug Fixes

- Add Theme, ThemeLibrary, get_theme to main lifx package exports
  ([`6b41bb8`](https://github.com/Djelibeybi/lifx-async/commit/6b41bb8b052a0447d5a667681eb3bedcfd1e7218))

### Documentation

- Add mkdocs-llmstxt to create llms.txt and llms-full.txt
  ([`4dd378c`](https://github.com/Djelibeybi/lifx-async/commit/4dd378cacf4e9904dc64e2e59936f4a9e325fc47))

- Remove effects release notes
  ([`2fdabc0`](https://github.com/Djelibeybi/lifx-async/commit/2fdabc04a3abba507bbee3f93721a8814296e269))


## v1.3.0 (2025-11-10)

### Features

- Add software effects
  ([`be768fb`](https://github.com/Djelibeybi/lifx-async/commit/be768fbb4c2984646da4a0ee954b36930ca6261d))


## v1.2.1 (2025-11-08)

### Bug Fixes

- Implement tile effect parameters as local quirk
  ([`f4ada9b`](https://github.com/Djelibeybi/lifx-async/commit/f4ada9b13f63060459ed80b4961eb9339559a8ea))


## v1.2.0 (2025-11-07)

### Features

- Add theme support
  ([`82477cd`](https://github.com/Djelibeybi/lifx-async/commit/82477cd078004c37ad5b538ed8a261ac5fbece78))


## v1.1.3 (2025-11-06)

### Performance Improvements

- Reduce network traffic when updating individual color values
  ([`679b717`](https://github.com/Djelibeybi/lifx-async/commit/679b7176abd7634644e9395281ffa28dde26ebec))


## v1.1.2 (2025-11-05)

### Bug Fixes

- Dummy fix to trigger semantic release
  ([`86ad8b4`](https://github.com/Djelibeybi/lifx-async/commit/86ad8b442138216974bb65dac130d6ff54bd65a5))


## v1.1.1 (2025-11-05)

### Bug Fixes

- Dummy fix to trigger semantic release
  ([`12786b5`](https://github.com/Djelibeybi/lifx-async/commit/12786b54e76cd51c023d64f7a23fc963252421f8))


## v1.1.0 (2025-11-05)

### Features

- Replace cache TTL system with timestamped state attributes
  ([`5ae147a`](https://github.com/Djelibeybi/lifx-async/commit/5ae147a8c1cbbdc0244c9316708bd381269375db))


## v1.0.0 (2025-11-04)

- Initial Release
