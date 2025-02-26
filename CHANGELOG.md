# Changelog

## 1.6.0
### Added
- Support for dynamic opcode accounting, backward jumps, loops, callsub, retsub
- Ability to pay for more app space
- Ability to pool fees

### Bug Fix
- Raise JSONDecodeError instead of None (#193)

## 1.5.0
### Added
- Support new features for indexer 2.3.2
- Support for offline and nonparticipating key registration transactions.
- Add TEAL 3 support

### BugFix
- Detects the sending of unsigned transactions
- Add asset_info() and application_info() methods to the v2 AlgodClient class.

## 1.4.1
## Bugfix
- Dependency on missing constant removed
- Logic multisig signing fixed
- kmd.sign_transaction now works with application txn
- Added check for empty result in list_wallets
- Now zero receiver is handled in transactions
- Added init file for testing

## Changed
- Moved examples out of README into examples folder
- Added optional 'round_num' arguments to standardize 'round_num', 'round', and 'block'

## 1.4.0
## Added
- Support for Applications 
## Bugfix
- Now content-type is set when sending transactions
- indexer client now allows no token for local development environment

### Added
- Support for indexer and algod 2.0

## 1.2.0
### Added
- Added support for Algorand Smart Contracts (ASC) 
    - Dynamic fee contract
    - Limit order contract
    - Periodic payment contract
- Added SuggestedParams, which contains fee, first valid round, last valid round, genesis hash, and genesis ID; transactions and templates from 'future' take SuggestedParams as an argument.
    - Added suggested_params_as_object() in algod

## 1.1.1
### Added
- Added asset decimals field.

## 1.1.0
### Added
- Added support for Algorand Standardized Assets (ASA)
- Added support for Algorand Smart Contracts (ASC) 
    - Added support for Hashed Time Lock Contract (HTLC) 
    - Added support for Split contract
- Added support for Group Transactions
- Added support for leases

## 1.0.5
### Added
- custom headers and example

## 1.0.4
### Changed
- more flexibility in transactions_by_address()
- documentation changes

## 1.0.3
### Added
- signing and verifying signatures for arbitrary bytes

## 1.0.2
### Added
- option for flat fee when creating transactions
- functions for converting from microalgos to algos and from algos to microalgos

## 1.0.1
### Added
- algod.send_transaction(): sends SignedTransaction

### Changed
- algod.send_raw_transaction(): sends base64 encoded transaction
- Multisig.get_account_from_sig() is now Multisig.get_multisig_account

## 1.0.0
### Added
- SDK released
