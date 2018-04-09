__copyright__ = "2018 QChain Inc. All Rights Reserved."
__contact__ = "https://qchain.co/licensing/"
__license__ = "GNU AGPLv3 or commercial, see LICENSE."

'''
    testnet
    -------

    Testnet handler functions.
'''

import binascii
import datetime
import decimal
import json
import math
from qchain import common, nem

# CONFIG
# ------

with open('config.json') as f:
    CONFIG = json.load(f)

MOSAIC_DEFINITION = nem.MosaicDefinition.from_dict(CONFIG['mosaic'])
MESSAGE = nem.Message.from_dict(CONFIG['message'])

# FUNCTIONS
# ---------

def estimate_fee(mosaic):
    '''
    Over-estimate the fee required for a transaction.
    Adapted from:
        https://nemproject.github.io/#transaction-fees
        https://blog.nem.io/nem-updated-0-6-82/

    :param *amounts: Sequence of microXEM (or XEM, etc.) to send.
    '''

    mosaic_fee = nem.calculate_mosaic_fee(MOSAIC_DEFINITION, mosaic)
    message_fee = nem.calculate_message_fee(MESSAGE)

    return mosaic_fee + message_fee


def create_transfer(recipient, amount):
    '''
    Create the transfer transaction (v2) with the mosaics.

    :param recipient: Address to which XQC will be sent.
    :param amount: Number of XQC to send.
    '''

    time_stamp = nem.new_time_stamp()
    mosaic = nem.Mosaic(MOSAIC_DEFINITION.mosaic_id, int(amount))

    return nem.TransferTransaction(
        time_stamp=time_stamp,
        signature='',
        fee=estimate_fee(mosaic),
        type=nem.Transfer,
        deadline=time_stamp + datetime.timedelta(hours=1).seconds,
        version=nem.TestNetworkVersion,
        signer=CONFIG['public_key'],
        relative_version=2,
        amount=0,
        recipient=recipient,
        message=MESSAGE,
        mosaics=[mosaic]
    )


def send_xqc(recipient, amount, node_list, max_amount=None):
    '''
    Send testnet XQC to a NEM address. The sending address is hard-coded
    to a master sending account.

    :param recipient: Address to which XQC will be sent.
    :param amount: Number of XQC to send.
    :param node_list: List of IP addresses for NIS nodes.
    :return: NEM response
    '''

    # parse and validate the input amount
    amount = nem.MicroXem(nem.Xem(amount))
    if max_amount is not None:
        max_amount = nem.MicroXem(nem.Xem(max_amount))
        if amount > max_amount:
            raise ValueError("Requested amount is above maximum.")

    # get parameters
    transfer = create_transfer(recipient, amount)
    public_key = common.SecureString.from_file('key.pub')
    private_key = common.SecureString.from_file('key')

    # get raw byte arrays
    raw_transaction = transfer.to_bytes()
    raw_signature = nem.sign(raw_transaction, public_key,  private_key)
    transaction = binascii.hexlify(raw_transaction).decode('ascii')
    signature = binascii.hexlify(raw_signature).decode('ascii')
    request = nem.RequestAnnounce(transaction, signature)
    result = nem.Error(transfer.time_stamp, "Bad Request", None, 400)

    for node in node_list:
        client = nem.Client(*node)
        hb = client.heartbeat()
        if isinstance(hb, nem.NemRequestResult) and hb.code == 1:
            # request ok, make message
            result = client.transaction.announce(request)
            if not isinstance(request, nem.Error):
                # successful posted the result, return
                return result
            elif result.message == 'FAILURE_INSUFFICIENT_FEE':
                # insufficient fee provided
                return result
            elif result.message == 'FAILURE_INSUFFICIENT_BALANCE':
                # account has insufficient balance for the transaction
                return result

    return result
