# CHANGELOG

<!-- version list -->

## v5.6.0 (2026-07-18)

### Features

- Wire reliability improvements (v1.1)
  ([`d99a501`](https://github.com/Djelibeybi/lifx-async/commit/d99a501b2f896a596e45e71b57e1e06e1d3fa15c))


## v5.5.1 (2026-06-14)

### Bug Fixes

- **ceiling**: Compare stored state at uint16 wire granularity
  ([`08b7e8d`](https://github.com/Djelibeybi/lifx-async/commit/08b7e8d9c23708b10aa2ebde27e7765a3f487dd1))

- **color**: Expose raw HSBK values instead of rounded ones
  ([`80b0b2f`](https://github.com/Djelibeybi/lifx-async/commit/80b0b2f3a0289b7c635461dd5ae3b53cb8ca8f19))

- **color**: Stop rounding computed lerp/average outputs
  ([`515dd91`](https://github.com/Djelibeybi/lifx-async/commit/515dd91d018ee5481602ee0ad9b270e0fe1eef8f))


## v5.5.0 (2026-06-13)

### Bug Fixes

- **01**: CR-01 drop size-invalid datagrams instead of aborting discovery
  ([`b33fde1`](https://github.com/Djelibeybi/lifx-async/commit/b33fde1464e73422cc260e649a75dfd77d79ffe8))

- **01**: Finish review-fix pass — WR-03/WR-04/WR-05
  ([`21c2b35`](https://github.com/Djelibeybi/lifx-async/commit/21c2b35e19f4c331c784af50ec655f36e35cdd8c))

- **01**: IN-01 remove no-cover pragma from exit-save except clause
  ([`282900c`](https://github.com/Djelibeybi/lifx-async/commit/282900c2e331309c77b160292c619efc1339e543))

- **01**: IN-02 run exit-save via asyncio.to_thread (D-01 revised)
  ([`0e46531`](https://github.com/Djelibeybi/lifx-async/commit/0e4653108c016cf40fb0fe445933bab51d3c2a8d))

- **01**: IN-03 preserve port, timeout and max_retries in from_ip
  ([`fa5da87`](https://github.com/Djelibeybi/lifx-async/commit/fa5da878025f8aed812b0a5ba0965b54a6bc8d3f))

- **01**: Tolerate unknown DeviceService values from real hardware
  ([`0cb5dc6`](https://github.com/Djelibeybi/lifx-async/commit/0cb5dc638e74ffe7c76ac6d31df66b99e6e60165))

- **01**: WR-01 merge on-disk device entry instead of replacing on save
  ([`a176243`](https://github.com/Djelibeybi/lifx-async/commit/a176243751cc2728730f9a130d4617cd8740bf59))

- **01**: WR-01 reject all-zeros broadcast target in serial guard
  ([`76b00ef`](https://github.com/Djelibeybi/lifx-async/commit/76b00efd5797b588254d40929651acd30e6a456d))

- **01**: WR-02 align mDNS idle-reset semantics with D-04
  ([`74928f8`](https://github.com/Djelibeybi/lifx-async/commit/74928f82e20e60ea7721c143a7750a5e3e30b47c))

- **01**: WR-02 assert state payload content in save-on-exit test
  ([`3c1c646`](https://github.com/Djelibeybi/lifx-async/commit/3c1c646c1ab8d1814457eb4dfce656e84842c5f6))

- **01**: WR-03 write state file atomically via temp file and os.replace
  ([`fde7b20`](https://github.com/Djelibeybi/lifx-async/commit/fde7b201b1e239b2b6af98542c24e42367b10176))

- **devices**: Guarantee ceiling connection cleanup if save is cancelled
  ([`6c5933d`](https://github.com/Djelibeybi/lifx-async/commit/6c5933d426fb8b8f98d5b1822656491434f813ac))

- **discovery**: Reject non-zero target padding in the serial guard
  ([`415006a`](https://github.com/Djelibeybi/lifx-async/commit/415006a5bde8988dedad775e64095cfc63c02e93))

### Documentation

- Add Phase 1 — unify duplicated discovery loops
  ([`426f018`](https://github.com/Djelibeybi/lifx-async/commit/426f01802d0802d40796e4b9619b45fb09de46de))

- Create roadmap (1 phase)
  ([`c79fa7c`](https://github.com/Djelibeybi/lifx-async/commit/c79fa7c8a6e0d586280b966a7741ca3caaf2d173))

- Define v1 requirements
  ([`496ee75`](https://github.com/Djelibeybi/lifx-async/commit/496ee75f417ffd719bf91a06fc568527c0dd1147))

- Initialize project
  ([`31ec39f`](https://github.com/Djelibeybi/lifx-async/commit/31ec39f80c64f811de49c84a1ca9086aedb01eb8))

- Map existing codebase
  ([`ee7b4e0`](https://github.com/Djelibeybi/lifx-async/commit/ee7b4e079d074e665552047159ead62d9040098a))

- **01**: Add code review fix report
  ([`03aa5b6`](https://github.com/Djelibeybi/lifx-async/commit/03aa5b6136e3220425831036a89b790d172f058a))

- **01**: Add code review fix report
  ([`a876703`](https://github.com/Djelibeybi/lifx-async/commit/a8767032b5c852c1bda377f9283810e0b554ae74))

- **01**: Add code review report
  ([`b9d7b8f`](https://github.com/Djelibeybi/lifx-async/commit/b9d7b8feda9c2601b102023ce85ac2705d7a2497))

- **01**: Add code review report
  ([`48bfa88`](https://github.com/Djelibeybi/lifx-async/commit/48bfa88fec2ddd5febcd399a5f788a2a91f6ed61))

- **01**: Capture phase context
  ([`d856de1`](https://github.com/Djelibeybi/lifx-async/commit/d856de1d7d09f2793e52af2a3b5e501d4eba7f9b))

- **01**: Capture phase context
  ([`20e0252`](https://github.com/Djelibeybi/lifx-async/commit/20e02527626c70782968c9c183d1c61caf10c02a))

- **01**: Create phase plan
  ([`052253b`](https://github.com/Djelibeybi/lifx-async/commit/052253b55fe1572f1555099c84a25447c13ce014))

- **01**: Create phase plan
  ([`1b14726`](https://github.com/Djelibeybi/lifx-async/commit/1b14726bc0d3f1156b3d0444f46b69e81c9daeff))

- **01**: Finalise phase plan artifacts
  ([`8fbb139`](https://github.com/Djelibeybi/lifx-async/commit/8fbb139de5a7f3d33c35a2f7db04ab4c5385d0ae))

- **01**: Mark Unify-discovery-loops phase complete & verified
  ([`0109677`](https://github.com/Djelibeybi/lifx-async/commit/010967797649dd96a2412c411399c43fc157ca4d))

- **01**: Record D-01 revision and final code review fix report
  ([`086339f`](https://github.com/Djelibeybi/lifx-async/commit/086339f9a1bec6cd539e5da6b8d1d4bfe9058efb))

- **01**: Research ceiling save-on-exit phase
  ([`7456f22`](https://github.com/Djelibeybi/lifx-async/commit/7456f22dafee7cdae98ffb4663f06829ba782bc5))

- **01-01**: Complete ceiling-save-on-exit plan
  ([`488dff5`](https://github.com/Djelibeybi/lifx-async/commit/488dff596cd45b2f57bc699c1e6a2d807ae8e864))

- **01-01**: Complete IdleDeadline plan
  ([`5748c49`](https://github.com/Djelibeybi/lifx-async/commit/5748c49625267dba8aea978255aa2efc0aad03a5))

- **01-02**: Complete thin-discover-devices-wrapper plan
  ([`690fd20`](https://github.com/Djelibeybi/lifx-async/commit/690fd207a77d0712fbbe7320ebd4e83698fb411b))

- **01-03**: Complete mDNS IdleDeadline adoption plan
  ([`74aa472`](https://github.com/Djelibeybi/lifx-async/commit/74aa4728b8fbb37de2443464624c3dfec9b008a0))

- **01-04**: Complete deprecate-receive-many plan
  ([`4345760`](https://github.com/Djelibeybi/lifx-async/commit/4345760e8151be97c88450b40157e45d4bb815bf))

- **01-05**: Complete discovery error test gap plan
  ([`e23cec0`](https://github.com/Djelibeybi/lifx-async/commit/e23cec0e646180ff7f5468ebcc657f222f8b994c))

- **phase-1**: Add security threat verification
  ([`dbff129`](https://github.com/Djelibeybi/lifx-async/commit/dbff129c7084af7dfec1162bed05fb09db40dd47))

- **phase-1**: Add security threat verification
  ([`608929d`](https://github.com/Djelibeybi/lifx-async/commit/608929d8028b5032425e3dde87603c3e70843576))

- **phase-1**: Add validation strategy
  ([`f310ebf`](https://github.com/Djelibeybi/lifx-async/commit/f310ebf35dd3fc2aa466954410426d2f552ffd46))

- **phase-1**: Add validation strategy
  ([`b85ea2a`](https://github.com/Djelibeybi/lifx-async/commit/b85ea2ae7dab4683b6cc9170270bd6b19b2e0b76))

- **phase-1**: Complete phase execution
  ([`b941e14`](https://github.com/Djelibeybi/lifx-async/commit/b941e14f239301027dfbafd003ac471af3c913aa))

- **phase-1**: Create phase plans for discovery loop unification
  ([`be081e5`](https://github.com/Djelibeybi/lifx-async/commit/be081e5cbc960f0726c1a5640fbd609fdd747b57))

- **phase-1**: Evolve PROJECT.md after phase completion
  ([`376bf9f`](https://github.com/Djelibeybi/lifx-async/commit/376bf9fa99e34026bfa11e32d34443296ef569c3))

- **phase-1**: Research unify-duplicated-discovery-loops
  ([`e67c946`](https://github.com/Djelibeybi/lifx-async/commit/e67c9460735606246bb8fd02ed786551d8919827))

- **state**: Record phase 1 context session
  ([`262f8d3`](https://github.com/Djelibeybi/lifx-async/commit/262f8d38fce4a3a092a6b3385a11a983f289e2c1))

- **state**: Record phase 1 context session
  ([`1aa4b2f`](https://github.com/Djelibeybi/lifx-async/commit/1aa4b2f9cb8ba17e17e1074d44d81978b2ee226d))

- **v1.0**: Add milestone audit (passed 7/7) and close out validation map
  ([`c99e9ad`](https://github.com/Djelibeybi/lifx-async/commit/c99e9adcd523ebd38d37aeb0c9742b914ff4a1cb))

### Features

- **01-01**: Add IdleDeadline unit tests in test_network/test_utils.py
  ([`40f9578`](https://github.com/Djelibeybi/lifx-async/commit/40f9578371edacbcbae8597818cd40ac95c01ddb))

- **01-01**: Implement CeilingLight.__aexit__ to save state on exit (GREEN)
  ([`272d79b`](https://github.com/Djelibeybi/lifx-async/commit/272d79bf822ce5b500b35367145887a782150824))

- **01-01**: Implement IdleDeadline in network/utils.py
  ([`28bb3d6`](https://github.com/Djelibeybi/lifx-async/commit/28bb3d67b15135a83a3dfedc0d152c3c416d7d08))

- **01-04**: Deprecate UdpTransport.receive_many with DeprecationWarning
  ([`bc6c95d`](https://github.com/Djelibeybi/lifx-async/commit/bc6c95d7ba9b2119039f0afd04a872a5839a189d))


## v5.4.9 (2026-05-21)

### Bug Fixes

- Add new products to the LIFX product list
  ([`f0e31c9`](https://github.com/Djelibeybi/lifx-async/commit/f0e31c909c65e7db4491fe6704f38e679ea2b017))


## v5.4.8 (2026-04-17)

### Bug Fixes

- Raise OSError in create_mdns_socket and handle exit in main()
  ([`5d036be`](https://github.com/Djelibeybi/lifx-async/commit/5d036beb85a4e4184ebe9fe43a9f59268e10fecf))

### Documentation

- **planning**: Address code review nitpicks in codebase docs
  ([`5609034`](https://github.com/Djelibeybi/lifx-async/commit/56090345365bba68f873ede2ac08d8584bac58d2))


## v5.4.7 (2026-04-17)

### Bug Fixes

- Ensure CeilingLightState exists before caliing set_power
  ([`48cef24`](https://github.com/Djelibeybi/lifx-async/commit/48cef2425cfdea57c06ecb04743229facfc41911))


## v5.4.6 (2026-03-22)

### Bug Fixes

- Add MIT license header to effects ported from pkivolowitz/lifx
  ([`5830c98`](https://github.com/Djelibeybi/lifx-async/commit/5830c98b460db4b5fb62f684c06a12190b4b496e))


## v5.4.5 (2026-03-22)

### Bug Fixes

- Device.connect() now returns Light for CCT and brightness-only products
  ([`df6d787`](https://github.com/Djelibeybi/lifx-async/commit/df6d7877593cabf77daa5b2871281e5b8558581c))

- Patch correct target for is_ceiling_product in tests
  ([`666a406`](https://github.com/Djelibeybi/lifx-async/commit/666a4069dab44ecdc21bf23fee995f79524e9c16))


## v5.4.4 (2026-03-21)

### Bug Fixes

- Set a default value for duration_seconds for set_hev_cycle
  ([`f7fc708`](https://github.com/Djelibeybi/lifx-async/commit/f7fc708d37964fb8b95e5a63096925ff539badfa))

### Documentation

- Update docstring to provide more detail on hev config
  ([`02de0f0`](https://github.com/Djelibeybi/lifx-async/commit/02de0f07463b77b89982afa8e50a65f58d6519b7))


## v5.4.3 (2026-03-21)

### Bug Fixes

- Defer is_on flag updates and add power-aware factory initialisation
  ([`3db28a3`](https://github.com/Djelibeybi/lifx-async/commit/3db28a3f9c69b4d767e67d09843282a3cfdf1d89))

- Defer is_on flags until after power-on and sync public fields on power-off
  ([`b412e40`](https://github.com/Djelibeybi/lifx-async/commit/b412e4069a0b9ba60962d8c537171a9616015b45))

- Defer stored state updates until after I/O succeeds in turn-off methods
  ([`01588ec`](https://github.com/Djelibeybi/lifx-async/commit/01588ec847271094d32dce576de0531af498292d))

- Harden CeilingLightState against aliased mutations and stale snapshots
  ([`73a7275`](https://github.com/Djelibeybi/lifx-async/commit/73a727515f03496f5e8cce7338bd94688e37dc8f))

- Move ceiling component state to CeilingLightState dataclass
  ([`06372b9`](https://github.com/Djelibeybi/lifx-async/commit/06372b9c89e483dfb94cfdaed6b298f7f7ac0bc7))

- Resolve remaining CodeRabbit review comments
  ([`cd450a8`](https://github.com/Djelibeybi/lifx-async/commit/cd450a8e5337fc452fb864dbc2dc6e6c07cfbca4))

- Return defensive copy of stored downlight colours
  ([`2575889`](https://github.com/Djelibeybi/lifx-async/commit/2575889ddaccf4d38be9aab7803a67c8ab828152))

- Sync ceiling component is_on state in getter methods
  ([`8b83f35`](https://github.com/Djelibeybi/lifx-async/commit/8b83f35a2e0035a0af301d4cb8774216c87b6533))

- Sync public CeilingLightState fields in all mutators and getters
  ([`1eac576`](https://github.com/Djelibeybi/lifx-async/commit/1eac576ace714420f190b1df1c756ad6d2a73b1c))


## v5.4.2 (2026-03-21)

### Bug Fixes

- Guard against ValueError if signal is negative or 0
  ([`a1085c6`](https://github.com/Djelibeybi/lifx-async/commit/a1085c66e03f06546ad23d5529277bcc616bcc6f))


## v5.4.1 (2026-03-19)

### Bug Fixes

- Asyncio and import pattern cleanup (review-critical_20260318)
  ([`07fed68`](https://github.com/Djelibeybi/lifx-async/commit/07fed681f42b8d413a944b5ba111ba6de3025766))

- Protocol correctness and code quality fixes (review-critical_20260318)
  ([`e3276bf`](https://github.com/Djelibeybi/lifx-async/commit/e3276bf1bd0e7f52f884e96d9a990704df4955f8))

- **animation**: Validate HSBK input length in update_colors()
  ([`94b232f`](https://github.com/Djelibeybi/lifx-async/commit/94b232f66646830ea933aa3c03ed22c7dc90a014))

- **codecov**: Allow coverage uploads from failing CI runs
  ([`1843d19`](https://github.com/Djelibeybi/lifx-async/commit/1843d195037eb77233ce521e1798b67410d6f9f5))

- **color**: Preserve full precision in with_* helpers
  ([`35f6229`](https://github.com/Djelibeybi/lifx-async/commit/35f62293a67c7337a5bb0a1f681fd382ed6e20a7))

- **effects**: Clear _last_generated_hsbk unconditionally after iteration
  ([`b6bf2bb`](https://github.com/Djelibeybi/lifx-async/commit/b6bf2bb6b64d9a059b5d0d1dcc5bbb89d954370b))

- **test**: Make source ID rejection test deterministic
  ([`3d93826`](https://github.com/Djelibeybi/lifx-async/commit/3d93826458ec4d7e7a3ac2f5d5d860ed32dea27f))

- **test**: Move noqa ARG001 to the actually unused config parameter
  ([`2c068bc`](https://github.com/Djelibeybi/lifx-async/commit/2c068bc2cf91feae62755813fe2c829cf3a705e0))

- **transport**: Rate-limit QueueFull warning to prevent log flooding
  ([`82378af`](https://github.com/Djelibeybi/lifx-async/commit/82378afbda25f35354bc60c834baf32389c55961))

### Documentation

- Fix remaining int RGB references and clean up long float literals
  ([`5880ad2`](https://github.com/Djelibeybi/lifx-async/commit/5880ad29be9adda8d8d6534400f2539f0aa5dfe9))

- Streamline CLAUDE.md from 907 to 381 lines
  ([`59769e8`](https://github.com/Djelibeybi/lifx-async/commit/59769e86e1031949491fd151ef3634b06ebd8980))

- **animator**: Fix stale comment about source ID allocation
  ([`6336427`](https://github.com/Djelibeybi/lifx-async/commit/63364276975ed510e4a3176079268746e1653e7f))

- **effects**: Consolidate effects content into user-guide (Phase 1)
  ([`71a5684`](https://github.com/Djelibeybi/lifx-async/commit/71a56848953ba13b6684faf4a8f35d0c7987053c))

- **effects**: Document _last_frames limitation for protocol-direct path
  ([`257febf`](https://github.com/Djelibeybi/lifx-async/commit/257febf9158c595b3e4c68eb8fc0cd5b13e02098))

- **effects**: Update FrameEffect docstrings for generate_protocol_frame
  ([`8e52cee`](https://github.com/Djelibeybi/lifx-async/commit/8e52ceecccf52506563a61f6fddbebb2f65d858d))

- **mkdocs**: Fix all documentation correctness issues
  ([`7a061e4`](https://github.com/Djelibeybi/lifx-async/commit/7a061e4c0776b2eecd362ed8dd8f56098df65b30))

- **nav**: Update navigation and add progressive disclosure links (Phase 4)
  ([`42caf99`](https://github.com/Djelibeybi/lifx-async/commit/42caf994f545641fa6140b6a872d86795eb47ce7))

- **plan**: Fix task list checkbox spacing at line 25-26
  ([`2f9e5e9`](https://github.com/Djelibeybi/lifx-async/commit/2f9e5e91a62da9ccdef5638dba784ccd9fe67d85))

- **plan**: Fix task list checkbox spacing at line 39-40
  ([`cb09448`](https://github.com/Djelibeybi/lifx-async/commit/cb09448a1bafb8f633e7a06f8f8918b45afc3610))

- **plan**: Fix task list checkbox spacing at line 54-55
  ([`5b3dd32`](https://github.com/Djelibeybi/lifx-async/commit/5b3dd32279066eef694d664b3f3f0b82957ce9e0))

- **plan**: Fix task list checkbox spacing at line 70-71
  ([`c0990aa`](https://github.com/Djelibeybi/lifx-async/commit/c0990aa67bc50f5456d2f9a71cbba581a38835be))

- **plan**: Fix task list checkbox spacing at line 75-79
  ([`70440a2`](https://github.com/Djelibeybi/lifx-async/commit/70440a255c13f73a73a0752f6e44526fe04c018b))

- **source**: Fix misleading docstrings in base.py, api.py, exceptions.py
  ([`901d4aa`](https://github.com/Djelibeybi/lifx-async/commit/901d4aad0910c7a84bffeee13056464148719000))

- **structure**: Relocate misplaced content and fix orphaned links (Phase 3)
  ([`25f2186`](https://github.com/Djelibeybi/lifx-async/commit/25f21864d4df28491e1dfdcf5678318d473edf07))

- **tests**: Fix misleading comment in idle timeout test
  ([`b76a418`](https://github.com/Djelibeybi/lifx-async/commit/b76a418d513b51c0b3de21a742303744c902e4b5))

- **themes,animation**: Deduplicate themes and animation content (Phase 2)
  ([`c489bc7`](https://github.com/Djelibeybi/lifx-async/commit/c489bc7cdb38eb2c64010f61cdd038e08c3c0a10))

### Performance Improvements

- **animation**: Avoid slice allocation in update_colors() hot loop
  ([`b3152e1`](https://github.com/Djelibeybi/lifx-async/commit/b3152e170f469cb814fc9f3ec24768e37b9b141b))

- **animation**: Use pre-compiled struct.Struct for HSBK writes
  ([`1b54956`](https://github.com/Djelibeybi/lifx-async/commit/1b5495635abb792f2884158507bfc07cf4546ece))

- **aurora**: Add direct generate_protocol_frame() override (review-perf_20260318)
  ([`a01f289`](https://github.com/Djelibeybi/lifx-async/commit/a01f2890521f7080ffbbf87e2d25dcfa8f3fdde3))

- **effects**: Add generate_protocol_frame() to FrameEffect (review-perf_20260318)
  ([`24bb03c`](https://github.com/Djelibeybi/lifx-async/commit/24bb03cc42f4ab3ab64a63207068f061f19a2de9))

- **framebuffer**: Pre-compute canvas-to-device LUT at init time (review-perf_20260318)
  ([`3b28194`](https://github.com/Djelibeybi/lifx-async/commit/3b2819454f636eeec327cedf79d40640003e1d6e))

- **packets**: Replace flat list building with direct struct.pack_into (review-perf_20260318)
  ([`ced40eb`](https://github.com/Djelibeybi/lifx-async/commit/ced40eb96d8c675bf33dcad99a0fb4caf39171c5))

- **protocol**: Guard asdict() in Packet.unpack() behind debug check (review-perf_20260318)
  ([`44617c1`](https://github.com/Djelibeybi/lifx-async/commit/44617c141674e86603fc4c82b512b8a3aa909a22))


## v5.4.0 (2026-03-18)

### Documentation

- **effects**: Add animated GIFs and effects gallery page
  ([`fbcaadc`](https://github.com/Djelibeybi/lifx-async/commit/fbcaadcd93d03b03cacd154857a4b6de4c34bf01))

- **effects**: Add documentation for 18 effects adapted from pkivolowitz/lifx
  ([`a4f47be`](https://github.com/Djelibeybi/lifx-async/commit/a4f47be11646da48b91a2b879c698f43aa7ca979))

### Features

- **examples**: Add effects demo script with device-type-aware selection
  ([`be36b95`](https://github.com/Djelibeybi/lifx-async/commit/be36b956eac3f5fc8de02da3f175d49de367da12))


## v5.3.0 (2026-03-18)

### Bug Fixes

- **color**: Clamp blend parameter in lerp methods
  ([`4c41ca4`](https://github.com/Djelibeybi/lifx-async/commit/4c41ca468ebdf288771be5972f628a43cc1fc0af))

- **effects**: Fix zones_per_bulb normalization, embers single-zone, CA restart, and test assertions
  ([`f049252`](https://github.com/Djelibeybi/lifx-async/commit/f04925282ccd15ef38f55639776c6a77357f3183))

- **effects**: Polish ported effects and fix API surface issues
  ([`ee01ec9`](https://github.com/Djelibeybi/lifx-async/commit/ee01ec9014dc5f26ff4d67d1efea8d97914c7870))

- **effects**: Resolve Pyright possibly-unbound variable in Sine effect
  ([`b6629ad`](https://github.com/Djelibeybi/lifx-async/commit/b6629ad7c15732b005ada925288416e91152a26e))

- **security**: Skip bandit B311 globally and remove nosec comments
  ([`90e713b`](https://github.com/Djelibeybi/lifx-async/commit/90e713b62743dc34b47ea21bc7b1087a96cb4258))

- **tests**: Update registry test to use superset check
  ([`a9c3063`](https://github.com/Djelibeybi/lifx-async/commit/a9c30635ba89238355b8e4b6c864e7b9cb9c8b7d))

- **tests**: Update theme count from 42 to 57 after palette additions
  ([`e416341`](https://github.com/Djelibeybi/lifx-async/commit/e4163414a24427d9e0f2d6bfe7d6e7669a4beed5))

### Documentation

- Add design spec for porting pkivolowitz/lifx effects
  ([`2d17778`](https://github.com/Djelibeybi/lifx-async/commit/2d17778dbdd8bc558fe33e061791832e9f11a928))

- Add implementation plan for effects port
  ([`70bfe89`](https://github.com/Djelibeybi/lifx-async/commit/70bfe8986cb77fb331db5f672883b69b6f200af8))

- Address spec review findings
  ([`9a3ca10`](https://github.com/Djelibeybi/lifx-async/commit/9a3ca106357a446b19b433dcfc2b1a8f42614f90))

### Features

- **color**: Add lerp_oklab and lerp_hsb methods to HSBK
  ([`71a794a`](https://github.com/Djelibeybi/lifx-async/commit/71a794a1ae8d7fc08e314e7b7f0acc79887ee720))

- **effects**: Add Cylon (Larson scanner) effect
  ([`26e75d5`](https://github.com/Djelibeybi/lifx-async/commit/26e75d5ee5f71a2e4764c00d4121735a18f2bdd3))

- **effects**: Add Double Slit (wave interference) effect
  ([`7617cca`](https://github.com/Djelibeybi/lifx-async/commit/7617ccad43b5b4b8d25ef4a3de3602a391a8e9bb))

- **effects**: Add Embers (fire simulation) effect
  ([`3a9ab6c`](https://github.com/Djelibeybi/lifx-async/commit/3a9ab6c44ec3a1f65a4c44bc969242be355e7c1e))

- **effects**: Add Fireworks effect
  ([`d509f4b`](https://github.com/Djelibeybi/lifx-async/commit/d509f4b5593e63d21e1bfd1c5e597e1b6f06e547))

- **effects**: Add Jacob's Ladder (electric arcs) effect
  ([`c447011`](https://github.com/Djelibeybi/lifx-async/commit/c4470119202e81d42712a0deca7984b3532f7ae7))

- **effects**: Add Newton's Cradle effect
  ([`a414b37`](https://github.com/Djelibeybi/lifx-async/commit/a414b37a69c590198c9d4e1dd98aaf6c069c61d7))

- **effects**: Add Pendulum Wave effect
  ([`9315730`](https://github.com/Djelibeybi/lifx-async/commit/931573011baf13d0fe1691a050a55215051b5fb4))

- **effects**: Add Plasma (electric tendrils) effect
  ([`6fed46d`](https://github.com/Djelibeybi/lifx-async/commit/6fed46d6409ebc95ea94eea3d828c08bd8367ae7))

- **effects**: Add Plasma2D effect for matrix devices
  ([`2a94fd7`](https://github.com/Djelibeybi/lifx-async/commit/2a94fd76e3b6fa177e50d6f857f108c9faddd5d4))

- **effects**: Add Ripple (water drops) effect
  ([`d3a4a33`](https://github.com/Djelibeybi/lifx-async/commit/d3a4a3356abe23290dd3f88997bdd95f8e6d04a9))

- **effects**: Add Rule 30 (cellular automaton) effect
  ([`13b9f07`](https://github.com/Djelibeybi/lifx-async/commit/13b9f077902d10eda1b66f7e57d0a70cc2b96b79))

- **effects**: Add Rule Trio (three CAs blended) effect
  ([`45346d4`](https://github.com/Djelibeybi/lifx-async/commit/45346d4a80e3128ab69bd393a38d56cabe7e6a38))

- **effects**: Add Sine (traveling ease wave) effect
  ([`24a2ec9`](https://github.com/Djelibeybi/lifx-async/commit/24a2ec9faadc30f809792dce9411d1efa5094cc2))

- **effects**: Add Sonar (radar pulses) effect
  ([`575fed4`](https://github.com/Djelibeybi/lifx-async/commit/575fed424eafe9e163efeecbe9d2119a1ef9dba9))

- **effects**: Add Spectrum Sweep effect
  ([`9aad95b`](https://github.com/Djelibeybi/lifx-async/commit/9aad95b924c8ee4e553b2ec23470d8b05b0049cf))

- **effects**: Add Spin (color migration) effect
  ([`9b91fc9`](https://github.com/Djelibeybi/lifx-async/commit/9b91fc9caa4304a99d92dc7ac13cfe9733e337f8))

- **effects**: Add Twinkle (sparkle) effect
  ([`2660f19`](https://github.com/Djelibeybi/lifx-async/commit/2660f19e39d75d4f081bb1d79cc4782c238a1aaf))

- **effects**: Add Wave (standing wave) effect
  ([`63cdf9b`](https://github.com/Djelibeybi/lifx-async/commit/63cdf9b3ffc105f7c0e26758221c6be518230303))

- **effects**: Register and export all 18 ported effects
  ([`c5caa0d`](https://github.com/Djelibeybi/lifx-async/commit/c5caa0db7334c3b40e3d702ea1fbff9474d1c678))

- **theme**: Add palette themes from pkivolowitz/lifx
  ([`4126ccf`](https://github.com/Djelibeybi/lifx-async/commit/4126ccff479f2e615634221b1e854c67b1caa4c4))


## v5.2.1 (2026-03-18)

### Bug Fixes

- **tests**: Add pytest-timeout, retry flaky Windows emulator tests
  ([`4b6b3a9`](https://github.com/Djelibeybi/lifx-async/commit/4b6b3a9f5870c4fe9b4e356152c0b0cd3086854a))

- **tests**: Extend timeout to 120s for emulator tests
  ([`016e1aa`](https://github.com/Djelibeybi/lifx-async/commit/016e1aa50c703b8da651b911624cecd21755f2ef))

### Documentation

- Add security policy
  ([`4e6c152`](https://github.com/Djelibeybi/lifx-async/commit/4e6c1526cc09c2ad08a85c8ce9978e6c6b708d3c))


## v5.2.0 (2026-02-07)

### Bug Fixes

- Address CodeRabbit review feedback
  ([`487f4ab`](https://github.com/Djelibeybi/lifx-async/commit/487f4abaa83f5d1a72e0ad50d27c08311bfd78cd))

### Documentation

- Fix duration_ms formula (1000 -> 1500/fps) in effects API docs
  ([`487f4ab`](https://github.com/Djelibeybi/lifx-async/commit/487f4abaa83f5d1a72e0ad50d27c08311bfd78cd))

### Features

- Add new effects, effect registry, and rename examples
  ([`2f8192d`](https://github.com/Djelibeybi/lifx-async/commit/2f8192d68c79670042b7a59dd2c63c9720806943))


## v5.1.1 (2026-02-06)

### Performance Improvements

- Optimize device initialization and packet sending
  ([`865c4e3`](https://github.com/Djelibeybi/lifx-async/commit/865c4e32f696881a4e0ed2932eb014c4136d0554))

- Pure-Python optimizations for protocol, network, and animation layers
  ([`a9a4bd4`](https://github.com/Djelibeybi/lifx-async/commit/a9a4bd40e35095c079339b336d82f1f5d509560a))


## v5.1.0 (2026-01-24)

### Bug Fixes

- **animation**: Load capabilities before checking has_chain
  ([`69e50b3`](https://github.com/Djelibeybi/lifx-async/commit/69e50b356ed22ad1679a823444db9fa7c19626b7))

### Documentation

- Add DeviceGroup usage example
  ([`9f85854`](https://github.com/Djelibeybi/lifx-async/commit/9f858543f745140c154128c63006047fccdbd823))

- Remove reference to deleted FieldSerializer class
  ([`5db0262`](https://github.com/Djelibeybi/lifx-async/commit/5db0262b593121be2de00bba44d522e11e449845))

### Features

- **animation**: Add high-performance animation module
  ([`afc8063`](https://github.com/Djelibeybi/lifx-async/commit/afc8063e6d863e118377facab30a7d3035b1ded5))


## v5.0.1 (2026-01-14)

### Bug Fixes

- Handle asyncio.TimeoutError on Python 3.10
  ([`4438bc4`](https://github.com/Djelibeybi/lifx-async/commit/4438bc45f19f477b585c6af8cf8cbaf5e9341d14))


## v5.0.0 (2026-01-12)

### Features

- Add Python 3.10 support
  ([`7c39131`](https://github.com/Djelibeybi/lifx-async/commit/7c391314305bb856d8bbcd23a5e481b729a5ad04))

### Breaking Changes

- Batch operations now raise first exception immediately (asyncio.gather behavior) instead of
  collecting all exceptions into an ExceptionGroup (TaskGroup behavior).


## v4.9.0 (2025-12-30)

### Features

- **api**: Add HTML named colors and kelvin temperature presets
  ([`b631d43`](https://github.com/Djelibeybi/lifx-async/commit/b631d43f9ba61db5f77e233a6bc0745bb3fed8b8))


## v4.8.1 (2025-12-24)

### Bug Fixes

- Tighten up the URL parsing to be even more specific
  ([`0222362`](https://github.com/Djelibeybi/lifx-async/commit/0222362ace8d7c8bbbe7d5a50f9fb21b7cb89cd5))


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
