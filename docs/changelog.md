# CHANGELOG

<!-- version list -->

## v4.8.0 (2025-12-20)

### Features

- **network**: Add mDNS/DNS-SD discovery for LIFX devices
  ([`f25987d`](https://github.com/Djelibeybi/lifx-async/commit/f25987d9357d395209dd7d346787671d85bf1371))


## v4.7.5 (2025-12-16)

### Bug Fixes

- **devices**: Override set_color in CeilingLight to track component state
  ([`0d20563`](https://github.com/Djelibeybi/lifx-async/commit/0d20563c170363229ab17620398283bd85ee7829))


## v4.7.4 (2025-12-16)

### Performance Improvements

- **devices**: Reduce get_all_tile_colors calls in CeilingLight
  ([`3936158`](https://github.com/Djelibeybi/lifx-async/commit/39361582856fcde57f30f052b8286f0bbb695f67))


## v4.7.3 (2025-12-16)

### Bug Fixes

- **devices**: Capture component colors before set_power turns off light
  ([`a99abee`](https://github.com/Djelibeybi/lifx-async/commit/a99abeeeb4f6cad1e49410204b8e7a567765b3ed))


## v4.7.2 (2025-12-16)

### Bug Fixes

- **api**: Close device connections in DeviceGroup context manager
  ([`054bfee`](https://github.com/Djelibeybi/lifx-async/commit/054bfee88e548d38c1e7c49277d3bb334b55adcc))

### Documentation

- **api**: Add dataclass documentation and improve navigation
  ([`c859c87`](https://github.com/Djelibeybi/lifx-async/commit/c859c8711335bdf5357412ccf4364075ce0df535))


## v4.7.1 (2025-12-13)

### Bug Fixes

- **devices**: Add length parameter to copy_frame_buffer()
  ([`6a74690`](https://github.com/Djelibeybi/lifx-async/commit/6a746904665d38545e534829c2c690a61e48da54))


## v4.7.0 (2025-12-13)

### Features

- **devices**: Add fast parameter to set_extended_color_zones()
  ([`0276fca`](https://github.com/Djelibeybi/lifx-async/commit/0276fca9b18e9f78441c843880ef52b4c79dac7b))


## v4.6.1 (2025-12-12)

### Bug Fixes

- **devices**: Check for power and brightness for Ceiling components
  ([`bd1b92f`](https://github.com/Djelibeybi/lifx-async/commit/bd1b92fb76c0e239c36dda09cca66035b527965a))


## v4.6.0 (2025-12-11)

### Features

- **devices**: Add CeilingLightState dataclass for ceiling component state
  ([`607f15c`](https://github.com/Djelibeybi/lifx-async/commit/607f15c3ed3508a883523ecee940959806d49400))


## v4.5.1 (2025-12-11)

### Bug Fixes

- **devices**: Export CeilingLight add add user guide and API documentation
  ([`10e0089`](https://github.com/Djelibeybi/lifx-async/commit/10e008983ffd8b233dd2427a4a4f64661c8f14bd))


## v4.5.0 (2025-12-08)

### Features

- **devices**: Add CeilingLight with independent uplight/downlight component control
  ([`95fc5a6`](https://github.com/Djelibeybi/lifx-async/commit/95fc5a68c598232f5c710ad5d67f3647ba89d720))


## v4.4.1 (2025-12-03)

### Bug Fixes

- **theme**: Prevent color displacement in multi-tile matrix theme application
  ([`ca936ec`](https://github.com/Djelibeybi/lifx-async/commit/ca936ec8df84fc42803182ae9898d243e017c5a3))


## v4.4.0 (2025-11-29)

### Features

- **devices**: Add factory pattern with automatic type detection and state management
  ([`4374248`](https://github.com/Djelibeybi/lifx-async/commit/4374248bb46cb5af1cf303866ad82b6692bb8932))


## v4.3.9 (2025-11-27)

### Bug Fixes

- **network**: Propagate timeout from request() to internal methods
  ([`b35ebea`](https://github.com/Djelibeybi/lifx-async/commit/b35ebea46120bfd4ad9ce149f5e25125d3694b30))


## v4.3.8 (2025-11-25)

### Bug Fixes

- **network**: Raise exception on StateUnhandled instead of returning False
  ([`5ca3e8a`](https://github.com/Djelibeybi/lifx-async/commit/5ca3e8abcde0ec0eefe77645aeb0a2e63b18418c))


## v4.3.7 (2025-11-25)

### Bug Fixes

- **devices**: Raise LifxUnsupportedCommandError on StateUnhandled responses
  ([`ec142cf`](https://github.com/Djelibeybi/lifx-async/commit/ec142cf0130847d65d4b9cd825575658936ef823))


## v4.3.6 (2025-11-25)

### Bug Fixes

- **network**: Return StateUnhandled packets instead of raising exception
  ([`f27e848`](https://github.com/Djelibeybi/lifx-async/commit/f27e84849656a84e7e120d66d1dba7bbabe18ed5))


## v4.3.5 (2025-11-22)

### Bug Fixes

- **devices**: Allow MatrixEffect without palette
  ([`fb31df5`](https://github.com/Djelibeybi/lifx-async/commit/fb31df51b1af9d8c7c2f573ec9619566b4f7393b))


## v4.3.4 (2025-11-22)

### Bug Fixes

- **network**: Exclude retry sleep time from timeout budget
  ([`312d7a7`](https://github.com/Djelibeybi/lifx-async/commit/312d7a7e2561de7d2bbf142c8a521daca31651bb))


## v4.3.3 (2025-11-22)

### Bug Fixes

- Give MatrixLight.get64() some default parameters
  ([`a69a49c`](https://github.com/Djelibeybi/lifx-async/commit/a69a49c93488c79c8c3be58a9304fd01b4b12231))

- **themes**: Apply theme colors to all zones via proper canvas interpolation
  ([`f1628c4`](https://github.com/Djelibeybi/lifx-async/commit/f1628c4a071d257d7db79a7945d1516c783d8d52))


## v4.3.2 (2025-11-22)

### Bug Fixes

- **effects**: Add name property to LIFXEffect and subclasses
  ([`deb8a54`](https://github.com/Djelibeybi/lifx-async/commit/deb8a54f674d2d4cd9b8dce519dc6ca8678e048a))


## v4.3.1 (2025-11-22)

### Bug Fixes

- Actually rename the matrix methods
  ([`061aaa7`](https://github.com/Djelibeybi/lifx-async/commit/061aaa7c1931b2fc606363d5acc14ec7fa1b039b))


## v4.3.0 (2025-11-22)

### Features

- **effects**: Unify effect enums and simplify API
  ([`df1c3c8`](https://github.com/Djelibeybi/lifx-async/commit/df1c3c8ba63dbf6cbfa5b973cdfe648c100a1371))


## v4.2.1 (2025-11-21)

### Bug Fixes

- Get_wifi_info now returns signal and rssi correctly
  ([`6db03b3`](https://github.com/Djelibeybi/lifx-async/commit/6db03b334a36de6faa1b9749f545f3775a01d7dd))


## v4.2.0 (2025-11-21)

### Documentation

- **api**: Remove obsolete reference to MessageBuilder
  ([`9847948`](https://github.com/Djelibeybi/lifx-async/commit/98479483d00c875e324d5a7dcd88bf08f11f73cb))

### Features

- **devices**: Add ambient light sensor support
  ([`75f0673`](https://github.com/Djelibeybi/lifx-async/commit/75f0673dc9b6e8bce30a5b5958215a600925357e))


## v4.1.0 (2025-11-20)

### Features

- **network**: Replace polling architecture with event-driven background receiver
  ([`9862eac`](https://github.com/Djelibeybi/lifx-async/commit/9862eac1eea162fa66bf19d277a3772de7c70db1))


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
