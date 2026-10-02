#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================

Dependencies:
    pip install portaldot-interface

pallet_nfts is the "upgraded replacement" for pallet_uniques (closer to real-world NFT business scenarios).
Its core concepts are similar to pallet_uniques:
    - Collection (collection_id, u32): an NFT collection
    - Item (item_id, u32): a specific NFT within a collection

Coverage:
    1. create                                                     - Create an NFT collection (requires a CollectionConfig)
    2. mint                                                       - Mint an NFT
    3. burn                                                       - Burn an NFT
    4. transfer                                                   - Transfer an NFT
    5. lock_item_transfer / unlock_item_transfer                  - Lock/unlock transfers of a single item (equivalent to freeze/thaw)
    6. lock_collection                                            - Lock the whole collection's configuration (e.g. prevent further changes to settings)
    7. approve_transfer                                           - Authorize someone else to transfer an item on your behalf (an expiry block can be set)
    8. cancel_approval / clear_all_transfer_approvals             - Revoke approvals
    9. set_attribute / set_metadata / set_collection_metadata     - Metadata and attributes
    10. mint_pre_signed                                           - Offline pre-signed minting (whitelist / lazy-mint scenarios)
    11. set_price / buy_item                                      - Built-in listing marketplace (similar to a simple NFT exchange)

Notes:
    - Management operations in pallet_nfts likewise require the signing account to hold the corresponding Owner/Issuer/Admin/Freezer role.
    - Creating a collection requires a CollectionDeposit; minting requires an ItemDeposit;
      setting metadata/attributes requires the corresponding per-byte deposit.
    - This script is for demonstration only. Verify on the testnet before using it on mainnet.
    - Never hard-code mnemonics in code.
"""

import sys
from substrateinterface import SubstrateInterface, Keypair, KeypairType
from substrateinterface.exceptions import SubstrateRequestException

# --------------------------------------------------------------------------
# Basic configuration
# --------------------------------------------------------------------------

# NODE_URL = "ws://127.0.0.1:9944"
NODE_URL = "wss://testnetv3-node.feso-apps.xyz"
MNEMONIC = "couch divert chest fan ridge length theory tool ethics soldier frame cabbage"

MINTER_MNEMONIC = "add army oxygen fence eyebrow fiction vivid close about poet execute oven"
BUYER_MNEMONIC = "add army oxygen fence eyebrow fiction vivid close about poet execute oven"
NATIVE_POT_DECIMALS = 14

# Target Collection ID / Item ID (both u32) - replace according to your situation
COLLECTION_ID = 5
ITEM_ID = 1


def get_portaldot() -> SubstrateInterface:
    portaldot = SubstrateInterface(url=NODE_URL)
    print(f"[Connected] Chain: {portaldot.chain}  Node version: {portaldot.version}")
    return portaldot


def get_keypair() -> Keypair:
    if not MNEMONIC:
        print("Please set the mnemonic first")
        sys.exit(1)
    return Keypair.create_from_mnemonic(MNEMONIC)


def submit(portaldot: SubstrateInterface, keypair: Keypair, call, wait_for_inclusion: bool = True):
    """Shared sign + submit + result-handling logic"""
    extrinsic = portaldot.create_signed_extrinsic(call=call, keypair=keypair)
    try:
        receipt = portaldot.submit_extrinsic(extrinsic, wait_for_inclusion=wait_for_inclusion)
        print(f"  Extrinsic hash: {receipt.extrinsic_hash}")
        if wait_for_inclusion:
            print(f"  Success: {receipt.is_success}")
            if not receipt.is_success:
                print(f"  Failure reason: {receipt.error_message}")
            else:
                for event in receipt.triggered_events:
                    print(f"  Event: {event.value['event_id']} -> {event.value.get('attributes')}")
        return receipt
    except SubstrateRequestException as e:
        print(f"  Failed to submit extrinsic: {e}")
        return None


# --------------------------------------------------------------------------
# 1. Create a collection (create)
# --------------------------------------------------------------------------
def default_collection_config(max_supply: int = None, mint_price: int = None, transferable: bool = True):
    """
    Build the CollectionConfig required by pallet_nfts::create.
    The structure is roughly:
    {
        'settings': <bitmask, 0 means no restrictions>,
        'max_supply': Option<u32>,
        'mint_settings': {
            'mint_type': {'Issuer': None} | {'Public': None} | {'HolderOf': collection_id},
            'price': Option<Balance>,
            'start_block': Option<BlockNumber>,
            'end_block': Option<BlockNumber>,
            'default_item_settings': <bitmask>,
        }
    }
    Common bit flags for settings/default_item_settings (combine as needed; 0 = unrestricted / everything transferable and modifiable):
        TransferableItems = 0, LockedTransfer = 1<<0,
        UnlockedMetadata = 1<<1 (the on-chain definition is authoritative; using 0 for "fully open" is recommended to start)
    To keep the example simple, no restrictions are applied by default (0). In production, check the metadata
    (portaldot.get_metadata_call_function) to confirm the exact bit definitions.
    """
    return {
        'settings': 0,
        'max_supply': max_supply,
        'mint_settings': {
            'mint_type': {'Issuer': None},  # Only the Issuer can mint; use {'Public': None} to enable public minting
            'price': mint_price,
            'start_block': None,
            'end_block': None,
            'default_item_settings': 0 if transferable else 1,  # Example: 1 means transfers locked by default; exact bits per on-chain definition
        }
    }


def create_collection(portaldot: SubstrateInterface, keypair: Keypair, admin: str, config: dict = None):
    """
    Create a new NFT collection. In pallet_nfts the collection_id is usually assigned by the chain (read it from the return value/events).
    You can also use force_create (requires Root/Sudo) to set an admin other than the caller.
    """
    config = config or default_collection_config()
    print(f"\n[create] Creating collection, admin={admin}, config={config}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='create',
        call_params={
            'admin': admin,
            'config': config,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 2. Mint an NFT (mint)
# --------------------------------------------------------------------------
def mint_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
              item_id: int, owner: str, mint_witness: dict = None):
    """
    Mint item_id under collection_id, owned by `owner`.
    mint_witness is used to satisfy constraints in mint_settings (e.g. paying the price,
    or proving you hold an NFT from a HolderOf collection). For public/unconstrained minting, pass None.
    """
    print(f"\n[mint] Minting NFT collection_id={collection_id}, item_id={item_id}, owner={owner}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='mint',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'mint_to': owner,
            'witness_data': mint_witness,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 3. Burn an NFT (burn)
# --------------------------------------------------------------------------
def burn_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, item_id: int):
    """Burn the given item; the caller must be the item owner or hold the appropriate role"""
    print(f"\n[burn] Burning NFT collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='burn',
        call_params={
            'collection': collection_id,
            'item': item_id,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 4. Transfer an NFT (transfer)
# --------------------------------------------------------------------------
def transfer_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                   item_id: int, dest: str):
    """Transfer the item to `dest`; either the current owner or an approved delegate can initiate it"""
    print(f"\n[transfer] Transferring NFT collection_id={collection_id}, item_id={item_id} -> {dest}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='transfer',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'dest': dest,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 5. Lock / unlock transfers of a single item (equivalent to freeze / thaw)
# --------------------------------------------------------------------------
def lock_item_transfer(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, item_id: int):
    """Lock a single item's ability to be transferred (Freezer/Admin role); equivalent to pallet_uniques freeze"""
    print(f"\n[lock_item_transfer] Locking NFT transfer collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='lock_item_transfer',
        call_params={
            'collection': collection_id,
            'item': item_id,
        }
    )
    return submit(portaldot, keypair, call)


def unlock_item_transfer(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, item_id: int):
    """Unlock a single item's ability to be transferred; equivalent to pallet_uniques thaw"""
    print(f"\n[unlock_item_transfer] Unlocking NFT transfer collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='unlock_item_transfer',
        call_params={
            'collection': collection_id,
            'item': item_id,
        }
    )
    return submit(portaldot, keypair, call)


def lock_item_properties(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, item_id: int,
                          lock_metadata: bool = True, lock_attributes: bool = True):
    """
    Lock the item's metadata/attributes so they can no longer be modified (often used to "finalize" an NFT and prevent later tampering with fields like rarity).
    Note: this lock is one-way and irreversible.
    """
    print(f"\n[lock_item_properties] Locking NFT properties collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='lock_item_properties',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'lock_metadata': lock_metadata,
            'lock_attributes': lock_attributes,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 6. Lock the entire collection (lock_collection)
# --------------------------------------------------------------------------
def lock_collection(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                     lock_settings: int):
    """
    Lock some of the collection's settings (e.g. prevent later changes to mint settings, prevent adding new items, etc.).
    lock_settings is a bitmask; the exact values are defined by CollectionSettings in the target chain's metadata.
    This operation is also irreversible - use with care.
    """
    print(f"\n[lock_collection] Locking collection config collection_id={collection_id}, lock_settings={lock_settings}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='lock_collection',
        call_params={
            'collection': collection_id,
            'lock_settings': lock_settings,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 7. Approve a delegated transfer (approve_transfer)
# --------------------------------------------------------------------------
def approve_transfer(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                      item_id: int, delegate: str, maybe_deadline: int = None):
    """
    The item's owner authorizes `delegate` to transfer the item on their behalf.
    Unlike pallet_uniques, an optional maybe_deadline (block height) is supported here;
    the approval expires automatically after it. Pass None if no expiry is needed.
    Multiple approvals for different delegates can exist on the same item at once (unlike pallet_uniques' "single delegate").
    """
    print(f"\n[approve_transfer] Approving {delegate} to transfer NFT collection_id={collection_id}, "
          f"item_id={item_id}, deadline={maybe_deadline}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='approve_transfer',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'delegate': delegate,
            'maybe_deadline': maybe_deadline,
        }
    )
    return submit(portaldot, keypair, call)


def delegated_transfer(portaldot: SubstrateInterface, delegate_keypair: Keypair, collection_id: int,
                        item_id: int, dest: str):
    """The approved account calls transfer directly to perform the delegated transfer; the chain checks it is a valid, unexpired delegate"""
    print(f"\n[delegated transfer] {delegate_keypair.ss58_address} transferring NFT on owner's behalf "
          f"collection_id={collection_id}, item_id={item_id} -> {dest}")
    return transfer_item(portaldot, delegate_keypair, collection_id, item_id, dest)


# --------------------------------------------------------------------------
# 8. Cancel approvals (cancel_approval / clear_all_transfer_approvals)
# --------------------------------------------------------------------------
def cancel_approval(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                     item_id: int, delegate: str):
    """Revoke the approval for one specific delegate"""
    print(f"\n[cancel_approval] Revoking approval for {delegate} collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='cancel_approval',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'delegate': delegate,
        }
    )
    return submit(portaldot, keypair, call)


def clear_all_transfer_approvals(portaldot: SubstrateInterface, keypair: Keypair,
                                  collection_id: int, item_id: int):
    """Clear all approvals on the item at once (no need to specify each delegate)"""
    print(f"\n[clear_all_transfer_approvals] Clearing all approvals collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='clear_all_transfer_approvals',
        call_params={
            'collection': collection_id,
            'item': item_id,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 9. Metadata / attributes (set_attribute / set_metadata / set_collection_metadata)
# --------------------------------------------------------------------------
def set_attribute(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                   item_id: int, key: bytes, value: bytes, namespace: dict = None):
    """
    Set an item attribute. `namespace` determines who maintains the attribute. Common values:
        {'CollectionOwner': None} - attribute set by the collection owner
        {'ItemOwner': None}       - attribute set by the item's current holder
        {'Account': some_address} - set by a third-party account (which pays its own deposit)
    Defaults to CollectionOwner.
    """
    namespace = namespace or {'CollectionOwner': None}
    print(f"\n[set_attribute] Setting attribute collection_id={collection_id}, item_id={item_id}, key={key}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='set_attribute',
        call_params={
            'collection': collection_id,
            'maybe_item': item_id,
            'namespace': namespace,
            'key': key,
            'value': value,
        }
    )
    return submit(portaldot, keypair, call)


def set_metadata(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                  item_id: int, data: bytes):
    """Set metadata for a single item (usually an IPFS URI or similar)"""
    print(f"\n[set_metadata] Setting item metadata collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='set_metadata',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'data': data,
        }
    )
    return submit(portaldot, keypair, call)


def set_collection_metadata(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, data: bytes):
    """Set metadata for the whole collection (e.g. a URI for the cover image or description document)"""
    print(f"\n[set_collection_metadata] Setting collection metadata collection_id={collection_id}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='set_collection_metadata',
        call_params={
            'collection': collection_id,
            'data': data,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 10. Offline pre-signed minting (mint_pre_signed)
# --------------------------------------------------------------------------
"""
Use case:
    The collection Owner/Issuer wants to pre-authorize "who can mint which item" via an offline signature,
    without an on-chain interaction for every mint (common for whitelist sales and lazy-minting).
    The flow has two steps:
        1) The Owner builds and signs the PreSignedMint data off-chain (build_and_sign_pre_signed_mint),
           then sends (mint_data, signature) to the party authorized to mint (any account, including the buyer).
        2) The authorized party (who need not be the Owner) calls mint_pre_signed and pays the fee
           to complete the mint; the chain verifies that the signature really comes from the Owner/Issuer, has not expired and has not been used.
"""
def get_call_arg_type_string(portaldot: SubstrateInterface, module: str, call: str, arg_name: str) -> str:
    """
    Dynamically look up, from the current chain's metadata, the SCALE type reference string for an extrinsic argument
    (e.g. "scale_info::450"), avoiding hard-coded type indexes or guessing type names.
    """
    call_function = portaldot.get_metadata_call_function(module, call)
    for arg in call_function.args:
        name = arg.get('name') if isinstance(arg, dict) else getattr(arg, 'name', None)
        type_ref = arg.get('type') if isinstance(arg, dict) else getattr(arg, 'type', None)
        if name != arg_name:
            continue

        if isinstance(type_ref, int):
            return f"scale_info::{type_ref}"

        type_str = str(type_ref)
        if type_str.isdigit():
            # Purely numeric string, e.g. "450"
            return f"scale_info::{type_str}"
        # Already a usable type reference (e.g. "scale_info::450" or a registered type name) - return as is
        return type_str
    raise ValueError(
        f"'{arg_name}' not found in the argument list of {module}.{call}; "
        f"print get_metadata_call_function('{module}', '{call}') "
        f"to check the argument names manually."
    )

def format_multisignature(keypair: Keypair, signature_bytes: bytes) -> dict:
    """
    Wrap raw signature bytes in the MultiSignature enum format ({'Sr25519': '0x...'} etc.).
    portaldot-interface needs this step when building a signature manually (rather than via create_signed_extrinsic).
    """
    crypto_type_map = {
        KeypairType.ED25519: 'Ed25519',
        KeypairType.SR25519: 'Sr25519',
        KeypairType.ECDSA: 'Ecdsa',
    }
    variant = crypto_type_map.get(keypair.crypto_type, 'Sr25519')
    return {variant: '0x' + signature_bytes.hex()}


def build_and_sign_pre_signed_mint(portaldot: SubstrateInterface, owner_keypair: Keypair,
                                    collection_id: int, item_id: int,
                                    attributes: list = None, metadata: bytes = b'',
                                    only_account: str = None, mint_price: int = None,
                                    valid_for_blocks: int = 200):
    """
    The collection Owner/Issuer builds and signs a "pre-authorized mint voucher" off-chain.
    attributes: [(key: bytes, value: bytes), ...], written at mint time
    only_account: if set, only this account can mint with the voucher; None means anyone holding the voucher can mint
    valid_for_blocks: voucher validity (offset from the current block height)
    Returns (mint_data, signature_dict); both must be handed to whoever actually performs the mint.
    """
    attributes = attributes or []
    current_block = portaldot.get_block_number(portaldot.get_chain_head())
    deadline = current_block + valid_for_blocks

    mint_data = {
        'collection': collection_id,
        'item': item_id,
        'attributes': attributes,
        'metadata': metadata,
        'only_account': only_account,
        'deadline': deadline,
        'mint_price': mint_price,
    }

    # SCALE-encode mint_data using the on-chain type definition, then sign it
    mint_data_type = get_call_arg_type_string(portaldot, "Nfts", "mint_pre_signed", "mint_data")
    scale_obj = portaldot.create_scale_object(mint_data_type)
    encoded = scale_obj.encode(mint_data)
    signature_bytes = owner_keypair.sign(encoded)

    print(f"\n[build_and_sign_pre_signed_mint] Pre-signed voucher generated: "
          f"collection={collection_id}, item={item_id}, deadline={deadline}, "
          f"only_account={only_account}")
    return mint_data, format_multisignature(owner_keypair, signature_bytes)


def mint_pre_signed(portaldot: SubstrateInterface, minter_keypair: Keypair,
                     mint_data: dict, signature: dict, signer: str):
    """
    The party actually performing the mint (any account, as long as it satisfies the only_account restriction in mint_data
    and submits before the deadline) calls this function to complete the on-chain mint.
    signer: the Owner/Issuer address that generated the pre-signed voucher (used for on-chain signature verification).
    If mint_data sets a mint_price, make sure the minter_keypair account has sufficient balance.
    """
    print(f"\n[mint_pre_signed] {minter_keypair.ss58_address} minting with pre-signed voucher "
          f"collection={mint_data['collection']}, item={mint_data['item']}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='mint_pre_signed',
        call_params={
            'mint_data': mint_data,
            'signature': signature,
            'signer': signer,
        }
    )
    return submit(portaldot, minter_keypair, call)


# --------------------------------------------------------------------------
# 11. Built-in listing marketplace (set_price / buy_item)
# --------------------------------------------------------------------------
def set_price(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, item_id: int,
              price: int, whitelisted_buyer: str = None):
    """
    The item's owner lists the item for sale.
    price: sale price (in the smallest unit); pass None to delist/cancel the listing.
    whitelisted_buyer: if set, only this address can buy at this price (private-deal scenario);
                        if None, anyone can buy (public listing).
    """
    action = "Delisting" if price is None else f"Listing for sale (price={price})"
    print(f"\n[set_price] {action} collection_id={collection_id}, item_id={item_id}"
          + (f", buyer restricted to={whitelisted_buyer}" if whitelisted_buyer else ""))
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='set_price',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'price': price,
            'whitelisted_buyer': whitelisted_buyer,
        }
    )
    return submit(portaldot, keypair, call)


def buy_item(portaldot: SubstrateInterface, buyer_keypair: Keypair, collection_id: int,
             item_id: int, bid_price: int):
    """
    A buyer purchases an item that is listed for sale.
    bid_price: the price the buyer is willing to pay; must be >= the current listing price (you may bid higher, but usually pass the listing price);
               if the item has a whitelisted_buyer that is not buyer_keypair's address, the transaction is rejected.
    After the sale, ownership is transferred to the buyer automatically and the proceeds go to the original owner.
    """
    print(f"\n[buy_item] {buyer_keypair.ss58_address} buying collection_id={collection_id}, "
          f"item_id={item_id}, bid_price={bid_price}")
    call = portaldot.compose_call(
        call_module='Nfts',
        call_function='buy_item',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'bid_price': bid_price,
        }
    )
    return submit(portaldot, buyer_keypair, call)

# --------------------------------------------------------------------------
# Helpers: query collection / NFT info
# --------------------------------------------------------------------------
def query_collection_info(portaldot: SubstrateInterface, collection_id: int):
    result = portaldot.query(module='Nfts', storage_function='Collection', params=[collection_id])
    print(f"\n[query] Collection({collection_id}) details: {result.value}")
    return result.value


def query_item_info(portaldot: SubstrateInterface, collection_id: int, item_id: int):
    result = portaldot.query(module='Nfts', storage_function='Item', params=[collection_id, item_id])
    print(f"\n[query] Item({collection_id}, {item_id}) info: {result.value}")
    return result.value


def query_item_attribute(portaldot: SubstrateInterface, collection_id: int, item_id: int,
                          namespace: dict, key: bytes):
    result = portaldot.query(module='Nfts', storage_function='Attribute',
                              params=[collection_id, item_id, namespace, key])
    print(f"\n[query] Item({collection_id}, {item_id}) attribute[{key}]: {result.value}")
    return result.value

def query_item_price(portaldot: SubstrateInterface, collection_id: int, item_id: int):
    """Query the item's current listing price (and whitelisted_buyer, if any)"""
    result = portaldot.query(module='Nfts', storage_function='ItemPriceOf', params=[collection_id, item_id])
    print(f"\n[query] Item({collection_id}, {item_id}) listing: {result.value}")
    return result.value

# --------------------------------------------------------------------------
# Main flow example
# --------------------------------------------------------------------------
def main():
    portaldot = get_portaldot()
    keypair = get_keypair()
    print(f"Current signing account: {keypair.ss58_address}")

    other_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

    # --- Query existing collection/NFT info (no permissions required; anyone can query) ---
    query_collection_info(portaldot, COLLECTION_ID)
    query_item_info(portaldot, COLLECTION_ID, ITEM_ID)

    # --- Uncomment the operations below as needed (most require the corresponding role, otherwise NoPermission/BadOrigin) ---

    # 1) Create the collection (collection_id is assigned by the chain; read the actual id from the events in the receipt)
    create_collection(portaldot, keypair, admin=keypair.ss58_address)

    # 2) Mint NFTs (default mint_type is Issuer, requiring the Issuer role; if configured as Public, anyone can mint)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID, owner=keypair.ss58_address)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+1, owner=keypair.ss58_address)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+2, owner=keypair.ss58_address)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+3, owner=keypair.ss58_address)

    # 3) Set metadata / attributes
    set_collection_metadata(portaldot, keypair, COLLECTION_ID, data=b'ipfs://Qm.../collection.json')
    set_metadata(portaldot, keypair, COLLECTION_ID, ITEM_ID, data=b'ipfs://Qm.../item.json')
    set_attribute(portaldot, keypair, COLLECTION_ID, ITEM_ID, key=b'test_nfts_key', value=b'test_nfts_value')

    # 4) Regular transfer
    transfer_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+1, dest=other_address)

    # 5) Approve someone else to transfer on your behalf (optionally set an expiry block maybe_deadline)
    approve_transfer(portaldot, keypair, COLLECTION_ID, ITEM_ID, delegate=other_address, maybe_deadline=None)

    # 6) Delegated transfer by the approved party (must be signed with the delegate's own Keypair; shown here for illustration only)
    # delegate_keypair = Keypair.create_from_mnemonic("DELEGATE_MNEMONIC")
    # delegated_transfer(portaldot, delegate_keypair, COLLECTION_ID, ITEM_ID, dest=other_address)

    # 7) Revoke approvals
    cancel_approval(portaldot, keypair, COLLECTION_ID, ITEM_ID, delegate=other_address)
    clear_all_transfer_approvals(portaldot, keypair, COLLECTION_ID, ITEM_ID)

    # 8) Lock / unlock transfers of a single item (equivalent to freeze/thaw)
    lock_item_transfer(portaldot, keypair, COLLECTION_ID, ITEM_ID)
    unlock_item_transfer(portaldot, keypair, COLLECTION_ID, ITEM_ID)

    # 9) Lock item properties / lock the whole collection config (irreversible - use with care)
    # lock_item_properties(portaldot, keypair, COLLECTION_ID, ITEM_ID)
    # lock_collection(portaldot, keypair, COLLECTION_ID, lock_settings=0)

    # 10) Burn an NFT
    burn_item(portaldot, keypair, COLLECTION_ID, ITEM_ID)

    # 11) Offline pre-signed minting: the owner signs off-chain, then any account (even the buyer) redeems it on-chain
    owner_keypair = keypair  # Assume the current account is the collection Owner/Issuer
    minter_keypair = Keypair.create_from_mnemonic(MINTER_MNEMONIC)  # The account that actually performs the mint
    mint_data, signature = build_and_sign_pre_signed_mint(
        portaldot, owner_keypair, COLLECTION_ID, ITEM_ID+4,
        attributes=[(b'test_nfts_offline_key', b'test_nfts_offline_value')],
        metadata=b'ipfs://Qm.../item.json',
        only_account=minter_keypair.ss58_address,   # If None, anyone can mint with this voucher
        mint_price=None,
        valid_for_blocks=200,
    )
    mint_pre_signed(portaldot, minter_keypair, mint_data, signature, signer=owner_keypair.ss58_address)

    # 12) List for sale / buy (built-in simple marketplace)
    set_price(portaldot, keypair, COLLECTION_ID, ITEM_ID+2, price=8*10**NATIVE_POT_DECIMALS)  # list
    query_item_price(portaldot, COLLECTION_ID, ITEM_ID)
    buyer_keypair = Keypair.create_from_mnemonic(BUYER_MNEMONIC)
    buy_item(portaldot, buyer_keypair, COLLECTION_ID, ITEM_ID+2, bid_price=9*10**NATIVE_POT_DECIMALS) # bid price

    set_price(portaldot, keypair, COLLECTION_ID, ITEM_ID+3, price=10*10**NATIVE_POT_DECIMALS)  # list
    set_price(portaldot, keypair, COLLECTION_ID, ITEM_ID+3, price=None)  # delist

    print("\nScript finished.")


if __name__ == '__main__':
    main()
