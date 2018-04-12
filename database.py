__copyright__ = "2018 QChain Inc. All Rights Reserved."
__contact__ = "https://qchain.co/licensing/"
__license__ = "GNU AGPLv3 or commercial, see LICENSE."

'''
    database
    --------

    Create the database table for the testnet handler.
'''

import datetime
import decimal
import boto3
from boto3.dynamodb.conditions import Key

# CONSTANTS
# ---------

DYNAMODB = boto3.resource('dynamodb', region_name='us-east-1')

# HELPERS
# -------

def current_date():
    '''Get the current date as an integer.'''

    date = datetime.datetime.now()
    return date.year * 10000 + date.month * 100 + date.day

# OBJECTS
# -------


class TestnetTable(object):
    '''Table for the testnet logic.'''

    def __init__(self, create=False):
        if create:
            self.create()
        else:
            self.table = DYNAMODB.Table('TestNet')

    # PUBLIC

    def create(self):
        '''Create the testnet XQC table.'''

        self.table = DYNAMODB.create_table(
            TableName='TestNet',
            KeySchema=[
                {
                    'AttributeName': 'address',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'date',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'address',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'date',
                    'AttributeType': 'N'
                }

            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            }
        )

    def delete(self):
        '''Delete the testnet table.'''

        self.table.delete()

    def put(self, address, amount):
        '''Put a amount into the database.'''

        return self.table.put_item(Item=self._item(address, amount))

    def update(self, address, amount):
        '''Update a amount in the database by address and amount.'''

        response = self.table.update_item(
            Key=self._key(address),
            UpdateExpression="set amount = if_not_exists(amount, :zero) + :val",
            ExpressionAttributeValues={
                ':val': decimal.Decimal(amount),
                ':zero': decimal.Decimal(0),
            },
            ReturnValues="UPDATED_NEW"
        )
        return response['Attributes']['amount']

    def get(self, address):
        '''Return a amount in the database by address.'''

        return self.table.get_item(Key=self._key(address))['Item']['amount']

    def cumulative_get(self, address):
        return sum(i['amount'] for i in self._query(address))

    # PRIVATE

    @staticmethod
    def _key(address):
        return {
            'address': address,
            'date': current_date()
        }

    @staticmethod
    def _item(address, amount):
        return {
            'address': address,
            'date': current_date(),
            'amount': decimal.Decimal(amount)
        }

    def _query(self, address):
        '''Query the table for all items at address.'''

        condition = Key('address').eq(address)
        return self.table.query(KeyConditionExpression=condition)['Items']
