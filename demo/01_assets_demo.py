#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================

Dependencies:
    pip install substrate-interface

Coverage:
    1. create            - Create an asset (Asset Admin/Owner)
    2. mint              - Mint additional units
    3. burn              - Burn units
    4. transfer          - Regular transfer
    5. freeze            - Freeze an account's asset balance
    6. thaw              - Unfreeze an account
    7. approve_transfer  - Authorize someone else to transfer on your behalf (approve)
    8. transfer_approved - The approved party executes the transfer (like ERC20 transferFrom)
    9. cancel_approval   - Revoke the approval

Notes:
    - Most management operations in pallet_assets (create/mint/burn/freeze/thaw, etc.) require the signing account to hold the corresponding role (Owner/Issuer/Admin/Freezer); otherwise the transaction is rejected with BadOrigin.
    - This script is for demonstration only. Before any real use, test thoroughly on the testnet and verify details such as decimals and fees yourself.
    - Never hard-code private keys/mnemonics in production code.
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

ASSET_ID = 3
DECIMALS = 18

def get_portaldot() -> SubstrateInterface:
    """Connect to the node"""
    portaldot = SubstrateInterface(url=NODE_URL)
    print(f"[Connected] Chain: {portaldot.chain}  Node version: {portaldot.version}")
    return portaldot


def get_keypair() -> Keypair:
    """Create the signing account from the mnemonic"""
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
# 1. Create an asset (create)
# --------------------------------------------------------------------------
def create_asset(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, admin: str, min_balance: int = 1):
    """
    Create a new asset.
    admin: the asset's admin address (the default account holding mint/burn/freeze permissions; Issuer/Admin/Freezer can later be assigned via set_team, and name/symbol/decimals via set_metadata)
    min_balance: the minimum balance an account must hold of this asset (below this, the account is treated as a "dust account" and reaped)
    """
    print(f"\n[create] Creating asset id={asset_id}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='create',
        call_params={
            'id': asset_id,
            'admin': admin,
            'min_balance': min_balance,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 2. Mint (mint)
# --------------------------------------------------------------------------
def mint_asset(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, beneficiary: str, amount: int):
    """
    The Issuer account mints `amount` units of the asset to `beneficiary` (scaled by decimals, not human-readable units).
    """
    print(f"\n[mint] Minting to {beneficiary}: asset id={asset_id}, amount={amount}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='mint',
        call_params={
            'id': asset_id,
            'beneficiary': beneficiary,
            'amount': amount * 10 ** DECIMALS,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 3. Burn (burn)
# --------------------------------------------------------------------------
def burn_asset(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, who: str, amount: int):
    """
    The Admin account burns `amount` units of the asset held by `who`.
    """
    print(f"\n[burn] Burning from {who}: asset id={asset_id}, amount={amount}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='burn',
        call_params={
            'id': asset_id,
            'who': who,
            'amount': amount * 10 ** DECIMALS,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 4. Transfer (transfer)
# --------------------------------------------------------------------------
def transfer_asset(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, dest: str, amount: int, keep_alive: bool = True):
    """
    Regular transfer between holders.
    With keep_alive=True, transfer_keep_alive is used so the sender's balance does not drop below min_balance.
    """
    func = 'transfer_keep_alive' if keep_alive else 'transfer'
    print(f"\n[{func}] Transferring asset id={asset_id} -> {dest}, amount={amount}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function=func,
        call_params={
            'id': asset_id,
            'target': dest,
            'amount': amount * 10 ** DECIMALS,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 5 & 6. Freeze / thaw an account (freeze / thaw)
# --------------------------------------------------------------------------
def freeze_account(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, who: str):
    """
    The Freezer account freezes `who`'s balance of this asset (it cannot be transferred out while frozen).
    """
    print(f"\n[freeze] Freezing account {who} for asset id={asset_id}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='freeze',
        call_params={
            'id': asset_id,
            'who': who,
        }
    )
    return submit(portaldot, keypair, call)


def thaw_account(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, who: str):
    """Unfreeze `who`'s balance of this asset"""
    print(f"\n[thaw] Unfreezing account {who} for asset id={asset_id}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='thaw',
        call_params={
            'id': asset_id,
            'who': who,
        }
    )
    return submit(portaldot, keypair, call)


def freeze_asset(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int):
    """Freeze the entire asset (no holder can transfer; typically used as an emergency pause)"""
    print(f"\n[freeze_asset] Freezing entire asset id={asset_id}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='freeze_asset',
        call_params={'id': asset_id}
    )
    return submit(portaldot, keypair, call)


def thaw_asset(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int):
    """Unfreeze the entire asset"""
    print(f"\n[thaw_asset] Unfreezing entire asset id={asset_id}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='thaw_asset',
        call_params={'id': asset_id}
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 7. Approve (approve_transfer) -- similar to ERC20 approve
# --------------------------------------------------------------------------
def approve_transfer(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, delegate: str, amount: int):
    """
    The asset holder (the keypair's account) authorizes `delegate` to transfer out the holder's assets up to a total of `amount`.
    Note: an AssetDeposit must be reserved as a storage deposit (approvals occupy on-chain storage).
    """
    print(f"\n[approve_transfer] Approving {delegate} to transfer, id={asset_id}, amount={amount}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='approve_transfer',
        call_params={
            'id': asset_id,
            'delegate': delegate,
            'amount': amount * 10 ** DECIMALS,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# 8. Delegated transfer (transfer_approved) -- similar to ERC20 transferFrom
# --------------------------------------------------------------------------
def transfer_approved(portaldot: SubstrateInterface, delegate_keypair: Keypair, asset_id: int, owner: str, destination: str, amount: int):
    """
    Initiated by the approved account (delegate_keypair): deducts `amount` of the asset from `owner`
    and sends it to `destination`. Requires that `owner` previously approved a sufficient amount to the delegate via approve_transfer.
    """
    print(f"\n[transfer_approved] {delegate_keypair.ss58_address} transferring on behalf of {owner} to {destination}, " f"id={asset_id}, amount={amount}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='transfer_approved',
        call_params={
            'id': asset_id,
            'owner': owner,
            'destination': destination,
            'amount': amount * 10 ** DECIMALS,
        }
    )
    return submit(portaldot, delegate_keypair, call)


# --------------------------------------------------------------------------
# 9. Cancel approval (cancel_approval)
# --------------------------------------------------------------------------
def cancel_approval(portaldot: SubstrateInterface, keypair: Keypair, asset_id: int, delegate: str):
    """The asset holder revokes a previous approval to `delegate` and gets the deposit back"""
    print(f"\n[cancel_approval] Revoking approval for {delegate}, id={asset_id}")
    call = portaldot.compose_call(
        call_module='Assets',
        call_function='cancel_approval',
        call_params={
            'id': asset_id,
            'delegate': delegate,
        }
    )
    return submit(portaldot, keypair, call)


# --------------------------------------------------------------------------
# Helpers: query asset info / account balance
# --------------------------------------------------------------------------
def query_asset_info(portaldot: SubstrateInterface, asset_id: int):
    """Query the asset's details (total supply, owner, status, etc.)"""
    result = portaldot.query(module='Assets', storage_function='Asset', params=[asset_id])
    print(f"\n[query] Asset({asset_id}) details: {result.value}")
    return result.value


def query_asset_balance(portaldot: SubstrateInterface, asset_id: int, account: str):
    """Query an account's balance and frozen status for the given asset"""
    result = portaldot.query(module='Assets', storage_function='Account', params=[asset_id, account])
    print(f"\n[query] {account} balance of Asset({asset_id}): {result.value}")
    return result.value


def query_approval(portaldot: SubstrateInterface, asset_id: int, owner: str, delegate: str):
    """Query the remaining amount of an approval (owner -> delegate)"""
    result = portaldot.query(module='Assets', storage_function='Approvals', params=[asset_id, owner, delegate])
    print(f"\n[query] Approval amount {owner} -> {delegate}: {result.value}")
    return result.value


# --------------------------------------------------------------------------
# Main flow example
# --------------------------------------------------------------------------
def main():
    portaldot = get_portaldot()
    keypair = get_keypair()
    print(f"Current signing account: {keypair.ss58_address}")

    # Another test account used in the example (as mint beneficiary / approved delegate / transfer target, etc.)
    # In production, replace with the addresses you actually need to interact with
    other_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

    # --- Query existing asset info (no permissions required; anyone can query) ---
    query_asset_info(portaldot, ASSET_ID)
    query_asset_balance(portaldot, ASSET_ID, keypair.ss58_address)

    # --- Uncomment the operations below as needed (most require the corresponding management role, otherwise BadOrigin) ---

    # 1) Create the asset (the Asset ID must not be taken yet)
    # create_asset(portaldot, keypair, ASSET_ID, admin=keypair.ss58_address, min_balance=1)

    # 2) Mint (requires Issuer role)
    mint_asset(portaldot, keypair, ASSET_ID, beneficiary=keypair.ss58_address, amount=10000)
    mint_asset(portaldot, keypair, ASSET_ID, beneficiary=other_address, amount=8000)

    # 3) Regular transfer
    transfer_asset(portaldot, keypair, ASSET_ID, dest=other_address, amount=1_000, keep_alive=True)

    # 4) Approve someone else to transfer on your behalf
    approve_transfer(portaldot, keypair, ASSET_ID, delegate=other_address, amount=500)
    query_approval(portaldot, ASSET_ID, owner=keypair.ss58_address, delegate=other_address)

    # 5) Delegated transfer by the approved party (must be signed with the delegate's own Keypair; shown here for illustration only)
    # delegate_keypair = Keypair.create_from_mnemonic("DELEGATE_MNEMONIC")
    # transfer_approved(portaldot, delegate_keypair, ASSET_ID, owner=keypair.ss58_address, destination=other_address, amount=200)

    # 6) Revoke the approval
    cancel_approval(portaldot, keypair, ASSET_ID, delegate=other_address)
    query_approval(portaldot, ASSET_ID, owner=keypair.ss58_address, delegate=other_address)

    # 7) Freeze / thaw a specific account (requires Freezer role)
    freeze_account(portaldot, keypair, ASSET_ID, who=other_address)
    thaw_account(portaldot, keypair, ASSET_ID, who=other_address)

    # 8) Freeze / thaw the entire asset (requires Freezer/Admin role)
    freeze_asset(portaldot, keypair, ASSET_ID)
    thaw_asset(portaldot, keypair, ASSET_ID)

    # 9) Burn (requires Admin role)
    burn_asset(portaldot, keypair, ASSET_ID, who=other_address, amount=500)

    print("\nScript finished.")


if __name__ == '__main__':
    main()
