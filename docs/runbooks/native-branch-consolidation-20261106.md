# Native branch consolidation, 2026-11-06

Review the changes, not just commit ancestry. The first shallow audit covered
24 refs including the symbolic default-branch alias. Independent full-history
recovery then verified all 23 actual remote branch heads. Excluding main and the
active producer, the 21 older branches comprise six ancestral branches, four
patch-equivalent branches, five obsolete metadata proposals and six motion/FEL
branches whose useful changes are now ported. No source benefit remains unported.

The recovery check also proves `fix/2202-passthrough-clock` is ancestral to the
producer; the shallow checkout could not establish that earlier. The final
three source groups were included in ee4e3e2. The verified full-history bundle
was restored into a separate empty repository, compared against all recorded
heads, and passed `git fsck` before the temporary recovery checkouts were removed.

Preserve recovery refs/bundles until the combined producer reaches main. Retire
old refs only after verifying their live heads still match the audited heads.
Do not restore their historical artifacts.json files or misleading version-only
dependency bump commits. Source-level equivalence does not establish binary
or device qualification.

| Reviewed ref | Audited head | Disposition |
| --- | --- | --- |
| `codex/3.0.0-windows-cross-build-oom-20261029` | `3581573d2baedfa32de84079c40338e8ab668021` | fully patch-equivalent |
| `codex/ci-cmake-android-glue-20261030` | `e846b40339a23ba1702dc58266511808351edb25` | fully patch-equivalent |
| `codex/dolby-vision-fel-20261026` | `a7daf6a8cf923657b04695309c1691c771e6f588` | Additive changes ported in ee4e3e2; older engine route superseded |
| `codex/fix-windows-ninja-wrapper-20261031` | `71c989a835819121ea4455af8629ecc9f5892cee` | fully patch-equivalent |
| `codex/motion-adaptive-phases-20261029` | `4fe0b70609ed12939748e79ca50bc14631252771` | PME/Vulkan/cadence source benefits now ported |
| `codex/motion-pme-overlap-20261028` | `003f85f3071736353c48932a78c239e04ffb64d5` | PME/Vulkan/cadence source benefits now ported |
| `codex/motion-pme-series-20261028` | `e430b4cf15ec4a1d4597f3959ff0b8b033cb2024` | Additive changes ported in ee4e3e2; older engine route superseded |
| `codex/motion-vulkan-linux-20261030` | `14d4b9bdb1cb376ded0c0202281a2081d31148ca` | PME/Vulkan/cadence source benefits now ported |
| `codex/pme-cadence-telemetry-20261031` | `79096a62e6390a1e69ea8c1ab2b6f313b0585754` | PME/Vulkan/cadence source benefits now ported |
| `codex/windows-build-swap-oom-20261030` | `5a1e6751e167b0d6399db8403d7f68981e741be9` | fully patch-equivalent |
| `create-pull-request/libass-build` | `4a6841b1f82d792fa78758e37d34317d2583bb4e` | obsolete metadata-only proposal |
| `create-pull-request/libplacebo-build` | `68c60918c33f7a88171df2833ba26366585d018a` | obsolete metadata-only proposal |
| `create-pull-request/libshaderc-build` | `5ee55a852870b0d200c4c773d9ff645f9b6b99b7` | obsolete metadata-only proposal |
| `create-pull-request/moltenvk-build` | `3a8ac69cb3b63f819cd9b8d91bdf59fc8e2a57db` | obsolete metadata-only proposal |
| `create-pull-request/pin-bump` | `b222748e358d25662f674398027508244021bca9` | obsolete metadata-only proposal |
| `fix/2202-passthrough-clock` | `6aa1d87491e42fe56f47afd506efd4e0f7ccb1ac` | superseded by consolidated implementation; no extra benefit found |


Desktop ports0170–0179 preserve FEL pairing and the non-Vulkan compilation
guard. Apple0004 and0042 are reconciled together, and Android0180 follows
the existing AudioTrack integration on both normal and FEL series. See
[neural runtime packaging](neural-runtime-packaging.md) for behavior tests and
packaging contracts. Immutable artifact keys must follow the combined source,
and final app pins must follow the verified producer manifest.
