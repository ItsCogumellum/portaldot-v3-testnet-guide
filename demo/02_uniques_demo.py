#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================

Dependencies:
    pip install portaldot-interface

pallet_uniques is the module for managing NFTs. Core concepts:
    - Collection (collection_id, u32): a "series/collection" of NFTs
    - Item (item_id, u32): a specific NFT within a collection

Coverage:
    1. create                                        - Create a new NFT collection
    2. mint                                          - Mint a new NFT (item) in a collection
    3. burn                                          - Burn a specific NFT
    4. transfer                                      - Transfer NFT ownership
    5. freeze / thaw                                 - Freeze/unfreeze a single item (blocks transfers)
    6. freeze_collection / thaw_collection           - Freeze/unfreeze an entire collection
    7. approve_transfer                              - Authorize someone else to transfer an item on your behalf
    8. cancel_approval                               - Revoke that approval
    9. set_metadata / set_attribute                  - Set item metadata/attributes (commonly used in NFT scenarios)
    10. set_price / buy_item                         - Built-in listing marketplace (similar to a simple NFT exchange)

Notes:
    - Most management calls in pallet_uniques (create/mint/burn/freeze, etc.) require the signing account
      to be the collection's Owner/Issuer/Admin/Freezer; insufficient permissions return NoPermission/BadOrigin.
    - Creating a collection usually requires a CollectionDeposit; minting a single item requires an ItemDeposit.
    - This script is for demonstration only. Verify on the testnet before using it on mainnet.
    - Never hard-code mnemonics in code.
"""

import sys
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

# --------------------------------------------------------------------------
# Basic configuration
# --------------------------------------------------------------------------

# NODE_URL = "ws://127.0.0.1:9944"
NODE_URL = "wss://testnetv3-node.feso-apps.xyz"
MNEMONIC = "couch divert chest fan ridge length theory tool ethics soldier frame cabbage"

BUYER_MNEMONIC = "add army oxygen fence eyebrow fiction vivid close about poet execute oven"
NATIVE_POT_DECIMALS = 14

# Target Collection ID / Item ID (both u32) - replace according to your situation
COLLECTION_ID = 2
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
def create_collection(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, admin: str):
    """
    Create a new NFT collection.
    admin: the collection's admin address (by default also holds the Issuer/Admin/Freezer roles; these can later be assigned separately via set_team).
    The creator must pay a CollectionDeposit.
    """
    print(f"\n[create] Creating collection collection_id={collection_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='create',
        call_params={
            'collection': collection_id,
            'admin': admin,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 2. Mint an NFT (mint)
# --------------------------------------------------------------------------
def mint_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
              item_id: int, owner: str):
    """
    The Issuer account mints a new item under collection_id, owned by `owner`.
    The minter must pay an ItemDeposit.
    """
    print(f"\n[mint] Minting NFT collection_id={collection_id}, item_id={item_id}, owner={owner}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='mint',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'owner': owner,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 3. Burn an NFT (burn)
# --------------------------------------------------------------------------
def burn_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
              item_id: int, check_owner: str = None):
    """
    Burn the given item. check_owner is optional and verifies the current owner matches what you expect (prevents race conditions).
    The caller must be the item's owner or the collection's Admin.
    """
    print(f"\n[burn] Burning NFT collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='burn',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'check_owner': check_owner,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 4. Transfer an NFT (transfer)
# --------------------------------------------------------------------------
def transfer_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                   item_id: int, dest: str):
    """
    Transfer the item to `dest`. Only the current owner (or an approved delegate, see approve_transfer)
    can initiate it successfully.
    """
    print(f"\n[transfer] Transferring NFT collection_id={collection_id}, item_id={item_id} -> {dest}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='transfer',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'dest': dest,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 5. Freeze / thaw a single item (freeze / thaw)
# --------------------------------------------------------------------------
def freeze_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, item_id: int):
    """The Freezer account freezes a single item; it cannot be transferred while frozen"""
    print(f"\n[freeze] Freezing NFT collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='freeze',
        call_params={
            'collection': collection_id,
            'item': item_id,
        }
    )
    return submit(portaldot, keypair, call)


def thaw_item(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int, item_id: int):
    """Unfreeze a single item"""
    print(f"\n[thaw] Unfreezing NFT collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='thaw',
        call_params={
            'collection': collection_id,
            'item': item_id,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 6. Freeze / thaw an entire collection (freeze_collection / thaw_collection)
# --------------------------------------------------------------------------
def freeze_collection(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int):
    """Freeze an entire collection - no item can be transferred/minted (often used as an emergency pause or to "finalize" a collection)"""
    print(f"\n[freeze_collection] Freezing entire collection collection_id={collection_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='freeze_collection',
        call_params={'collection': collection_id}
    )
    return submit(portaldot, keypair, call)


def thaw_collection(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int):
    """Unfreeze an entire collection"""
    print(f"\n[thaw_collection] Unfreezing entire collection collection_id={collection_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='thaw_collection',
        call_params={'collection': collection_id}
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 7. Approve a delegated transfer (approve_transfer) -- similar to ERC721 approve
# --------------------------------------------------------------------------
def approve_transfer(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                      item_id: int, delegate: str):
    """
    The item's owner authorizes `delegate` to transfer the item on their behalf (single item only; only one active delegate at a time).
    """
    print(f"\n[approve_transfer] Approving {delegate} to transfer NFT collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='approve_transfer',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'delegate': delegate,
        }
    )
    return submit(portaldot, keypair, call)


def delegated_transfer(portaldot: SubstrateInterface, delegate_keypair: Keypair, collection_id: int,
                        item_id: int, dest: str):
    """
    The approved account (delegate_keypair) performs the delegated transfer. In pallet_uniques the approved party
    simply calls transfer (no separate transfer_approved call is needed);
    the chain automatically checks whether it is the currently active delegate.
    """
    print(f"\n[delegated transfer] {delegate_keypair.ss58_address} transferring NFT on owner's behalf "
          f"collection_id={collection_id}, item_id={item_id} -> {dest}")
    return transfer_item(portaldot, delegate_keypair, collection_id, item_id, dest)


# --------------------------------------------------------------------------
# 8. Cancel approval (cancel_approval)
# --------------------------------------------------------------------------
def cancel_approval(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                     item_id: int, maybe_check_delegate: str = None):
    """The owner revokes a previous approval to a delegate"""
    print(f"\n[cancel_approval] Revoking NFT approval collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='cancel_approval',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'maybe_check_delegate': maybe_check_delegate,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 9. Metadata / attributes (set_metadata / set_attribute)
# --------------------------------------------------------------------------
def set_metadata(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                  item_id: int, data: bytes, is_frozen: bool = False):
    """
    Set metadata for the item (usually a URI pointing to IPFS or other storage).
    Requires the collection's Admin role and a deposit of MetadataDepositBase + a per-byte deposit.
    """
    print(f"\n[set_metadata] Setting metadata collection_id={collection_id}, item_id={item_id}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='set_metadata',
        call_params={
            'collection': collection_id,
            'item': item_id,
            'data': data,
            'is_frozen': is_frozen,
        }
    )
    return submit(portaldot, keypair, call)


def set_attribute(portaldot: SubstrateInterface, keypair: Keypair, collection_id: int,
                   item_id: int, key: bytes, value: bytes):
    """Set a custom key-value attribute on the item (business fields such as rarity, level, etc.)"""
    print(f"\n[set_attribute] Setting attribute collection_id={collection_id}, item_id={item_id}, key={key}")
    call = portaldot.compose_call(
        call_module='Uniques',
        call_function='set_attribute',
        call_params={
            'collection': collection_id,
            'maybe_item': item_id,
            'key': key,
            'value': value,
        }
    )
    return submit(portaldot, keypair, call)

# --------------------------------------------------------------------------
# 10. Built-in listing marketplace (set_price / buy_item)
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
        call_module='Uniques',
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
        call_module='Uniques',
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
    """Query the collection's details (owner, item count, frozen status, etc.)"""
    result = portaldot.query(module='Uniques', storage_function='Class', params=[collection_id])
    print(f"\n[query] Collection({collection_id}) details: {result.value}")
    return result.value


def query_item_info(portaldot: SubstrateInterface, collection_id: int, item_id: int):
    """Query a single item's info (owner, frozen status, etc.)"""
    result = portaldot.query(module='Uniques', storage_function='Asset', params=[collection_id, item_id])
    print(f"\n[query] Item({collection_id}, {item_id}) info: {result.value}")
    return result.value


def query_item_metadata(portaldot: SubstrateInterface, collection_id: int, item_id: int):
    """Query the item's metadata"""
    result = portaldot.query(module='Uniques', storage_function='InstanceMetadataOf',
                              params=[collection_id, item_id])
    print(f"\n[query] Item({collection_id}, {item_id}) metadata: {result.value}")
    return result.value

def query_item_price(portaldot: SubstrateInterface, collection_id: int, item_id: int):
    """Query the item's current listing price (and whitelisted_buyer, if any)"""
    result = portaldot.query(module='Uniques', storage_function='ItemPriceOf', params=[collection_id, item_id])
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

    # 1) Create the collection (only once; collection_id must not be taken)
    create_collection(portaldot, keypair, COLLECTION_ID, admin=keypair.ss58_address)

    # 2) Mint NFTs (requires Issuer role)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID, owner=keypair.ss58_address)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+1, owner=keypair.ss58_address)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+2, owner=keypair.ss58_address)
    mint_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+3, owner=keypair.ss58_address)

    # 3) Set metadata / attributes (requires Admin role)
    set_metadata(portaldot, keypair, COLLECTION_ID, ITEM_ID, data=b'ipfs://Qm.../metadata.json')
    set_attribute(portaldot, keypair, COLLECTION_ID, ITEM_ID, key=b'test_uniques_key', value=b'test_uniques_value')

    # 4) Regular transfer (the current account must be the item owner)
    transfer_item(portaldot, keypair, COLLECTION_ID, ITEM_ID+1, dest=other_address)

    # 5) Approve someone else to transfer on your behalf
    approve_transfer(portaldot, keypair, COLLECTION_ID, ITEM_ID, delegate=other_address)

    # 6) Delegated transfer by the approved party (must be signed with the delegate's own Keypair; shown here for illustration only)
    # delegate_keypair = Keypair.create_from_mnemonic("DELEGATE_MNEMONIC")
    # delegated_transfer(portaldot, delegate_keypair, COLLECTION_ID, ITEM_ID, dest=other_address)

    # 7) Revoke the approval
    cancel_approval(portaldot, keypair, COLLECTION_ID, ITEM_ID)

    # 8) Freeze / thaw a single item (requires Freezer role)
    freeze_item(portaldot, keypair, COLLECTION_ID, ITEM_ID)
    thaw_item(portaldot, keypair, COLLECTION_ID, ITEM_ID)

    # 9) Freeze / thaw the entire collection (requires Freezer/Admin role)
    freeze_collection(portaldot, keypair, COLLECTION_ID)
    thaw_collection(portaldot, keypair, COLLECTION_ID)

    # 10) Burn an NFT (requires owner or Admin role)
    burn_item(portaldot, keypair, COLLECTION_ID, ITEM_ID, check_owner=keypair.ss58_address)

    # 11) List for sale / buy (built-in simple marketplace)
    set_price(portaldot, keypair, COLLECTION_ID, ITEM_ID+2, price=8*10**NATIVE_POT_DECIMALS)  # list
    query_item_price(portaldot, COLLECTION_ID, ITEM_ID)
    buyer_keypair = Keypair.create_from_mnemonic(BUYER_MNEMONIC)
    buy_item(portaldot, buyer_keypair, COLLECTION_ID, ITEM_ID+2, bid_price=9*10**NATIVE_POT_DECIMALS) # bid price

    set_price(portaldot, keypair, COLLECTION_ID, ITEM_ID+3, price=10*10**NATIVE_POT_DECIMALS)  # list
    set_price(portaldot, keypair, COLLECTION_ID, ITEM_ID+3, price=None)  # delist

    print("\nScript finished.")


if __name__ == '__main__':
    main()
