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
import boto3
import database
from qchain import common, nem

# CONFIG
# ------

with open('config.json') as f:
    CONFIG = json.load(f)

TRANSFER_MAX_AMOUNT = nem.MicroXem(nem.Xem(CONFIG['transfer_maximum_amount']))
DAILY_MAX_AMOUNT = nem.MicroXem(nem.Xem(CONFIG['daily_maximum_amount']))
MOSAIC_DEFINITION = nem.MosaicDefinition.from_dict(CONFIG['mosaic'])
MESSAGE = nem.Message.from_dict(CONFIG['message'])

SSM = boto3.client('ssm', region_name='us-east-1')
TESTNET_DB = database.TestnetTable()

# ERRORS
# ------


def bad_request_error():
    '''Return a bad request.'''

    return nem.Error(
        nem.new_time_stamp(),
        "BAD_REQUEST",
        None,
        400
    )


def invalid_amount_error():
    '''Return am invalid amount error.'''

    return nem.Error(
        nem.new_time_stamp(),
        "FAILURE_INVALID_AMOUNT",
        "Amount must be greater than 0.",
        400
    )


def daily_max_error():
    '''Return a bad request.'''

    return nem.Error(
        nem.new_time_stamp(),
        "FAILURE_DAILY_MAX_EXCEEDED",
        None,
        400
    )


def transfer_max_error():
    '''Return a bad request.'''

    return nem.Error(
        nem.new_time_stamp(),
        "FAILURE_TRANSFER_MAX_EXCEEDED",
        None,
        400
    )

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


def send_xqc(recipient, amount, node_list):
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
    address_total = nem.MicroXem(nem.Xem(TESTNET_DB.get(recipient, 0)))
    daily_total = nem.MicroXem(nem.Xem(TESTNET_DB.total_by_date()))
    if amount <= nem.MicroXem(0):
        return invalid_amount_error()
    elif address_total + amount > TRANSFER_MAX_AMOUNT:
        return transfer_max_error()
    elif daily_total > DAILY_MAX_AMOUNT:
        return daily_max_error()

    # get parameters
    transfer = create_transfer(recipient, amount)
    public_key = binascii.unhexlify(CONFIG['public_key'])
    secret = SSM.get_parameter(Name='qchainNemPrivateKey', WithDecryption=True)
    private_key = binascii.unhexlify(secret['Parameter']['Value'])

    # get raw byte arrays
    raw_transaction = transfer.to_bytes()
    raw_signature = nem.sign(raw_transaction, public_key,  private_key)
    transaction = binascii.hexlify(raw_transaction).decode('ascii')
    signature = binascii.hexlify(raw_signature).decode('ascii')
    request = nem.RequestAnnounce(transaction, signature)
    result = bad_request_error()

    for node in node_list:
        client = nem.Client(*node)
        hb = client.heartbeat()
        if isinstance(hb, nem.NemRequestResult) and hb.code == 1:
            # request ok, make message
            result = client.transaction.announce(request)
            if not isinstance(request, nem.Error):
                # successful posted the result, return
                TESTNET_DB.update(recipient, int(nem.Xem(amount)))
                return result
            elif result.message == 'FAILURE_INSUFFICIENT_FEE':
                # insufficient fee provided
                return result
            elif result.message == 'FAILURE_INSUFFICIENT_BALANCE':
                # account has insufficient balance for the transaction
                return result

    return result
