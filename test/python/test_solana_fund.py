from ragger.backend.interface import RAPDU, RaisePolicy
from ragger.navigator import NavInsID

from .apps.exchange import ExchangeClient, Rate, SubCommand, Errors
from .apps.ethereum import EthereumClient

from .apps.solana import SolanaClient, ErrorType
from .apps.solana_utils import SOL_PACKED_DERIVATION_PATH
from .apps.solana_cmd_builder import SystemInstructionTransfer, Message, verify_signature
from .apps import solana_utils as SOL

from .signing_authority import SigningAuthority, LEDGER_SIGNER

from .utils import ROOT_SCREENSHOT_PATH


# Swap transaction infos for valid ETH <-> SOL exchanges. Tamper the values to generate errors
VALID_FUND_SOL_TX_INFOS = {
    "user_id": "Daft Punk",
    "account_name": "Account 0",
    "in_currency": "SOL",
    "in_amount": SOL.AMOUNT_BYTES,
    "in_address": SOL.FOREIGN_ADDRESS
}

# Helper to validate a FUND transaction by the Exchange app and put the Solana app in front
def valid_fund(backend, navigator, test_name, tx_infos, fees):
    ex = ExchangeClient(backend, Rate.FIXED, SubCommand.FUND)
    partner = SigningAuthority(curve=ex.partner_curve, name="Partner name")

    ex.init_transaction()
    ex.set_partner_key(partner.credentials)
    ex.check_partner_key(LEDGER_SIGNER.sign(partner.credentials))
    ex.process_transaction(tx_infos, fees)
    ex.check_transaction_signature(partner)
    with ex.check_address(payout_signer=LEDGER_SIGNER):
        navigator.navigate_until_text_and_compare(NavInsID.RIGHT_CLICK,
                                                  [NavInsID.BOTH_CLICK],
                                                  "Accept",
                                                  ROOT_SCREENSHOT_PATH,
                                                  test_name)
    ex.start_signing_transaction()


def test_solana_fund_ok(backend, navigator, test_name):
    valid_fund(backend, navigator, test_name, VALID_FUND_SOL_TX_INFOS, SOL.FEES_BYTES)

    instruction: SystemInstructionTransfer = SystemInstructionTransfer(SOL.OWNED_PUBLIC_KEY, SOL.FOREIGN_PUBLIC_KEY, SOL.AMOUNT)
    message: bytes = Message([instruction]).serialize()

    sol = SolanaClient(backend)
    with sol.send_async_sign_message(SOL_PACKED_DERIVATION_PATH, message):
        # Instant rapdu expected
        pass
    signature: bytes = sol.get_async_response().data
    verify_signature(SOL.OWNED_PUBLIC_KEY, message, signature)


def test_solana_fund_wrong_amount(backend, navigator, test_name):
    valid_fund(backend, navigator, test_name, VALID_FUND_SOL_TX_INFOS, SOL.FEES_BYTES)

    instruction: SystemInstructionTransfer = SystemInstructionTransfer(SOL.OWNED_PUBLIC_KEY, SOL.FOREIGN_PUBLIC_KEY, SOL.AMOUNT + 1)
    message: bytes = Message([instruction]).serialize()

    sol = SolanaClient(backend)
    backend.raise_policy = RaisePolicy.RAISE_NOTHING
    with sol.send_async_sign_message(SOL_PACKED_DERIVATION_PATH, message):
        # Instant rapdu expected
        pass
    rapdu: RAPDU = sol.get_async_response()
    print("Received rapdu :", rapdu)
    assert rapdu.status == ErrorType.SOLANA_SUMMARY_FINALIZE_FAILED


def test_solana_fund_wrong_destination(backend, navigator, test_name):
    valid_fund(backend, navigator, test_name, VALID_FUND_SOL_TX_INFOS, SOL.FEES_BYTES)

    instruction: SystemInstructionTransfer = SystemInstructionTransfer(SOL.OWNED_PUBLIC_KEY, SOL.FOREIGN_PUBLIC_KEY_2, SOL.AMOUNT)
    message: bytes = Message([instruction]).serialize()

    sol = SolanaClient(backend)
    backend.raise_policy = RaisePolicy.RAISE_NOTHING
    with sol.send_async_sign_message(SOL_PACKED_DERIVATION_PATH, message):
        # Instant rapdu expected
        pass
    rapdu: RAPDU = sol.get_async_response()
    print("Received rapdu :", rapdu)
    assert rapdu.status == ErrorType.SOLANA_SUMMARY_FINALIZE_FAILED


def test_solana_fund_cancel(backend, navigator, test_name):
    ex = ExchangeClient(backend, Rate.FIXED, SubCommand.FUND)
    partner = SigningAuthority(curve=ex.partner_curve, name="Partner name")

    ex.init_transaction()
    ex.set_partner_key(partner.credentials)
    ex.check_partner_key(LEDGER_SIGNER.sign(partner.credentials))
    ex.process_transaction(VALID_FUND_SOL_TX_INFOS, SOL.FEES_BYTES)
    ex.check_transaction_signature(partner)

    backend.raise_policy = RaisePolicy.RAISE_NOTHING
    with ex.check_address(LEDGER_SIGNER):
        navigator.navigate_until_text_and_compare(NavInsID.RIGHT_CLICK,
                                          [NavInsID.BOTH_CLICK],
                                          "Reject",
                                          ROOT_SCREENSHOT_PATH,
                                          test_name)
    assert ex.get_check_address_response().status == Errors.USER_REFUSED