# -*- coding: utf-8 -*-
"""
Use py substrate-interface to interact with the Storage.sol contract deployed on revive-dev-node

Covers:
  1. Account mapping (H160 <-> AccountId32)
  2. Reading data: retrieve() -- read-only simulated call via ReviveApi_call
  3. Data-change dry-run: store(num) -- also via ReviveApi_call, but not persisted; used to estimate gas / check whether it would fail
  4. Real data-change call: store(num) -- build a Revive.call extrinsic, sign it and submit it on-chain

Dependencies:
  pip install substrate-interface eth-abi eth-utils

Notes:

  - Replace CONTRACT_ADDRESS with the contract's H160 address obtained after deploying with Remix (0x-prefixed, 20 bytes).

"""

from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.utils.ss58 import ss58_decode
from eth_utils import keccak
import eth_abi

# Whether to use the fallback (hand-written SCALE encode/decode + raw state_call)
# If substrate.runtime_call("ReviveApi", "call", ...) reports "not found" / cannot find ReviveApi,
# turn this switch on to bypass runtime_call().
USE_RAW_STATE_CALL_FALLBACK = True


# ------------------------------------------------------------------
# Hand-written SCALE encode/decode (used when metadata does not auto-detect ReviveApi)
# ------------------------------------------------------------------


def encode_compact_u64(value: int) -> bytes:
    if value < 0:
        raise ValueError("Compact<u64> cannot be negative")
    if value < (1 << 6):
        return bytes([value << 2])
    if value < (1 << 14):
        return ((value << 2) | 0x01).to_bytes(2, "little")
    if value < (1 << 30):
        return ((value << 2) | 0x02).to_bytes(4, "little")
    if value < (1 << 62):
        return ((value << 2) | 0x03).to_bytes(8, "little")
    raise ValueError("Compact<u64> overflow")


def encode_compact_u32(value: int) -> bytes:
    if value < 0:
        raise ValueError("Compact<u32> cannot be negative")
    if value < (1 << 6):
        return bytes([value << 2])
    if value < (1 << 14):
        return ((value << 2) | 0x01).to_bytes(2, "little")
    if value < (1 << 30):
        return ((value << 2) | 0x02).to_bytes(4, "little")
    raise ValueError("Compact<u32> overflow")


def encode_bytes(data: bytes) -> bytes:
    return encode_compact_u32(len(data)) + data


def encode_weight(ref_time: int, proof_size: int) -> bytes:
    return encode_compact_u64(ref_time) + encode_compact_u64(proof_size)


def encode_revive_call_params(
    origin_ss58: str,
    dest_h160: str,
    value: int,
    gas_limit,
    storage_deposit_limit,
    input_data: bytes,
) -> bytes:
    """
    Manually SCALE-encode the parameters in ReviveApi::call order:
    origin: AccountId32,
    dest: H160,
    value: u128,
    gas_limit: Option<Weight{ref_time: Compact<u64>, proof_size: Compact<u64>}>,
    storage_deposit_limit: Option<u128>,
    input_data: Vec<u8>
    """

    result = bytearray()

    # origin: AccountId32 (32 bytes)
    pubkey_hex = ss58_decode(origin_ss58)
    origin = bytes.fromhex(pubkey_hex.removeprefix("0x"))
    if len(origin) != 32:
        raise ValueError(f"origin must be 32 bytes, got {len(origin)}")
    result += origin

    # dest: H160 (20 bytes)
    dest = bytes.fromhex(dest_h160.removeprefix("0x"))
    if len(dest) != 20:
        raise ValueError(f"dest must be 20 bytes, got {len(dest)}")
    result += dest

    # value: u128, 16 bytes little-endian
    result += value.to_bytes(16, "little")

    # Option<Weight>
    if gas_limit is None:
        result += b"\x00"
    else:
        ref_time, proof_size = gas_limit
        result += b"\x01"
        result += encode_weight(ref_time, proof_size)

    # Option<u128>
    if storage_deposit_limit is None:
        result += b"\x00"
    else:
        result += b"\x01"
        result += storage_deposit_limit.to_bytes(16, "little")

    # Bytes
    result += encode_bytes(input_data)

    return bytes(result)


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        b = self.data[self.pos : self.pos + n]
        self.pos += n
        return b

    def u8(self) -> int:
        return self.take(1)[0]

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "little")

    def u128(self) -> int:
        return int.from_bytes(self.take(16), "little")

    def compact(self) -> int:
        first = self.u8()
        mode = first & 0b11
        if mode == 0b00:  # single-byte
            return first >> 2
        elif mode == 0b01:  # two-byte
            second = self.u8()
            return (first | (second << 8)) >> 2
        elif mode == 0b10:  # four-byte
            rest = self.take(3)
            val = first | (rest[0] << 8) | (rest[1] << 16) | (rest[2] << 24)
            return val >> 2
        else:  # big-integer mode
            length = (first >> 2) + 4
            return int.from_bytes(self.take(length), "little")

    def weight(self) -> dict:
        return {"ref_time": self.compact(), "proof_size": self.compact()}

    def storage_deposit(self) -> dict:
        tag = self.u8()
        amount = self.u128()
        kind = "Refund" if tag == 0 else "Charge"
        return {kind: amount}

    def bytes_vec(self) -> bytes:
        length = self.compact()
        return self.take(length)


def decode_revive_call_result(raw_hex: str) -> dict:
    """
    Decode the SCALE-encoded return value of `ReviveApi_call`
    (the runtime API behind api.call.dryRun / api.rpc.state.call("ReviveApi_call", ...).

    Rust type (pallet-revive, current):

        pub struct ContractResult<R, Balance> {
            pub weight_consumed: Weight,        // { ref_time: Compact<u64>, proof_size: Compact<u64> }
            pub weight_required: Weight,        // { ref_time: Compact<u64>, proof_size: Compact<u64> }
            pub storage_deposit: StorageDeposit<Balance>,      // enum: 0=Refund(u128), 1=Charge(u128)
            pub max_storage_deposit: StorageDeposit<Balance>,  // enum: 0=Refund(u128), 1=Charge(u128)
            pub gas_consumed: Balance,          // plain u128 (16 bytes LE)
            pub result: Result<R, DispatchError>,
        }

        // R = ExecReturnValue for a `call`
        pub struct ExecReturnValue {
            pub flags: u32,      // plain 4 bytes LE
            pub data: Vec<u8>,   // Compact<u32> length + raw bytes
        }
    """

    hex_str = raw_hex.strip()
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]
    if len(hex_str) % 2 == 1:
        # tolerate a stray extra/missing nibble picked up when copy-pasting;
        # trailing bytes are documented as safe to ignore for this type anyway
        hex_str = hex_str[:-1]
    r = Reader(bytes.fromhex(hex_str))

    out = {}
    out["weightConsumed"] = r.weight()
    out["weightRequired"] = r.weight()
    out["storageDeposit"] = r.storage_deposit()
    out["maxStorageDeposit"] = r.storage_deposit()
    out["gasConsumed"] = r.u128()

    result_tag = r.u8()   # 0 = Ok, 1 = Err
    if result_tag == 0:
        flags = r.u32()
        data = r.bytes_vec()
        out["result"] = {
            "Ok": {
                "flags": {"bits": flags},
                "data": "0x" + data.hex(),
            }
        }
    else:
        # DispatchError decoding omitted here - add if you need to decode reverts
        out["result"] = {"Err": "DispatchError (raw bytes follow, not decoded here)"}

    out["_bytes_consumed"] = r.pos
    out["_bytes_total"] = len(r.data)
    return out


# ------------------------------------------------------------------
# Basic configuration
# ------------------------------------------------------------------

# NODE_WS_URL = "ws://127.0.0.1:9944"
NODE_WS_URL = "wss://testnetv3-node.feso-apps.xyz"

CONTRACT_ADDRESS = (
    "0x32514F81C9FA7D61A0f799Bf87bB432F27CEA881"  # TODO: replace with the actual contract address
)

# Development account (revive-dev-node pre-funds //Alice by default)
keypair = Keypair.create_from_uri("//Alice")

portaldot = SubstrateInterface(url=NODE_WS_URL)


# ------------------------------------------------------------------
# Utility functions: encode function call data per the Solidity ABI rules
# ------------------------------------------------------------------


def encode_call(signature: str, types: list, values: list) -> bytes:
    """
    signature: e.g. "store(uint256)" / "retrieve()"
    types:     e.g. ["uint256"]
    values:    e.g. [123]
    """
    selector = keccak(text=signature)[:4]
    encoded_params = eth_abi.encode(types, values) if types else b""
    return selector + encoded_params


def decode_result(types: list, data_hex: str):
    raw = bytes.fromhex(data_hex[2:] if data_hex.startswith("0x") else data_hex)
    return eth_abi.decode(types, raw)


# ------------------------------------------------------------------
# 0. Account mapping: AccountId32 -> H160
# ------------------------------------------------------------------


def ensure_account_mapped():
    """
    pallet-revive requires accounts taking part in contract calls to first establish an AccountId32 <-> H160 mapping;
    otherwise the origin cannot act as a caller under EVM semantics. This only needs to be done once; if already mapped
    it will error/be ignored, so a simple try/except is used as a safeguard.
    """
    call = portaldot.compose_call(
        call_module="Revive",
        call_function="map_account",
        call_params={},
    )
    extrinsic = portaldot.create_signed_extrinsic(call=call, keypair=keypair)
    try:
        receipt = portaldot.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        print("Account mapping result:", receipt.is_success)
    except Exception as e:
        # If already mapped, the node usually reports something like AccountAlreadyMapped - safe to ignore
        print("map_account info (ignore if already mapped):", e)


# ------------------------------------------------------------------
# 1. Reading data: retrieve()  -- read-only, simulated via the Runtime API
# ------------------------------------------------------------------


def _revive_api_call(
    dest: str, value: int, gas_limit, storage_deposit_limit, calldata: bytes
) -> dict:
    """
    Unified wrapper: prefer runtime_call();
    on failure / when disabled, fall back to hand-written SCALE encode/decode + raw state_call.
    """
    if not USE_RAW_STATE_CALL_FALLBACK:
        result = portaldot.runtime_call(
            "ReviveApi",
            "call",
            [
                keypair.ss58_address,
                dest,
                value,
                gas_limit,
                storage_deposit_limit,
                calldata,
            ],
        )
        return result.value

    params_hex = (
        "0x"
        + encode_revive_call_params(
            keypair.ss58_address,
            dest,
            value,
            gas_limit,
            storage_deposit_limit,
            calldata,
        ).hex()
    )

    raw_response = portaldot.rpc_request("state_call", ["ReviveApi_call", params_hex])
    raw_hex = raw_response["result"]
    return decode_revive_call_result(raw_hex)


def read_number():
    calldata = encode_call("retrieve()", [], [])

    value = _revive_api_call(CONTRACT_ADDRESS, 0, None, None, calldata)
    print("retrieve() raw return:", value)

    if "api_error_raw" in value:
        print("Runtime API call itself failed (ApiError), raw bytes:", value["api_error_raw"])
        return None

    exec_result = value["result"]
    if "Ok" in exec_result:
        data_hex = exec_result["Ok"]["data"]
        number = decode_result(["uint256"], data_hex)[0]
        print("On-chain number =", number)
        return number
    else:
        print(
            "Contract call failed/reverted, raw remaining bytes:",
            exec_result.get("Err_raw_remaining") or exec_result.get("Err"),
        )
        return None


# ------------------------------------------------------------------
# 2. Data-change dry-run: store(num) -- not persisted, simulation only; used to estimate gas / check for revert
# ------------------------------------------------------------------


def dry_run_store(num: int):
    calldata = encode_call("store(uint256)", ["uint256"], [num])

    value = _revive_api_call(CONTRACT_ADDRESS, 0, None, None, calldata)
    print("dry-run store() raw return:", value)

    if "api_error_raw" in value:
        print("Runtime API call itself failed (ApiError), raw bytes:", value["api_error_raw"])
        return None, None

    weight_required = value.get("weightRequired")
    storage_deposit = value.get("storageDeposit")
    exec_result = value["result"]

    if "Ok" in exec_result:
        print("Simulation succeeded, estimated weight_required =", weight_required)
        print("Estimated storage_deposit =", storage_deposit)
        return weight_required, storage_deposit
    else:
        print(
            "Execution would fail:",
            exec_result.get("Err_raw_remaining") or exec_result.get("Err"),
        )
        return None, None


# ------------------------------------------------------------------
# 3. Real data-change call: store(num) -- build the extrinsic, sign it and submit on-chain
# ------------------------------------------------------------------


def real_store(num: int):
    calldata = encode_call("store(uint256)", ["uint256"], [num])

    # Dry-run first to get the required gas_limit (Weight) and storage_deposit_limit, instead of hard-coding values
    weight_required, storage_deposit = dry_run_store(num)
    if weight_required is None:
        print("Dry-run did not pass, aborting the real call")
        return None

    # When using runtime_call(), weight_required is usually {"ref_time": ..., "proof_size": ...}
    # When using the hand-written fallback it is a (ref_time, proof_size) tuple; normalize to the dict form compose_call expects
    if isinstance(weight_required, dict):
        weight_limit = weight_required
    else:
        ref_time, proof_size = weight_required
        weight_limit = {"ref_time": ref_time, "proof_size": proof_size}

    # storage_deposit generally looks like {"Charge": amount} or {"Refund": amount}
    storage_deposit_limit = storage_deposit.get("Charge", 0) if storage_deposit else 0

    call = portaldot.compose_call(
        call_module="Revive",
        call_function="call",
        call_params={
            "dest": CONTRACT_ADDRESS,
            "value": 0,
            "weight_limit": weight_limit,
            "storage_deposit_limit": storage_deposit_limit,
            "data": calldata,
        },
    )

    extrinsic = portaldot.create_signed_extrinsic(call=call, keypair=keypair)
    receipt = portaldot.submit_extrinsic(extrinsic, wait_for_inclusion=True)

    print("Real call succeeded:", receipt.is_success)
    print("extrinsic hash:", receipt.extrinsic_hash)

    for event in receipt.triggered_events:
        print("Event:", event.value)

    return receipt


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

if __name__ == "__main__":
    ensure_account_mapped()

    print("\n=== 1. Read current value ===")
    read_number()

    print("\n=== 2. dry-run store(42) ===")
    dry_run_store(42)

    print("\n=== 3. Real call store(42) ===")
    real_store(42)

    print("\n=== 4. Read again to confirm the update ===")
    read_number()
