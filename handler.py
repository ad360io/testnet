__copyright__ = "2018 QChain Inc. All Rights Reserved."
__contact__ = "https://qchain.co/licensing/"
__license__ = "GNU AGPLv3 or commercial, see LICENSE."

'''
    handler
    -------

    Handler code for testnet XQC functions.
'''

import json
import testnet


# FUNCTIONS
# ---------


def request_error(exception):
    '''Format an internal server error to a diagnostic message.'''

    return {
        "statusCode": 500,
        "body": json.dumps({
            "message": "Internal server error.",
            # TODO: fix
            "error": str(exception) #type(exception).__name__
        })
    }


def send_testnet_xqc(event, context):
    '''Handler to send testnet XQC to a custom address.'''

    parameters = event['queryStringParameters']
    try:
        address = parameters['address']
        amount = parameters.get('amount', testnet.CONFIG['default_transfer_amount'])
        max_amount = testnet.CONFIG['maximum_transfer_amount']
        node_list = parameters.get('nodeList', testnet.CONFIG['node_list'])
        body = testnet.send_xqc(address, amount, node_list, max_amount)

    except Exception as exception:
        return request_error(exception)

    response = {
        "statusCode": 200,
        "body": body.to_json()
    }

    return response
