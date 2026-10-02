"""
================================================

Dependencies:
    pip install substrate-interface

"""

from substrateinterface import SubstrateInterface, Keypair, ExtrinsicReceipt
from substrateinterface.exceptions import SubstrateRequestException
import substrateinterface.utils.ss58

# --------------------------------------------------------------------------
# Account operations
# --------------------------------------------------------------------------

# Generate a random mnemonic
mnemonic = Keypair.generate_mnemonic()
print('random mnemonic = ', mnemonic)

# Derive address, public key and private key from the mnemonic
mn_keypair = Keypair.create_from_mnemonic(mnemonic)
print('address of random mnemonic = ', mn_keypair.ss58_address)
print('public key of random mnemonic = ', mn_keypair.public_key)
print('private key of random mnemonic = ', mn_keypair.private_key)

# Check whether the address is valid
check = substrateinterface.utils.ss58.is_valid_ss58_address(mn_keypair.ss58_address, valid_ss58_format=42)
print('valid ss58 address ? ', check)

# Derive using a derivation path
hard = 1
soft = 1
path_keypair = Keypair.create_from_uri(mnemonic + "/{}//{}".format(hard, soft))
print('derived account keypair = ', path_keypair)

# Sign data
signature = mn_keypair.sign("Test123")
if mn_keypair.verify("Test123", signature):
    print('signature verified')

print('\n')

# --------------------------------------------------------------------------
# State queries and transaction signing
# --------------------------------------------------------------------------

# Connect to the node
portaldot = SubstrateInterface(
    url = "wss://testnetv3-node.feso-apps.xyz",
    # url="ws://127.0.0.1:9944",
    ss58_format = 42
)

# Query the latest block height and hash
r = portaldot.get_block_header()
print('last block height = ', r['header']['number'])
print('last block hash = ', r['header']['hash'])

# Query the latest finalized block hash
final = portaldot.get_chain_finalised_head()
print('last final block hash = ', final)

# Query block contents
block_content = portaldot.get_block(final)
print('block height = ', block_content['header']['number'])
print('blcok hash = ', block_content['header']['hash'])
print('extrinsics in block: ', block_content['extrinsics'])
print('\n')

# Create an account from an existing mnemonic
# Mnemonic = couch divert chest fan ridge length theory tool ethics soldier frame cabbage
# Address  = 5CtKYqmJRn7Ycqs1kQA6y8XQRGXQBQc5wtZzPjZLd5yLtmBf
keypair = Keypair.create_from_mnemonic('couch divert chest fan ridge length theory tool ethics soldier frame cabbage')

# Get the account balance
result = portaldot.query(
    module='System',
    storage_function='Account',
    params=[keypair.ss58_address]
)
print('account address = ', keypair.ss58_address)
print('account nonce = ', result.value['nonce'])
print('account free balance = ', result.value['data']['free'])

# Transaction
destination_address = '5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY'
call = portaldot.compose_call(
    call_module='Balances',
    call_function='transfer_keep_alive',
    call_params={
        'dest': destination_address,
        'value': 5 * 10 ** 14
    }
)
# Sign the transaction
extrinsic = portaldot.create_signed_extrinsic(call=call, keypair=keypair)
# Get the estimated fee
fee_estimate = portaldot.get_payment_info(call=call, keypair=keypair)
print('sending an balance transfer extrinsic...')
try:
    # Broadcast the transaction
    receipt = portaldot.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    print("extrinsic '{}' sent and included in block '{}'".format(receipt.extrinsic_hash, receipt.block_hash))
    tx_info = ExtrinsicReceipt(portaldot, receipt.extrinsic_hash, receipt.block_hash).extrinsic
    print('data of the extrinsic: ')
    for key, value in tx_info.value.items():
        print(key, value)
except SubstrateRequestException as e:
    print("failed to send: {}".format(e))
print('\n')

# --------------------------------------------------------------------------
# Offline transaction signing
# --------------------------------------------------------------------------

# Build the transaction
online_call = portaldot.compose_call(
    call_module='Balances',
    call_function='transfer_keep_alive',
    call_params={
        'dest': destination_address,
        'value': 2 * 10 ** 14
    }
)
nonce = portaldot.get_account_nonce('5CtKYqmJRn7Ycqs1kQA6y8XQRGXQBQc5wtZzPjZLd5yLtmBf')
signature_payload = portaldot.generate_signature_payload(call=online_call, nonce=nonce)

# Offline signing - this step can be performed on an offline device
offline_keypair = Keypair.create_from_mnemonic('couch divert chest fan ridge length theory tool ethics soldier frame cabbage')
offline_signature = offline_keypair.sign(signature_payload)

# Broadcast the transaction
online_keypair = Keypair(ss58_address='5CtKYqmJRn7Ycqs1kQA6y8XQRGXQBQc5wtZzPjZLd5yLtmBf')
extrinsic = portaldot.create_signed_extrinsic(
    call=online_call,
    keypair=online_keypair,
    nonce=nonce,
    signature=offline_signature
)
result = portaldot.submit_extrinsic(extrinsic=extrinsic, wait_for_inclusion=True)
print('id of off-line signed extrinsic = ', result.get_extrinsic_identifier())
print('hash of off-line signed extrinsic = ', result.extrinsic_hash)
