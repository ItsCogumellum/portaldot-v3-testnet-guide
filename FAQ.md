# Portaldot V3.0 FAQ

Last updated: October 7, 2026

This FAQ separates behavior demonstrated by the current Portaldot V3 testnet guide from Mainnet 3.0 details that have not yet been announced. Testnet endpoints, token symbols, chain IDs, screenshots, and examples must not be treated as final mainnet configuration.

## Status key

- **Documented:** described or demonstrated in the current testnet guide or sample code.
- **Listed for V3.0:** included in the V3.0 feature description, but without a launch date, rollout phase, or participation requirements.
- **Awaiting confirmation:** not specified by the available Portaldot documentation. It should not be presented as a launch commitment.

## Revive, EVM tooling, and accounts

### How does revive-based EVM compatibility work in practice?

Portaldot V3 exposes an Ethereum-compatible JSON-RPC endpoint for Solidity contracts through the `revive` module. The current guide documents the following workflow:

1. Add the Portaldot V3 testnet to MetaMask.
2. Use an Ethereum-style H160 account as the deployer.
3. Resolve that H160 address to its mapped Substrate `AccountId32`/SS58 address with `reviveApi.accountId`.
4. Fund the mapped SS58 address with test POT for gas and contract operations.
5. Compile and deploy the Solidity contract from Remix, or configure Hardhat with the testnet RPC and chain ID.
6. Interact with the same revive contract through EVM tooling or Portaldot tooling. Native-side state-changing calls should be dry-run first to determine the required weight/gas and storage-deposit limit.

MetaMask, Remix, and Hardhat are documented. Foundry is not currently tested or documented in this repository, so Mainnet 3.0 Foundry support is **awaiting confirmation**.

### What is the H160-to-SS58 mapping, and will wallets handle it automatically?

Portaldot uses H160 addresses for Ethereum-style tooling and `AccountId32`/SS58 addresses on the native Substrate side. `revive` maps between these representations. On the current testnet, the guide tells users to query **Developer → Runtime calls → reviveApi → accountId** and fund the returned SS58 address. After that funding, the corresponding balance appears in MetaMask.

Automatic mapping or display by wallets and explorers on Mainnet 3.0 is **awaiting confirmation**. Until the mainnet workflow is published, users should resolve and verify the mapped address instead of assuming that a wallet or explorer has done it automatically.

### What happens if POT is sent directly to an H160 address from the native side?

The current Portaldot documentation does not define a recovery procedure or guarantee that an incorrectly addressed transfer can be recovered. Users should not test this with real funds. They should first obtain the mapped SS58 address with `reviveApi.accountId`, verify it, and make a small test transfer.

Recovery behavior, any fallback-account tool, and the official support process for Mainnet 3.0 are **awaiting confirmation**.

### Can one account be used across EVM, WASM/ink!, Assets, and NFTs?

The guide demonstrates that a revive H160 account has a mapped native account and that native POT funded to that mapping is visible to EVM tooling. It does not demonstrate a single account workflow across `contracts` (WASM/ink!), `assets`, `uniques`, and `nfts`, nor does it specify wallet UX for those modules.

It is therefore safe to say that revive provides an H160/native-account mapping. A universal account experience across every module is **awaiting confirmation and end-to-end testing**.

### Who pays gas, and how do storage deposits work?

The transaction signer funds execution. In the documented testnet flow, the mapped account must hold test POT to deploy or call a Solidity contract. Contract execution consumes gas/weight, while new on-chain storage can also require a storage deposit.

When using Portaldot tooling, run a dry-run before a state-changing call. The dry-run returns the required `weight_limit` and `storage_deposit_limit`; those values are then supplied to the on-chain `Revive.call` extrinsic. A read-only runtime call does not persist changes.

Final Mainnet 3.0 fee parameters, deposit rates, and limits are **awaiting confirmation**.

### What is the purpose of deploying with Remix? Is Remix a way to interact with testnet POT?

Remix is used to compile, deploy, and call Solidity smart contracts through MetaMask on the Portaldot V3 testnet. MetaMask signs the transaction, and test POT in the mapped account pays the transaction cost.

Remix is not a faucet and does not create test POT. It is a development interface for contract deployment and interaction.

## Native modules and smart contracts

### Should new NFT projects use `nfts` or `uniques`?

For new projects that need richer NFT behavior, `nfts` is the recommended starting point in the current guide. It supports features such as configurable minting, public and pre-signed minting, role-based attribute namespaces, finer-grained locks, approvals, pricing, and atomic swaps.

`uniques` remains suitable for simpler collections, basic NFT operations, and compatibility with implementations already built around that module. Teams should still verify the exact runtime calls and deposits on testnet before choosing a production design.

### When should a project use native Assets/NFTs instead of Solidity contracts?

| Choose | Good fit |
|---|---|
| Native `assets` | Standard fungible tokens that benefit from runtime-level minting, burning, freezing, roles, approvals, and lower implementation complexity. |
| Native `nfts` | Collections that can use the runtime's built-in minting, metadata, attributes, approvals, locking, pricing, and swap features. |
| `uniques` | Basic or existing NFT implementations that do not need the richer `nfts` feature set. |
| Solidity through `revive` | Custom programmable logic, Ethereum-style developer workflows, or applications being adapted from the Solidity ecosystem. |
| WASM/ink! through `contracts` | Applications intentionally built for the chain's WASM contract environment. Mainnet tooling and interoperability details are still to be published. |

Native modules and smart contracts are separate execution and asset models. The right choice depends on whether the application needs standardized runtime features or custom contract logic.

### Can ink! contracts call Solidity contracts, and can Solidity contracts call ink! contracts in the same transaction?

This is **awaiting confirmation**. The available Portaldot guide shows two ways to interact with a Solidity contract deployed through `revive`: EVM tooling and Portaldot tooling. It does not document direct cross-calls between the `contracts` and `revive` modules.

No project should assume synchronous ink!↔Solidity composability until Portaldot publishes the supported call path, address conversion rules, gas/weight behavior, and failure semantics.

### Does an ERC-20 or ERC-721 automatically appear in native Assets, `nfts`, or iBridge?

No automatic representation is documented. An ERC token deployed in `revive`, an asset created in `assets`, and an NFT created in `nfts` are different on-chain objects unless Portaldot provides an explicit adapter, precompile, wrapper, or bridge route.

iBridge is listed as an EVM cross-chain interoperability feature, but its supported networks, token-registration process, custody or mint/burn model, fees, limits, and launch availability are **awaiting confirmation**.

### Can a failed call leave inconsistent balances?

Within a normal revive contract call, failed execution is expected to roll back the call's state changes. However, the current Portaldot documentation does not define atomic behavior for future cross-module, ink!↔Solidity, or bridge operations. Those paths must be documented and tested separately before the community promises atomic settlement.

## Mainnet 3.0 features and launch status

### Which features are listed for V3.0?

The V3.0 feature description lists the following modules. The source describes their purpose, but does not state whether each one will be enabled on launch day.

| Category | Feature | Runtime module | Described purpose | Current status |
|---|---|---|---|---|
| Consensus | BEEFY | `beefy` | Cross-chain proof mechanism | Listed for V3.0; launch timing not specified |
| Governance | OpenGov Referenda | `referenda` | New governance system | Listed for V3.0; launch timing not specified |
| Governance | Voting and Delegation | `conviction_voting` | Conviction voting | Listed for V3.0; launch timing not specified |
| Governance support | Preimage | `preimage` | Stores governance call data | Listed for V3.0; launch timing not specified |
| Parachain | Parachain Registration | `paras` | Parachain management | Listed for V3.0; launch timing not specified |
| Parachain | Collator System | `cumulus_parachain_system` | Collator support | Listed for V3.0; launch timing not specified |
| Coretime | Agile Coretime | `broker` | Coretime market | Listed for V3.0; launch timing not specified |
| Smart contracts | WASM Contracts | `contracts` | ink! contract runtime environment | Listed for V3.0; launch timing not specified |
| Smart contracts | EVM-compatible execution | `revive` | Solidity-compatible contract direction | Documented on testnet; mainnet launch details not specified |
| NFT | NFT Collection / Item | `nfts` | NFT creation, transfer, and attributes | Documented on testnet; mainnet launch details not specified |
| Identity | On-chain Identity | `identity` | Identity registration and verification | Listed for V3.0; launch timing not specified |
| Bridging | iBridge | `ibridge` | EVM cross-chain interoperability | Listed for V3.0; launch timing not specified |

The launch-day status and participation requirements for BEEFY, parachain registration, Agile Coretime, collators, on-chain identity, and iBridge are **awaiting an official release matrix**.

### Will the Mainnet 3.0 upgrade be seamless for existing users?

The available documents do not specify the migration plan for existing POT balances, bonded staking positions, unclaimed staking rewards, account mappings, or application state. Users should not be told to migrate funds or unbond based on the current testnet guide.

Before launch, Portaldot should publish a migration notice stating:

- whether balances and staking state carry over automatically;
- whether users, validators, or collators must take action;
- the snapshot or upgrade block, if any;
- expected downtime or service interruptions;
- how exchanges, wallets, explorers, and RPC providers should prepare;
- the official recovery and support process.

Until that notice exists, migration behavior is **awaiting confirmation**.

### How will V3.0 maintain performance and low fees as usage grows?

The current materials do not provide throughput targets, fee benchmarks, block limits, congestion policy, capacity plans, or service-level commitments. Agile Coretime and the collator/parachain components are listed as V3.0 features, but the feature list alone does not prove a specific scaling result.

Performance claims should wait for published benchmarks and mainnet parameters covering transaction throughput, block utilization, contract limits, fee behavior under load, RPC capacity, and cross-chain latency.

### Which use cases and builder programs will Portaldot prioritize?

The testnet guide currently enables experimentation with native fungible assets, native NFTs, Solidity contracts through `revive`, and native-side contract interaction. Those are practical areas for builders to test now.

The official priority use cases, grants, hackathons, incentives, partnerships, onboarding programs, and user-acquisition plans are not specified in the available technical materials and are **awaiting a community or ecosystem announcement**.

## What the community can safely say today

- Portaldot V3 testnet documents native Assets, basic and advanced native NFTs, and Solidity contracts through `revive`.
- MetaMask, Remix, and Hardhat are included in the current Solidity workflow.
- EVM accounts use an H160/native-account mapping. The current guide instructs users to resolve the mapped SS58 address before funding from the native side.
- Remix deploys and interacts with contracts; it does not distribute test tokens.
- `nfts` is the richer native NFT module, while `uniques` covers more basic use cases.
- The V3.0 feature list names BEEFY, OpenGov, parachain and collator support, Agile Coretime, WASM contracts, `revive`, native NFTs, identity, and iBridge.
- Mainnet launch dates, rollout phases, migration instructions, participation requirements, cross-environment interoperability, and performance commitments require a separate official announcement.

## References

- [Portaldot V3 Testnet Guide](README.md)
- `PortaldotV3_New_Features_Description.xlsx`, provided by the Portaldot team on October 7, 2026
- [Polkadot SDK `pallet_revive` address mapping](https://paritytech.github.io/polkadot-sdk/master/pallet_revive/trait.AddressMapper.html)
- [Polkadot SDK `pallet_revive` calls and account recovery primitives](https://paritytech.github.io/polkadot-sdk/master/pallet_revive/pallet/struct.Pallet.html)
- [Polkadot SDK contract execution results and storage-deposit rollback](https://paritytech.github.io/polkadot-sdk/master/pallet_revive/struct.ContractResult.html)

The Polkadot SDK links provide technical background only. Portaldot's deployed runtime and official release notes are authoritative for Portaldot-specific behavior.
