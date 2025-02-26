import base64
import json
import os
import urllib
import unittest
from datetime import datetime
from urllib.request import Request, urlopen

import parse
from behave import given, when, then, register_type, step  # pylint: disable=no-name-in-module

from algosdk.future import transaction
from algosdk import account, encoding, error, mnemonic
from algosdk.v2client import *
from algosdk.v2client.models import DryrunRequest, DryrunSource, \
    Account, Application, ApplicationLocalState
from algosdk.error import AlgodHTTPError, IndexerHTTPError
from algosdk.testing.dryrun import DryrunTestCaseMixin

from test.steps.steps import token as daemon_token
from test.steps.steps import algod_port

@parse.with_pattern(r".*")
def parse_string(text):
    return text


register_type(MaybeString=parse_string)

@parse.with_pattern(r"true|false")
def parse_bool(value):
    if value not in ("true", "false"):
        raise ValueError("Unknown value for include_all: {}".format(value))
    return value == "true"

register_type(MaybeBool=parse_bool)

@given("mock server recording request paths")
def setup_mockserver(context):
    context.url = "http://127.0.0.1:" + str(context.path_server_port)
    context.acl = algod.AlgodClient("algod_token", context.url)
    context.icl = indexer.IndexerClient("indexer_token", context.url)


@given('mock http responses in "{jsonfiles}" loaded from "{directory}"')
def mock_response(context, jsonfiles, directory):
    context.url = "http://127.0.0.1:" + str(context.response_server_port)
    context.acl = algod.AlgodClient("algod_token", context.url)
    context.icl = indexer.IndexerClient("indexer_token", context.url)

    # The mock server writes this response to a file, on a regular request
    # that file is read.
    # It's an interesting approach, but currently doesn't support setting
    # the content type, or different return codes. This will require a bit
    # of extra work when/if we support the different error cases.
    #
    # Take a look at 'environment.py' to see the mock servers.
    req = Request(context.url + "/mock/" + directory + "/" + jsonfiles, method="GET")
    urlopen(req)


@given('mock http responses in "{filename}" loaded from "{directory}" with status {status}.')
def step_impl(context, filename, directory, status):
    context.expected_status_code = int(status)
    with open("test/features/resources/mock_response_status", "w") as f:
        f.write(status)
    mock_response(context, filename, directory)
    f = open("test/features/resources/mock_response_path", "r")
    mock_response_path = f.read()
    f.close()
    f = open("test/features/resources/" + mock_response_path, "r")
    expected_mock_response = f.read()
    f.close()
    expected_mock_response = bytes(expected_mock_response, "ascii")
    context.expected_mock_response = json.loads(expected_mock_response)

def validate_error(context, err):
    if context.expected_status_code != 200:
        if context.expected_status_code == 500:
            assert context.expected_mock_response == json.loads(err.args[0])
        else:
            raise NotImplementedError("test does not know how to validate status code " + context.expected_status_code)
    else:
        raise err


@when('we make any "{client}" call to "{endpoint}".')
def step_impl(context, client, endpoint):
    # with the current implementation of mock responses, there is no need to do an 'endpoint' lookup
    if client == "indexer":
        try:
            context.response = context.icl.health()
        except error.IndexerHTTPError as err:
            validate_error(context, err)
    elif client == "algod":
        try:
            context.response = context.acl.status()
        except error.AlgodHTTPError as err:
            validate_error(context, err)
    else:
        raise NotImplementedError('did not recognize client "' + client + '"')


@then('the parsed response should equal the mock response.')
def step_impl(context):
    if context.expected_status_code == 200:
        assert context.expected_mock_response == context.response


@when('we make a Pending Transaction Information against txid "{txid}" with format "{response_format}"')
def pending_txn_info(context, txid, response_format):
    context.response = context.acl.pending_transaction_info(txid, response_format=response_format)


@when('we make a Pending Transaction Information with max {max} and format "{response_format}"')
def pending_txn_with_max(context, max, response_format):
    context.response = context.acl.pending_transactions(int(max), response_format=response_format)


@when('we make any Pending Transactions Information call')
def pending_txn_any(context):
    context.response = context.acl.pending_transactions(100, response_format="msgpack")


@when('we make any Pending Transaction Information call')
def pending_txn_any2(context):
    context.response = context.acl.pending_transaction_info("sdfsf", response_format="msgpack")


@then('the parsed Pending Transaction Information response should have sender "{sender}"')
def parse_pending_txn(context, sender):
    context.response = json.loads(context.response)
    assert encoding.encode_address(base64.b64decode(context.response["txn"]["txn"]["snd"])) == sender


@then(
    'the parsed Pending Transactions Information response should contain an array of len {length} and element number {idx} should have sender "{sender}"')
def parse_pending_txns(context, length, idx, sender):
    context.response = json.loads(context.response)
    assert len(context.response["top-transactions"]) == int(length)
    assert encoding.encode_address(
        base64.b64decode(context.response["top-transactions"][int(idx)]["txn"]["snd"])) == sender


@when(
    'we make a Pending Transactions By Address call against account "{account}" and max {max} and format "{response_format}"')
def pending_txns_by_addr(context, account, max, response_format):
    context.response = context.acl.pending_transactions_by_address(account, limit=int(max),
                                                                   response_format=response_format)


@when('we make any Pending Transactions By Address call')
def pending_txns_by_addr_any(context):
    context.response = context.acl.pending_transactions_by_address(
        "PNWOET7LLOWMBMLE4KOCELCX6X3D3Q4H2Q4QJASYIEOF7YIPPQBG3YQ5YI", response_format="msgpack")


@then(
    'the parsed Pending Transactions By Address response should contain an array of len {length} and element number {idx} should have sender "{sender}"')
def parse_pend_by_addr(context, length, idx, sender):
    context.response = json.loads(context.response)
    assert len(context.response["top-transactions"]) == int(length)
    assert encoding.encode_address(
        base64.b64decode(context.response["top-transactions"][int(idx)]["txn"]["snd"])) == sender


@when('we make any Send Raw Transaction call')
def send_any(context):
    context.response = context.acl.send_raw_transaction("Bg==")


@then('the parsed Send Raw Transaction response should have txid "{txid}"')
def parsed_send(context, txid):
    assert context.response == txid


@when('we make any Node Status call')
def status_any(context):
    context.response = context.acl.status()


@then('the parsed Node Status response should have a last round of {roundNum}')
def parse_status(context, roundNum):
    assert context.response["last-round"] == int(roundNum)


@when('we make a Status after Block call with round {block}')
def status_after(context, block):
    context.response = context.acl.status_after_block(int(block))


@when('we make any Status After Block call')
def status_after_any(context):
    context.response = context.acl.status_after_block(3)


@then('the parsed Status After Block response should have a last round of {roundNum}')
def parse_status_after(context, roundNum):
    assert context.response["last-round"] == int(roundNum)


@when('we make any Ledger Supply call')
def ledger_any(context):
    context.response = context.acl.ledger_supply()


@then('the parsed Ledger Supply response should have totalMoney {tot} onlineMoney {online} on round {roundNum}')
def parse_ledger(context, tot, online, roundNum):
    assert context.response["online-money"] == int(online)
    assert context.response["total-money"] == int(tot)
    assert context.response["current_round"] == int(roundNum)


@when('we make an Account Information call against account "{account}"')
def acc_info(context, account):
    context.response = context.acl.account_info(account)


@when('we make any Account Information call')
def acc_info_any(context):
    context.response = context.acl.account_info("PNWOET7LLOWMBMLE4KOCELCX6X3D3Q4H2Q4QJASYIEOF7YIPPQBG3YQ5YI")


@then('the parsed Account Information response should have address "{address}"')
def parse_acc_info(context, address):
    assert context.response["address"] == address

@when('we make a GetAssetByID call for assetID {asset_id}')
def asset_info(context, asset_id):
    context.response = context.acl.asset_info(int(asset_id))

@when('we make a GetApplicationByID call for applicationID {app_id}')
def application_info(context, app_id):
    context.response = context.acl.application_info(int(app_id))

@when('we make a Get Block call against block number {block} with format "{response_format}"')
def block(context, block, response_format):
    context.response = context.acl.block_info(int(block), response_format=response_format)


@when('we make any Get Block call')
def block_any(context):
    context.response = context.acl.block_info(3, response_format="msgpack")


@then('the parsed Get Block response should have rewards pool "{pool}"')
def parse_block(context, pool):
    context.response = json.loads(context.response)
    assert context.response["block"]["rwd"] == pool


@when(
    'I get the next page using {indexer} to lookup asset balances for {assetid} with {currencygt}, {currencylt}, {limit}')
def next_asset_balance(context, indexer, assetid, currencygt, currencylt, limit):
    context.response = context.icls[indexer].asset_balances(int(assetid), min_balance=int(currencygt),
                                                            max_balance=int(currencylt), limit=int(limit),
                                                            next_page=context.response["next-token"])


@then('There are {numaccounts} with the asset, the first is "{account}" has "{isfrozen}" and {amount}')
def check_asset_balance(context, numaccounts, account, isfrozen, amount):
    assert len(context.response["balances"]) == int(numaccounts)
    assert context.response["balances"][0]["address"] == account
    assert context.response["balances"][0]["amount"] == int(amount)
    assert context.response["balances"][0]["is-frozen"] == (isfrozen == "true")


@when(
    'we make a Lookup Asset Balances call against asset index {index} with limit {limit} afterAddress "{afterAddress:MaybeString}" round {block} currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan}')
def asset_balance(context, index, limit, afterAddress, block, currencyGreaterThan, currencyLessThan):
    context.response = context.icl.asset_balances(int(index), int(limit), next_page=None,
                                                  min_balance=int(currencyGreaterThan),
                                                  max_balance=int(currencyLessThan), block=int(block))


@when('we make any LookupAssetBalances call')
def asset_balance_any(context):
    context.response = context.icl.asset_balances(123, 10)


@then(
    'the parsed LookupAssetBalances response should be valid on round {roundNum}, and contain an array of len {length} and element number {idx} should have address "{address}" amount {amount} and frozen state "{frozenState}"')
def parse_asset_balance(context, roundNum, length, idx, address, amount, frozenState):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["balances"]) == int(length)
    assert context.response["balances"][int(idx)]["address"] == address
    assert context.response["balances"][int(idx)]["amount"] == int(amount)
    assert context.response["balances"][int(idx)]["is-frozen"] == (frozenState == "true")


@when('I use {indexer} to search for all {assetid} asset transactions')
def icl_asset_txns(context, indexer, assetid):
    context.response = context.icls[indexer].search_asset_transactions(int(assetid))


@when(
    'we make a Lookup Asset Transactions call against asset index {index} with NotePrefix "{notePrefixB64:MaybeString}" TxType "{txType:MaybeString}" SigType "{sigType:MaybeString}" txid "{txid:MaybeString}" round {block} minRound {minRound} maxRound {maxRound} limit {limit} beforeTime "{beforeTime:MaybeString}" afterTime "{afterTime:MaybeString}" currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} address "{address:MaybeString}" addressRole "{addressRole:MaybeString}" ExcluseCloseTo "{excludeCloseTo:MaybeString}" RekeyTo "{rekeyTo:MaybeString}"')
def asset_txns(context, index, notePrefixB64, txType, sigType, txid, block, minRound, maxRound, limit, beforeTime,
               afterTime, currencyGreaterThan, currencyLessThan, address, addressRole, excludeCloseTo, rekeyTo):
    if notePrefixB64 == "none":
        notePrefixB64 = ""
    if txType == "none":
        txType = None
    if sigType == "none":
        sigType = None
    if txid == "none":
        txid = None
    if beforeTime == "none":
        beforeTime = None
    if afterTime == "none":
        afterTime = None
    if address == "none":
        address = None
    if addressRole == "none":
        addressRole = None
    if excludeCloseTo == "none":
        excludeCloseTo = None
    if rekeyTo == "none":
        rekeyTo = None
    context.response = context.icl.search_asset_transactions(int(index), limit=int(limit), next_page=None,
                                                             note_prefix=base64.b64decode(notePrefixB64),
                                                             txn_type=txType,
                                                             sig_type=sigType, txid=txid, block=int(block),
                                                             min_round=int(minRound), max_round=int(maxRound),
                                                             start_time=afterTime, end_time=beforeTime,
                                                             min_amount=int(currencyGreaterThan),
                                                             max_amount=int(currencyLessThan), address=address,
                                                             address_role=addressRole,
                                                             exclude_close_to=excludeCloseTo, rekey_to=rekeyTo)


@when(
    'we make a Lookup Asset Transactions call against asset index {index} with NotePrefix "{notePrefixB64:MaybeString}" TxType "{txType:MaybeString}" SigType "{sigType:MaybeString}" txid "{txid:MaybeString}" round {block} minRound {minRound} maxRound {maxRound} limit {limit} beforeTime "{beforeTime:MaybeString}" afterTime "{afterTime:MaybeString}" currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} address "{address:MaybeString}" addressRole "{addressRole:MaybeString}" ExcluseCloseTo "{excludeCloseTo:MaybeString}"')
def step_impl(context, index, notePrefixB64, txType, sigType, txid, block, minRound, maxRound, limit, beforeTime,
              afterTime, currencyGreaterThan, currencyLessThan, address, addressRole, excludeCloseTo):
    if notePrefixB64 == "none":
        notePrefixB64 = ""
    if txType == "none":
        txType = None
    if sigType == "none":
        sigType = None
    if txid == "none":
        txid = None
    if beforeTime == "none":
        beforeTime = None
    if afterTime == "none":
        afterTime = None
    if address == "none":
        address = None
    if addressRole == "none":
        addressRole = None
    if excludeCloseTo == "none":
        excludeCloseTo = None

    context.response = context.icl.search_asset_transactions(int(index), limit=int(limit), next_page=None,
                                                             note_prefix=base64.b64decode(notePrefixB64),
                                                             txn_type=txType,
                                                             sig_type=sigType, txid=txid, block=int(block),
                                                             min_round=int(minRound), max_round=int(maxRound),
                                                             start_time=afterTime, end_time=beforeTime,
                                                             min_amount=int(currencyGreaterThan),
                                                             max_amount=int(currencyLessThan), address=address,
                                                             address_role=addressRole,
                                                             exclude_close_to=excludeCloseTo, rekey_to=None)


@when('we make any LookupAssetTransactions call')
def asset_txns_any(context):
    context.response = context.icl.search_asset_transactions(32)


@then(
    'the parsed LookupAssetTransactions response should be valid on round {roundNum}, and contain an array of len {length} and element number {idx} should have sender "{sender}"')
def parse_asset_tns(context, roundNum, length, idx, sender):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["transactions"]) == int(length)
    assert context.response["transactions"][int(idx)]["sender"] == sender


@when('I use {indexer} to search for all "{accountid}" transactions')
def icl_txns_by_addr(context, indexer, accountid):
    context.response = context.icls[indexer].search_transactions_by_address(accountid)


@when(
    'we make a Lookup Account Transactions call against account "{account:MaybeString}" with NotePrefix "{notePrefixB64:MaybeString}" TxType "{txType:MaybeString}" SigType "{sigType:MaybeString}" txid "{txid:MaybeString}" round {block} minRound {minRound} maxRound {maxRound} limit {limit} beforeTime "{beforeTime:MaybeString}" afterTime "{afterTime:MaybeString}" currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} assetIndex {index} rekeyTo "{rekeyTo:MaybeString}"')
def txns_by_addr(context, account, notePrefixB64, txType, sigType, txid, block, minRound, maxRound, limit, beforeTime,
                 afterTime, currencyGreaterThan, currencyLessThan, index, rekeyTo):
    if notePrefixB64 == "none":
        notePrefixB64 = ""
    if txType == "none":
        txType = None
    if sigType == "none":
        sigType = None
    if txid == "none":
        txid = None
    if beforeTime == "none":
        beforeTime = None
    if afterTime == "none":
        afterTime = None
    if rekeyTo == "none":
        rekeyTo = None
    context.response = context.icl.search_transactions_by_address(asset_id=int(index), limit=int(limit), next_page=None,
                                                                  note_prefix=base64.b64decode(notePrefixB64),
                                                                  txn_type=txType,
                                                                  sig_type=sigType, txid=txid, block=int(block),
                                                                  min_round=int(minRound), max_round=int(maxRound),
                                                                  start_time=afterTime, end_time=beforeTime,
                                                                  min_amount=int(currencyGreaterThan),
                                                                  max_amount=int(currencyLessThan), address=account,
                                                                  rekey_to=rekeyTo)


@when(
    'we make a Lookup Account Transactions call against account "{account:MaybeString}" with NotePrefix "{notePrefixB64:MaybeString}" TxType "{txType:MaybeString}" SigType "{sigType:MaybeString}" txid "{txid:MaybeString}" round {block} minRound {minRound} maxRound {maxRound} limit {limit} beforeTime "{beforeTime:MaybeString}" afterTime "{afterTime:MaybeString}" currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} assetIndex {index}')
def txns_by_addr(context, account, notePrefixB64, txType, sigType, txid, block, minRound, maxRound, limit, beforeTime,
                 afterTime, currencyGreaterThan, currencyLessThan, index):
    if notePrefixB64 == "none":
        notePrefixB64 = ""
    if txType == "none":
        txType = None
    if sigType == "none":
        sigType = None
    if txid == "none":
        txid = None
    if beforeTime == "none":
        beforeTime = None
    if afterTime == "none":
        afterTime = None
    context.response = context.icl.search_transactions_by_address(asset_id=int(index), limit=int(limit), next_page=None,
                                                                  note_prefix=base64.b64decode(notePrefixB64),
                                                                  txn_type=txType,
                                                                  sig_type=sigType, txid=txid, block=int(block),
                                                                  min_round=int(minRound), max_round=int(maxRound),
                                                                  start_time=afterTime, end_time=beforeTime,
                                                                  min_amount=int(currencyGreaterThan),
                                                                  max_amount=int(currencyLessThan), address=account,
                                                                  rekey_to=None)


@when('we make any LookupAccountTransactions call')
def txns_by_addr_any(context):
    context.response = context.icl.search_transactions_by_address(
        "PNWOET7LLOWMBMLE4KOCELCX6X3D3Q4H2Q4QJASYIEOF7YIPPQBG3YQ5YI")


@then(
    'the parsed LookupAccountTransactions response should be valid on round {roundNum}, and contain an array of len {length} and element number {idx} should have sender "{sender}"')
def parse_txns_by_addr(context, roundNum, length, idx, sender):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["transactions"]) == int(length)
    if int(length) > 0:
        assert context.response["transactions"][int(idx)]["sender"] == sender


@when('I use {indexer} to check the services health')
def icl_health(context, indexer):
    context.response = context.icls[indexer].health()


@then('I receive status code {code}')
def icl_health_check(context, code):
    # An exception is thrown when the code is not 200
    assert int(code) == 200


@when('I use {indexer} to lookup block {number}')
def icl_lookup_block(context, indexer, number):
    context.response = context.icls[indexer].block_info(int(number))


@then('The block was confirmed at {timestamp}, contains {num} transactions, has the previous block hash "{prevHash}"')
def icl_block_check(context, timestamp, num, prevHash):
    assert context.response["previous-block-hash"] == prevHash
    assert len(context.response["transactions"]) == int(num)
    assert context.response["timestamp"] == int(timestamp)


@when('we make a Lookup Block call against round {block}')
def lookup_block(context, block):
    context.response = context.icl.block_info(int(block))


@when('we make any LookupBlock call')
def lookup_block_any(context):
    context.response = context.icl.block_info(12)


@then('the parsed LookupBlock response should have previous block hash "{prevHash}"')
def parse_lookup_block(context, prevHash):
    assert context.response["previous-block-hash"] == prevHash


@then('The account has {num} assets, the first is asset {index} has a frozen status of "{frozen}" and amount {units}.')
def lookup_account_check(context, num, index, frozen, units):
    assert len(context.response["account"]["assets"]) == int(num)
    assert context.response["account"]["assets"][0]["asset-id"] == int(index)
    assert context.response["account"]["assets"][0]["is-frozen"] == (frozen == "true")
    assert context.response["account"]["assets"][0]["amount"] == int(units)


@then(
    'The account created {num} assets, the first is asset {index} is named "{name}" with a total amount of {total} "{unit}"')
def lookup_account_check_created(context, num, index, name, total, unit):
    assert len(context.response["account"]["created-assets"]) == int(num)
    assert context.response["account"]["created-assets"][0]["index"] == int(index)
    assert context.response["account"]["created-assets"][0]["params"]["name"] == name
    assert context.response["account"]["created-assets"][0]["params"]["unit-name"] == unit
    assert context.response["account"]["created-assets"][0]["params"]["total"] == int(total)


@then('The account has {μalgos} μalgos and {num} assets, {assetid} has {assetamount}')
def lookup_account_check_holdings(context, μalgos, num, assetid, assetamount):
    assert context.response["account"]["amount"] == int(μalgos)
    assert len(context.response["account"].get("assets", [])) == int(num)
    if int(num) > 0:
        assets = context.response["account"]["assets"]
        for a in assets:
            if a["asset-id"] == int(assetid):
                assert a["amount"] == int(assetamount)


@when('I use {indexer} to lookup account "{account}" at round {round}')
def icl_lookup_account_at_round(context, indexer, account, round):
    context.response = context.icls[indexer].account_info(account, int(round))


@when('we make a Lookup Account by ID call against account "{account}" with round {block}')
def lookup_account(context, account, block):
    context.response = context.icl.account_info(account, int(block))


@when("we make any LookupAccountByID call")
def lookup_account_any(context):
    context.response = context.icl.account_info("PNWOET7LLOWMBMLE4KOCELCX6X3D3Q4H2Q4QJASYIEOF7YIPPQBG3YQ5YI", 12)


@then('the parsed LookupAccountByID response should have address "{address}"')
def parse_account(context, address):
    assert context.response["account"]["address"] == address


@when(
    'I use {indexer} to lookup asset balances for {assetid} with {currencygt}, {currencylt}, {limit} and token "{token}"')
def icl_asset_balance(context, indexer, assetid, currencygt, currencylt, limit, token):
    context.response = context.icls[indexer].asset_balances(int(assetid), min_balance=int(currencygt),
                                                            max_balance=int(currencylt), limit=int(limit),
                                                            next_page=token)


def parse_args(assetid):
    t = assetid.split(" ")
    l = {
        "assetid": t[2],
        "currencygt": t[4][:-1],
        "currencylt": t[5][:-1],
        "limit": t[6],
        "token": t[9][1:-1]
    }
    return l


@when('I use {indexer} to lookup asset {assetid}')
def icl_lookup_asset(context, indexer, assetid):
    try:
        context.response = context.icls[indexer].asset_info(int(assetid))
    except:
        icl_asset_balance(context, indexer, **parse_args(assetid))


@then('The asset found has: "{name}", "{units}", "{creator}", {decimals}, "{defaultfrozen}", {total}, "{clawback}"')
def check_lookup_asset(context, name, units, creator, decimals, defaultfrozen, total, clawback):
    assert context.response["asset"]["params"]["name"] == name
    assert context.response["asset"]["params"]["unit-name"] == units
    assert context.response["asset"]["params"]["creator"] == creator
    assert context.response["asset"]["params"]["decimals"] == int(decimals)
    assert context.response["asset"]["params"]["default-frozen"] == (defaultfrozen == "true")
    assert context.response["asset"]["params"]["total"] == int(total)
    assert context.response["asset"]["params"]["clawback"] == clawback


@when('we make a Lookup Asset by ID call against asset index {index}')
def lookup_asset(context, index):
    context.response = context.icl.asset_info(int(index))


@when('we make any LookupAssetByID call')
def lookup_asset_any(context):
    context.response = context.icl.asset_info(1)


@then('the parsed LookupAssetByID response should have index {index}')
def parse_asset(context, index):
    assert context.response["asset"]["index"] == int(index)

@when('we make a LookupApplications call with applicationID {app_id}')
def lookup_application(context, app_id):
    context.response = context.icl.applications(int(app_id))

@when('we make a SearchForApplications call with applicationID {app_id}')
def search_application(context, app_id):
    context.response = context.icl.search_applications(int(app_id))

@when(
    'we make a Search Accounts call with assetID {index} limit {limit} currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} and round {block}')
def search_accounts(context, index, limit, currencyGreaterThan, currencyLessThan, block):
    context.response = context.icl.accounts(asset_id=int(index), limit=int(limit), next_page=None,
                                            min_balance=int(currencyGreaterThan),
                                            max_balance=int(currencyLessThan), block=int(block))


@when(
    'we make a Search Accounts call with assetID {index} limit {limit} currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} round {block} and authenticating address "{authAddr:MaybeString}"')
def search_accounts(context, index, limit, currencyGreaterThan, currencyLessThan, block, authAddr):
    if authAddr == "none":
        authAddr = None
    context.response = context.icl.accounts(asset_id=int(index), limit=int(limit), next_page=None,
                                            min_balance=int(currencyGreaterThan),
                                            max_balance=int(currencyLessThan), block=int(block), auth_addr=authAddr)

@when(
    'I use {indexer} to search for an account with {assetid}, {limit}, {currencygt}, {currencylt}, "{auth_addr:MaybeString}", {application_id}, "{include_all:MaybeBool}" and token "{token:MaybeString}"')
def icl_search_accounts_with_auth_addr_and_app_id_and_include_all(context, indexer, assetid, limit, currencygt, currencylt, auth_addr, application_id, include_all, token):
    context.response = context.icls[indexer].accounts(asset_id=int(assetid), limit=int(limit), next_page=token,
                                                      min_balance=int(currencygt),
                                                      max_balance=int(currencylt),
                                                      auth_addr=auth_addr,
                                                      application_id=int(application_id),
                                                      include_all=include_all)

@when(
    'I use {indexer} to search for an account with {assetid}, {limit}, {currencygt}, {currencylt}, "{auth_addr:MaybeString}", {application_id} and token "{token:MaybeString}"')
def icl_search_accounts_with_auth_addr_and_app_id(context, indexer, assetid, limit, currencygt, currencylt, auth_addr, application_id, token):
    context.response = context.icls[indexer].accounts(asset_id=int(assetid), limit=int(limit), next_page=token,
                                                      min_balance=int(currencygt),
                                                      max_balance=int(currencylt),
                                                      auth_addr=auth_addr,
                                                      application_id=int(application_id))

@when(
    'I use {indexer} to search for an account with {assetid}, {limit}, {currencygt}, {currencylt} and token "{token:MaybeString}"')
def icl_search_accounts_legacy(context, indexer, assetid, limit, currencygt, currencylt, token):
    context.response = context.icls[indexer].accounts(asset_id=int(assetid), limit=int(limit), next_page=token,
                                                     min_balance=int(currencygt),
                                                     max_balance=int(currencylt))


@then(
    'I get the next page using {indexer} to search for an account with {assetid}, {limit}, {currencygt} and {currencylt}')
def search_accounts_nex(context, indexer, assetid, limit, currencygt, currencylt):
    context.response = context.icls[indexer].accounts(asset_id=int(assetid), limit=int(limit),
                                                      min_balance=int(currencygt),
                                                      max_balance=int(currencylt),
                                                      next_page=context.response["next-token"])


@then(
    'There are {num}, the first has {pendingrewards}, {rewardsbase}, {rewards}, {withoutrewards}, "{address}", {amount}, "{status}", "{sigtype:MaybeString}"')
def check_search_accounts(context, num, pendingrewards, rewardsbase, rewards, withoutrewards, address, amount, status,
                          sigtype):
    assert len(context.response["accounts"]) == int(num)
    assert context.response["accounts"][0]["pending-rewards"] == int(pendingrewards)
    assert context.response["accounts"][0].get("rewards-base", 0) == int(rewardsbase)
    assert context.response["accounts"][0]["rewards"] == int(rewards)
    assert context.response["accounts"][0]["amount-without-pending-rewards"] == int(withoutrewards)
    assert context.response["accounts"][0]["address"] == address
    assert context.response["accounts"][0]["amount"] == int(amount)
    assert context.response["accounts"][0]["status"] == status
    assert context.response["accounts"][0].get("sig-type", "") == sigtype


@then(
    'The first account is online and has "{address}", {keydilution}, {firstvalid}, {lastvalid}, "{votekey}", "{selectionkey}"')
def check_search_accounts_online(context, address, keydilution, firstvalid, lastvalid, votekey, selectionkey):
    assert context.response["accounts"][0]["status"] == "Online"
    assert context.response["accounts"][0]["address"] == address
    assert context.response["accounts"][0]["participation"]["vote-key-dilution"] == int(keydilution)
    assert context.response["accounts"][0]["participation"]["vote-first-valid"] == int(firstvalid)
    assert context.response["accounts"][0]["participation"]["vote-last-valid"] == int(lastvalid)
    assert context.response["accounts"][0]["participation"]["vote-participation-key"] == votekey
    assert context.response["accounts"][0]["participation"]["selection-participation-key"] == selectionkey


@when('we make any SearchAccounts call')
def search_accounts_any(context):
    context.response = context.icl.accounts(asset_id=2)


@then(
    'the parsed SearchAccounts response should be valid on round {roundNum} and the array should be of len {length} and the element at index {index} should have address "{address}"')
def parse_accounts(context, roundNum, length, index, address):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["accounts"]) == int(length)
    if int(length) > 0:
        assert context.response["accounts"][int(index)]["address"] == address


@when(
    'the parsed SearchAccounts response should be valid on round {roundNum} and the array should be of len {length} and the element at index {index} should have authorizing address "{authAddr:MaybeString}"')
def parse_accounts_auth(context, roundNum, length, index, authAddr):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["accounts"]) == int(length)
    if int(length) > 0:
        assert context.response["accounts"][int(index)]["auth-addr"] == authAddr


@when('I get the next page using {indexer} to search for transactions with {limit} and {maxround}')
def search_txns_next(context, indexer, limit, maxround):
    context.response = context.icls[indexer].search_transactions(limit=int(limit), max_round=int(maxround),
                                                                 next_page=context.response["next-token"])


@when(
    'I use {indexer} to search for transactions with {limit}, "{noteprefix:MaybeString}", "{txtype:MaybeString}", "{sigtype:MaybeString}", "{txid:MaybeString}", {block}, {minround}, {maxround}, {assetid}, "{beforetime:MaybeString}", "{aftertime:MaybeString}", {currencygt}, {currencylt}, "{address:MaybeString}", "{addressrole:MaybeString}", "{excludecloseto:MaybeString}" and token "{token:MaybeString}"')
def icl_search_txns(context, indexer, limit, noteprefix, txtype, sigtype, txid, block, minround, maxround, assetid,
                    beforetime, aftertime, currencygt, currencylt, address, addressrole, excludecloseto, token):
    context.response = context.icls[indexer].search_transactions(asset_id=int(assetid), limit=int(limit),
                                                                 next_page=token,
                                                                 note_prefix=base64.b64decode(noteprefix),
                                                                 txn_type=txtype,
                                                                 sig_type=sigtype, txid=txid, block=int(block),
                                                                 min_round=int(minround), max_round=int(maxround),
                                                                 start_time=aftertime, end_time=beforetime,
                                                                 min_amount=int(currencygt),
                                                                 max_amount=int(currencylt), address=address,
                                                                 address_role=addressrole,
                                                                 exclude_close_to=excludecloseto == "true")


@when(
    'I use {indexer} to search for transactions with {limit}, "{noteprefix:MaybeString}", "{txtype:MaybeString}", "{sigtype:MaybeString}", "{txid:MaybeString}", {block}, {minround}, {maxround}, {assetid}, "{beforetime:MaybeString}", "{aftertime:MaybeString}", {currencygt}, {currencylt}, "{address:MaybeString}", "{addressrole:MaybeString}", "{excludecloseto:MaybeString}", {application_id} and token "{token:MaybeString}"')
def icl_search_txns_with_app(context, indexer, limit, noteprefix, txtype, sigtype, txid, block, minround, maxround, assetid,
                    beforetime, aftertime, currencygt, currencylt, address, addressrole, excludecloseto, application_id, token):
    context.response = context.icls[indexer].search_transactions(asset_id=int(assetid), limit=int(limit),
                                                                 next_page=token,
                                                                 note_prefix=base64.b64decode(noteprefix),
                                                                 txn_type=txtype,
                                                                 sig_type=sigtype, txid=txid, block=int(block),
                                                                 min_round=int(minround), max_round=int(maxround),
                                                                 start_time=aftertime, end_time=beforetime,
                                                                 min_amount=int(currencygt),
                                                                 max_amount=int(currencylt), address=address,
                                                                 address_role=addressrole,
                                                                 application_id=int(application_id),
                                                                 exclude_close_to=excludecloseto == "true")

@then('there are {num} transactions in the response, the first is "{txid:MaybeString}".')
def check_transactions(context, num, txid):
    assert len(context.response["transactions"]) == int(num)
    if int(num) > 0:
        assert context.response["transactions"][0]["id"] == txid


@then('Every transaction has tx-type "{txtype}"')
def check_transaction_types(context, txtype):
    for txn in context.response["transactions"]:
        assert txn["tx-type"] == txtype


@then('Every transaction has sig-type "{sigtype}"')
def check_sig_types(context, sigtype):
    for txn in context.response["transactions"]:
        if sigtype == "lsig":
            assert list(txn["signature"].keys())[0] == "logicsig"
        if sigtype == "msig":
            assert list(txn["signature"].keys())[0] == "multisig"
        if sigtype == "sig":
            assert list(txn["signature"].keys())[0] == sigtype


@then('Every transaction has round >= {minround}')
def check_minround(context, minround):
    for txn in context.response["transactions"]:
        assert txn["confirmed-round"] >= int(minround)


@then('Every transaction has round <= {maxround}')
def check_maxround(context, maxround):
    for txn in context.response["transactions"]:
        assert txn["confirmed-round"] <= int(maxround)


@then('Every transaction has round {block}')
def check_round(context, block):
    for txn in context.response["transactions"]:
        assert txn["confirmed-round"] == int(block)


@then('Every transaction works with asset-id {assetid}')
def check_assetid(context, assetid):
    for txn in context.response["transactions"]:
        if "asset-config-transaction" in txn:
            subtxn = txn["asset-config-transaction"]
        else:
            subtxn = txn["asset-transfer-transaction"]
        assert subtxn["asset-id"] == int(assetid) or txn["created-asset-index"] == int(assetid)


@then('Every transaction is older than "{before}"')
def check_before(context, before):
    for txn in context.response["transactions"]:
        t = datetime.fromisoformat(before.replace("Z", "+00:00"))
        assert txn["round-time"] <= datetime.timestamp(t)


@then('Every transaction is newer than "{after}"')
def check_after(context, after):
    t = True
    for txn in context.response["transactions"]:
        t = datetime.fromisoformat(after.replace("Z", "+00:00"))
        if not txn["round-time"] >= datetime.timestamp(t):
            t = False
    assert t


@then('Every transaction moves between {currencygt} and {currencylt} currency')
def check_currency(context, currencygt, currencylt):
    for txn in context.response["transactions"]:
        amt = 0
        if "asset-transfer-transaction" in txn:
            amt = txn["asset-transfer-transaction"]["amount"]
        else:
            amt = txn["payment-transaction"]["amount"]
        if int(currencygt) == 0:
            if int(currencylt) > 0:
                assert amt <= int(currencylt)
        else:
            if int(currencylt) > 0:
                assert int(currencygt) <= amt <= int(currencylt)
            else:
                assert int(currencygt) <= amt


@when(
    'we make a Search For Transactions call with account "{account:MaybeString}" NotePrefix "{notePrefixB64:MaybeString}" TxType "{txType:MaybeString}" SigType "{sigType:MaybeString}" txid "{txid:MaybeString}" round {block} minRound {minRound} maxRound {maxRound} limit {limit} beforeTime "{beforeTime:MaybeString}" afterTime "{afterTime:MaybeString}" currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} assetIndex {index} addressRole "{addressRole:MaybeString}" ExcluseCloseTo "{excludeCloseTo:MaybeString}" rekeyTo "{rekeyTo:MaybeString}"')
def search_txns(context, account, notePrefixB64, txType, sigType, txid, block, minRound, maxRound, limit, beforeTime,
                afterTime, currencyGreaterThan, currencyLessThan, index, addressRole, excludeCloseTo, rekeyTo):
    if notePrefixB64 == "none":
        notePrefixB64 = ""
    if txType == "none":
        txType = None
    if sigType == "none":
        sigType = None
    if txid == "none":
        txid = None
    if beforeTime == "none":
        beforeTime = None
    if afterTime == "none":
        afterTime = None
    if account == "none":
        account = None
    if addressRole == "none":
        addressRole = None
    if excludeCloseTo == "none":
        excludeCloseTo = None
    if rekeyTo == "none":
        rekeyTo = None
    context.response = context.icl.search_transactions(asset_id=int(index), limit=int(limit), next_page=None,
                                                       note_prefix=base64.b64decode(notePrefixB64), txn_type=txType,
                                                       sig_type=sigType, txid=txid, block=int(block),
                                                       min_round=int(minRound), max_round=int(maxRound),
                                                       start_time=afterTime, end_time=beforeTime,
                                                       min_amount=int(currencyGreaterThan),
                                                       max_amount=int(currencyLessThan), address=account,
                                                       address_role=addressRole,
                                                       exclude_close_to=excludeCloseTo, rekey_to=rekeyTo)


@when(
    'we make a Search For Transactions call with account "{account:MaybeString}" NotePrefix "{notePrefixB64:MaybeString}" TxType "{txType:MaybeString}" SigType "{sigType:MaybeString}" txid "{txid:MaybeString}" round {block} minRound {minRound} maxRound {maxRound} limit {limit} beforeTime "{beforeTime:MaybeString}" afterTime "{afterTime:MaybeString}" currencyGreaterThan {currencyGreaterThan} currencyLessThan {currencyLessThan} assetIndex {index} addressRole "{addressRole:MaybeString}" ExcluseCloseTo "{excludeCloseTo:MaybeString}"')
def search_txns(context, account, notePrefixB64, txType, sigType, txid, block, minRound, maxRound, limit, beforeTime,
                afterTime, currencyGreaterThan, currencyLessThan, index, addressRole, excludeCloseTo):
    if notePrefixB64 == "none":
        notePrefixB64 = ""
    if txType == "none":
        txType = None
    if sigType == "none":
        sigType = None
    if txid == "none":
        txid = None
    if beforeTime == "none":
        beforeTime = None
    if afterTime == "none":
        afterTime = None
    if account == "none":
        account = None
    if addressRole == "none":
        addressRole = None
    if excludeCloseTo == "none":
        excludeCloseTo = None
    context.response = context.icl.search_transactions(asset_id=int(index), limit=int(limit), next_page=None,
                                                       note_prefix=base64.b64decode(notePrefixB64), txn_type=txType,
                                                       sig_type=sigType, txid=txid, block=int(block),
                                                       min_round=int(minRound), max_round=int(maxRound),
                                                       start_time=afterTime, end_time=beforeTime,
                                                       min_amount=int(currencyGreaterThan),
                                                       max_amount=int(currencyLessThan), address=account,
                                                       address_role=addressRole,
                                                       exclude_close_to=excludeCloseTo, rekey_to=None)


@when('we make any SearchForTransactions call')
def search_txns_any(context):
    context.response = context.icl.search_transactions(asset_id=2)


@then(
    'the parsed SearchForTransactions response should be valid on round {roundNum} and the array should be of len {length} and the element at index {index} should have sender "{sender}"')
def parse_search_txns(context, roundNum, length, index, sender):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["transactions"]) == int(length)
    if int(length) > 0:
        assert context.response["transactions"][int(index)]["sender"] == sender


@when(
    'the parsed SearchForTransactions response should be valid on round {roundNum} and the array should be of len {length} and the element at index {index} should have rekey-to "{rekeyTo:MaybeString}"')
def step_impl(context, roundNum, length, index, rekeyTo):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["transactions"]) == int(length)
    if int(length) > 0:
        assert context.response["transactions"][int(index)]["rekey-to"] == rekeyTo


@when(
    'I use {indexer} to search for assets with {limit}, {assetidin}, "{creator:MaybeString}", "{name:MaybeString}", "{unit:MaybeString}", and token "{token:MaybeString}"')
def icl_search_assets(context, indexer, limit, assetidin, creator, name, unit, token):
    context.response = context.icls[indexer].search_assets(
        limit=int(limit), next_page=token, creator=creator, name=name, unit=unit,
        asset_id=int(assetidin))


@then('there are {num} assets in the response, the first is {assetidout}.')
def check_assets(context, num, assetidout):
    assert len(context.response["assets"]) == int(num)
    if int(num) > 0:
        assert context.response["assets"][0]["index"] == int(assetidout)

@when('I use {indexer} to search for applications with {limit}, {application_id}, "{include_all:MaybeBool}" and token "{token:MaybeString}"')
def search_applications_include_all(context, indexer, limit, application_id, include_all, token):
    context.response = context.icls[indexer].search_applications(application_id=int(application_id),limit=int(limit),
                                                                 include_all=include_all,next_page=token)

@when('I use {indexer} to search for applications with {limit}, {application_id}, and token "{token:MaybeString}"')
def search_applications(context, indexer, limit, application_id, token):
    context.response = context.icls[indexer].search_applications(application_id=int(application_id),limit=int(limit),
                                                                 next_page=token)

@when('I use {indexer} to lookup application with {application_id} and "{include_all:MaybeBool}"')
def lookup_application_include_all(context, indexer, application_id, include_all):
    try:
        context.response = context.icls[indexer].applications(application_id=int(application_id), include_all=include_all)
    except IndexerHTTPError as e:
        context.response = json.loads(str(e))

@when('I use {indexer} to lookup application with {application_id}')
def lookup_application(context, indexer, application_id):
    context.response = context.icls[indexer].applications(application_id=int(application_id))

@then(u'the parsed response should equal "{jsonfile}".')
def step_impl(context, jsonfile):
    loaded_response = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.dirname(os.path.dirname(dir_path))
    with open(dir_path + "/test/features/resources/" + jsonfile, "rb") as f:
        loaded_response = bytearray(f.read())
    # sort context.response
    def recursively_sort_on_key(dictionary):
        returned_dict = dict()
        for k, v in sorted(dictionary.items()):
            if isinstance(v, dict):
                returned_dict[k] = recursively_sort_on_key(v)
            elif isinstance(v, list) and all(isinstance(item, dict) for item in v):
                if all('key' in item.keys() for item in v):
                    from operator import itemgetter
                    returned_dict[k] = sorted(v, key=itemgetter('key'))
                else:
                    sorted_list = list()
                    for item in v:
                        sorted_list.append(recursively_sort_on_key(item))
                    returned_dict[k] = sorted_list
            else:
                returned_dict[k] = v
        return returned_dict
    context.response = recursively_sort_on_key(context.response)
    loaded_response = recursively_sort_on_key(json.loads(loaded_response))
    if context.response != loaded_response:
        print("EXPECTED: " + str(loaded_response))
        print("ACTUAL: " + str(context.response))
    assert context.response == loaded_response


@when(
    'we make a SearchForAssets call with limit {limit} creator "{creator:MaybeString}" name "{name:MaybeString}" unit "{unit:MaybeString}" index {index}')
def search_assets(context, limit, creator, name, unit, index):
    if creator == "none":
        creator = None
    if name == "none":
        name = None
    if unit == "none":
        unit = None

    context.response = context.icl.search_assets(limit=int(limit),
                                                 next_page=None, creator=creator, name=name, unit=unit,
                                                 asset_id=int(index))


@when('we make any SearchForAssets call')
def search_assets_any(context):
    context.response = context.icl.search_assets(asset_id=2)


@then(
    'the parsed SearchForAssets response should be valid on round {roundNum} and the array should be of len {length} and the element at index {index} should have asset index {assetIndex}')
def parse_search_assets(context, roundNum, length, index, assetIndex):
    assert context.response["current-round"] == int(roundNum)
    assert len(context.response["assets"]) == int(length)
    if int(length) > 0:
        assert context.response["assets"][int(index)]["index"] == int(assetIndex)


@when('we make any Suggested Transaction Parameters call')
def suggested_any(context):
    context.response = context.acl.suggested_params()


@then('the parsed Suggested Transaction Parameters response should have first round valid of {roundNum}')
def parse_suggested(context, roundNum):
    assert context.response.first == int(roundNum)


@then('expect the path used to be "{path}"')
def expect_path(context, path):
    if not isinstance(context.response, dict):
        try:
            context.response = json.loads(context.response)
        except json.JSONDecodeError:
            pass
    exp_path, exp_query = urllib.parse.splitquery(path)
    exp_query = urllib.parse.parse_qs(exp_query)

    actual_path, actual_query = urllib.parse.splitquery(context.response["path"])
    actual_query = urllib.parse.parse_qs(actual_query)
    assert exp_path == actual_path.replace("%3A", ":")
    assert exp_query == actual_query


@then('we expect the path used to be "{path}"')
def we_expect_path(context, path):
    expect_path(context, path)


@then('expect error string to contain "{err:MaybeString}"')
def expect_error(context, err):
    pass


@given('indexer client {index} at "{address}" port {port} with token "{token}"')
def indexer_client(context, index, address, port, token):
    if not hasattr(context, "icls"):
        context.icls = dict()
    context.icls[index] = indexer.IndexerClient(token, "http://" + address + ":" + str(port))


@when('we make a SearchForApplications call with {application_id} and {round}')
def search_applications(context, application_id, round):
    context.response = context.icl.search_applications(application_id=int(application_id), round=int(round))


@when('we make a LookupApplications call with {application_id} and {round}')
def lookup_applications(context, application_id, round):
    context.response = context.icl.applications(application_id=int(application_id), round=int(round))


@given('a signing account with address "{address}" and mnemonic "{mnemonic}"')
def signing_account(context, address, mnemonic):
    context.signing_mnemonic = mnemonic


def operation_string_to_enum(operation):
    if operation == "call":
        return transaction.OnComplete.NoOpOC
    elif operation == "create":
        return transaction.OnComplete.NoOpOC
    elif operation == "update":
        return transaction.OnComplete.UpdateApplicationOC
    elif operation == "optin":
        return transaction.OnComplete.OptInOC
    elif operation == "delete":
        return transaction.OnComplete.DeleteApplicationOC
    elif operation == "clear":
        return transaction.OnComplete.ClearStateOC
    elif operation == "closeout":
        return transaction.OnComplete.CloseOutOC
    else:
        raise NotImplementedError("no oncomplete enum for operation " + operation)

def split_and_process_app_args(in_args):
    split_args = in_args.split(",")
    sub_args = [sub_arg.split(":") for sub_arg in split_args]
    app_args = []
    for sub_arg in sub_args:
        if sub_arg[0] == "str":
            app_args.append(bytes(sub_arg[1], 'ascii'))
        elif sub_arg[0] == "int":
            app_args.append(int(sub_arg[1]))
        elif sub_arg[0] == "addr":
            app_args.append(encoding.decode_address(sub_arg[1]))
    return app_args

@when(
        'I build an application transaction with operation "{operation:MaybeString}", application-id {application_id}, sender "{sender:MaybeString}", approval-program "{approval_program:MaybeString}", clear-program "{clear_program:MaybeString}", global-bytes {global_bytes}, global-ints {global_ints}, local-bytes {local_bytes}, local-ints {local_ints}, app-args "{app_args:MaybeString}", foreign-apps "{foreign_apps:MaybeString}", foreign-assets "{foreign_assets:MaybeString}", app-accounts "{app_accounts:MaybeString}", fee {fee}, first-valid {first_valid}, last-valid {last_valid}, genesis-hash "{genesis_hash:MaybeString}", extra-pages {extra_pages}')
def build_app_transaction(context, operation, application_id, sender, approval_program, clear_program, global_bytes,
                          global_ints, local_bytes, local_ints, app_args, foreign_apps, foreign_assets, app_accounts,
                          fee, first_valid, last_valid, genesis_hash, extra_pages):
    if operation == "none":
        operation = None
    else:
        operation = operation_string_to_enum(operation)
    if sender == "none":
        sender = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.dirname(os.path.dirname(dir_path))
    if approval_program == "none":
        approval_program = None
    elif approval_program:
        with open(dir_path + "/test/features/resources/" + approval_program, "rb") as f:
            approval_program = bytearray(f.read())
    if clear_program == "none":
        clear_program = None
    elif clear_program:
        with open(dir_path + "/test/features/resources/" + clear_program, "rb") as f:
            clear_program = bytearray(f.read())
    if app_args == "none":
        app_args = None
    elif app_args:
        app_args = split_and_process_app_args(app_args)
    if foreign_apps == "none":
        foreign_apps = None
    elif foreign_apps:
        foreign_apps = [int(app) for app in foreign_apps.split(",")]
    if foreign_assets == "none":
        foreign_assets = None
    elif foreign_assets:
        foreign_assets = [int(app) for app in foreign_assets.split(",")]
    if app_accounts == "none":
        app_accounts = None
    elif app_accounts:
        app_accounts = [account_pubkey for account_pubkey in app_accounts.split(",")]
    if genesis_hash == "none":
        genesis_hash = None
    if int(local_ints) == 0 and int(local_bytes) == 0:
        local_schema = None
    else:
        local_schema = transaction.StateSchema(num_uints=int(local_ints), num_byte_slices=int(local_bytes))
    if int(global_ints) == 0 and int(global_bytes) == 0:
        global_schema = None
    else:
        global_schema = transaction.StateSchema(num_uints=int(global_ints), num_byte_slices=int(global_bytes))
    sp = transaction.SuggestedParams(int(fee), int(first_valid), int(last_valid), genesis_hash, flat_fee=True)
    context.transaction = transaction.ApplicationCallTxn(sender=sender, sp=sp, index=int(application_id),
                                                         on_complete=operation, local_schema=local_schema,
                                                         global_schema=global_schema,
                                                         approval_program=approval_program, clear_program=clear_program,
                                                         app_args=app_args, accounts=app_accounts,
                                                         foreign_apps=foreign_apps,
                                                         foreign_assets=foreign_assets,
                                                         extra_pages=int(extra_pages),
                                                         note=None, lease=None, rekey_to=None)


@when('sign the transaction')
def sign_transaction_with_signing_account(context):
    private_key = mnemonic.to_private_key(context.signing_mnemonic)
    context.signed_transaction = context.transaction.sign(private_key)


@then('the base64 encoded signed transaction should equal "{golden}"')
def compare_to_base64_golden(context, golden):
    actual_base64 = encoding.msgpack_encode(context.signed_transaction)
    assert (golden == actual_base64)


@given('an algod v2 client connected to "{host}" port {port} with token "{token}"')
def algod_v2_client_at_host_port_and_token(context, host, port, token):
    algod_address = "http://" + str(host) + ":" + str(port)
    context.app_acl = algod.AlgodClient(token, algod_address)

@given(u'an algod v2 client')
def algod_v2_client(context):
    algod_address = "http://localhost" + ":" + str(algod_port)
    context.app_acl = algod.AlgodClient(daemon_token, algod_address)

@given('I create a new transient account and fund it with {transient_fund_amount} microalgos.')
def create_transient_and_fund(context, transient_fund_amount):
    context.transient_sk, context.transient_pk = account.generate_account()
    sp = context.app_acl.suggested_params()
    payment = transaction.PaymentTxn(context.accounts[0], sp, context.transient_pk, int(transient_fund_amount))
    signed_payment = context.wallet.sign_transaction(payment)
    context.app_acl.send_transaction(signed_payment)
    context.app_acl.status_after_block(sp.first + 2)

@step('I build an application transaction with the transient account, the current application, suggested params, operation "{operation}", approval-program "{approval_program:MaybeString}", clear-program "{clear_program:MaybeString}", global-bytes {global_bytes}, global-ints {global_ints}, local-bytes {local_bytes}, local-ints {local_ints}, app-args "{app_args:MaybeString}", foreign-apps "{foreign_apps:MaybeString}", foreign-assets "{foreign_assets:MaybeString}", app-accounts "{app_accounts:MaybeString}", extra-pages {extra_pages}')
def build_app_txn_with_transient(context, operation, approval_program, clear_program, global_bytes, global_ints, local_bytes, local_ints,
              app_args, foreign_apps, foreign_assets, app_accounts, extra_pages):
    if operation == "none":
        operation = None
    else:
        operation = operation_string_to_enum(operation)
    dir_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = os.path.dirname(os.path.dirname(dir_path))
    if approval_program == "none":
        approval_program = None
    elif approval_program:
        with open(dir_path + "/test/features/resources/" + approval_program, "rb") as f:
            approval_program = bytearray(f.read())
    if clear_program == "none":
        clear_program = None
    elif clear_program:
        with open(dir_path + "/test/features/resources/" + clear_program, "rb") as f:
            clear_program = bytearray(f.read())
    if int(local_ints) == 0 and int(local_bytes) == 0:
        local_schema = None
    else:
        local_schema = transaction.StateSchema(num_uints=int(local_ints), num_byte_slices=int(local_bytes))
    if int(global_ints) == 0 and int(global_bytes) == 0:
        global_schema = None
    else:
        global_schema = transaction.StateSchema(num_uints=int(global_ints), num_byte_slices=int(global_bytes))
    if app_args == "none":
        app_args = None
    elif app_args:
        app_args = split_and_process_app_args(app_args)
    if foreign_apps == "none":
        foreign_apps = None
    elif foreign_apps:
        foreign_apps = [int(app) for app in foreign_apps.split(",")]
    if foreign_assets == "none":
        foreign_assets = None
    elif foreign_assets:
        foreign_assets = [int(asset) for asset in foreign_assets.split(",")]
    if app_accounts == "none":
        app_accounts = None
    elif app_accounts:
        app_accounts = [account_pubkey for account_pubkey in app_accounts.split(",")]
    application_id = 0
    if hasattr(context, "current_application_id") and context.current_application_id:
        application_id = context.current_application_id
    sp = context.app_acl.suggested_params()
    context.app_transaction = transaction.ApplicationCallTxn(sender=context.transient_pk, sp=sp,
                                                             index=int(application_id),
                                                             on_complete=operation, local_schema=local_schema,
                                                             global_schema=global_schema,
                                                             approval_program=approval_program,
                                                             clear_program=clear_program,
                                                             app_args=app_args, accounts=app_accounts,
                                                             foreign_apps=foreign_apps,
                                                             foreign_assets=foreign_assets,
                                                             extra_pages=int(extra_pages),
                                                             note=None, lease=None, rekey_to=None)


@step('I sign and submit the transaction, saving the txid. If there is an error it is "{error_string:MaybeString}".')
def sign_submit_save_txid_with_error(context, error_string):
    try:
        signed_app_transaction = context.app_transaction.sign(context.transient_sk)
        context.app_txid = context.app_acl.send_transaction(signed_app_transaction)
    except Exception as e:
        if error_string not in str(e):
            raise RuntimeError("error string " + error_string + " not in actual error " + str(e))


@step('I wait for the transaction to be confirmed.')
def wait_for_app_txn_confirm(context):
    sp = context.app_acl.suggested_params()
    last_round = sp.first
    context.app_acl.status_after_block(last_round+2)
    assert "type" in context.acl.transaction_info(context.transient_pk, context.app_txid)
    assert "type" in context.acl.transaction_by_id(context.app_txid)


@given('I remember the new application ID.')
def remember_app_id(context):
    context.current_application_id = context.acl.pending_transaction_info(context.app_txid)["txresults"]["createdapp"]


@step('The transient account should have the created app "{app_created_bool_as_string:MaybeString}" and total schema byte-slices {byte_slices} and uints {uints}, the application "{application_state:MaybeString}" state contains key "{state_key:MaybeString}" with value "{state_value:MaybeString}"')
def verify_app_txn(context, app_created_bool_as_string, byte_slices, uints, application_state, state_key, state_value):
    account_info = context.app_acl.account_info(context.transient_pk)
    app_total_schema = account_info['apps-total-schema']
    assert app_total_schema['num-byte-slice'] == int(byte_slices)
    assert app_total_schema['num-uint'] == int(uints)

    app_created = app_created_bool_as_string == "true"
    created_apps = account_info['created-apps']
    # If we don't expect the app to exist, verify that it isn't there and exit.
    if not app_created:
        for app in created_apps:
            assert app['id'] != context.current_application_id
        return

    found_app = False
    for app in created_apps:
        found_app = found_app or app['id'] == context.current_application_id
    assert found_app

    # If there is no key to check, we're done.
    if state_key is None or state_key == "":
        return

    found_value_for_key = False
    key_values = list()
    if application_state == "local":
        counter = 0
        for local_state in account_info['apps-local-state']:
            if local_state['id'] == context.current_application_id:
                key_values = local_state['key-value']
                counter = counter + 1
        assert counter == 1
    elif application_state == "global":
        counter = 0
        for created_app in account_info['created-apps']:
            if created_app['id'] == context.current_application_id:
                key_values = created_app['params']['global-state']
                counter = counter + 1
        assert counter == 1
    else:
        raise NotImplementedError("test does not understand application state \"" + application_state + "\"")

    assert len(key_values) > 0

    for key_value in key_values:
        found_key = key_value['key']
        if found_key == state_key:
            found_value_for_key = True
            found_value = key_value['value']
            if found_value['type'] == 1:
                assert found_value['bytes'] == state_value
            elif found_value['type'] == 0:
                assert found_value['uint'] == int(state_value)
    assert found_value_for_key


def load_resource(res):
    """load data from features/resources"""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(dir_path, "..", "features", "resources", res)
    with open(path, "rb") as fin:
        data = fin.read()
    return data


@when(u'I compile a teal program "{program}"')
def compile_step(context, program):
    data = load_resource(program)
    source = data.decode('utf-8')

    try:
        context.response = context.app_acl.compile(source)
        context.status = 200
    except AlgodHTTPError as ex:
        context.status = ex.code
        context.response = dict(result="", hash="")


@then(u'it is compiled with {status} and "{result:MaybeString}" and "{hash:MaybeString}"')
def compile_check_step(context, status, result, hash):
    assert context.status == int(status)
    assert context.response["result"] == result
    assert context.response["hash"] == hash


@when(u'I dryrun a "{kind}" program "{program}"')
def dryrun_step(context, kind, program):
    data = load_resource(program)
    sp = transaction.SuggestedParams(int(1000), int(1), int(100), "", flat_fee=True)
    zero_addr = encoding.encode_address(bytes(32))
    txn = transaction.Transaction(zero_addr, sp, None, None, "pay", None)
    sources = []

    if  kind == "compiled":
        lsig = transaction.LogicSig(data)
        txns = [transaction.LogicSigTransaction(txn, lsig)]
    elif kind == "source":
        txns = [transaction.SignedTransaction(txn, None)]
        sources = [DryrunSource(field_name="lsig", source=data, txn_index=0)]
    else:
        assert False, f"kind {kind} not in (source, compiled)"

    drr = DryrunRequest(txns=txns, sources=sources)
    context.response = context.app_acl.dryrun(drr)


@then(u'I get execution result "{result}"')
def dryrun_check_step(context, result):
    ddr = context.response
    assert len(ddr["txns"]) > 0

    res = ddr["txns"][0]
    if res["logic-sig-messages"] is not None and len(res["logic-sig-messages"]) > 0:
        msgs = res["logic-sig-messages"]
    elif res["app-call-messages"] is not None and len(res["app-call-messages"]) > 0:
        msgs = res["app-call-messages"]

    assert len(msgs) > 0
    assert msgs[-1] == result


@when(u'we make any Dryrun call')
def dryrun_any_call_step(context):
    context.response = context.acl.dryrun(DryrunRequest())


@then(u'the parsed Dryrun Response should have global delta "{creator}" with {action}')
def dryrun_parsed_response(context, creator, action):
    ddr = context.response
    assert len(ddr["txns"]) > 0

    delta = ddr["txns"][0]["global-delta"]
    assert len(delta) > 0
    assert delta[0]["key"] == creator
    assert delta[0]["value"]["action"] == int(action)


@given(u'dryrun test case with "{program}" of type "{kind}"')
def dryrun_test_case_step(context, program, kind):
    if kind not in set(["lsig", "approv", "clearp"]):
        assert False, f"kind {kind} not in (lsig, approv, clearp)"

    prog = load_resource(program)
    # check if source
    if prog[0] > 0x20:
        prog = prog.decode("utf-8")

    context.dryrun_case_program = prog
    context.dryrun_case_kind = kind


@then(u'status assert of "{status}" is succeed')
def dryrun_test_case_status_assert_step(context, status):
    class TestCase(DryrunTestCaseMixin, unittest.TestCase):
        """Mock TestCase to test"""
    ts = TestCase()
    ts.algo_client = context.app_acl

    lsig = None
    app = None
    if context.dryrun_case_kind == "lsig":
        lsig = dict()
    if context.dryrun_case_kind == "approv":
        app = dict()
    elif context.dryrun_case_kind == "clearp":
        app = dict(on_complete=transaction.OnComplete.ClearStateOC)

    if status == "PASS":
        ts.assertPass(context.dryrun_case_program, lsig=lsig, app=app)
    else:
        ts.assertReject(context.dryrun_case_program, lsig=lsig, app=app)


def dryrun_test_case_global_state_assert_impl(context, key, value, action, raises):
    class TestCase(DryrunTestCaseMixin, unittest.TestCase):
        """Mock TestCase to test"""

    ts = TestCase()
    ts.algo_client = context.app_acl

    action = int(action)

    val = dict(action=action)
    if action == 1:
        val["bytes"] = value
    elif action == 2:
        val["uint"] = int(value)

    on_complete = transaction.OnComplete.NoOpOC
    if context.dryrun_case_kind == "clearp":
        on_complete = transaction.OnComplete.ClearStateOC

    raised = False
    try:
        ts.assertGlobalStateContains(
            context.dryrun_case_program, dict(key=key, value=val),
            app=dict(on_complete=on_complete)
        )
    except AssertionError:
        raised = True

    if raises:
        ts.assertTrue(raised, "assertGlobalStateContains expected to raise")


@then(u'global delta assert with "{key}", "{value}" and {action} is succeed')
def dryrun_test_case_global_state_assert_step(context, key, value, action):
    dryrun_test_case_global_state_assert_impl(context, key, value, action, False)


@then(u'global delta assert with "{key}", "{value}" and {action} is failed')
def dryrun_test_case_global_state_assert_fail_step(context, key, value, action):
    dryrun_test_case_global_state_assert_impl(context, key, value, action, True)

@then(u'local delta assert for "{account}" of accounts {index} with "{key}", "{value}" and {action} is succeed')
def dryrun_test_case_local_state_assert_fail_step(context, account, index, key, value, action):
    class TestCase(DryrunTestCaseMixin, unittest.TestCase):
        """Mock TestCase to test"""

    ts = TestCase()
    ts.algo_client = context.app_acl

    action = int(action)

    val = dict(action=action)
    if action == 1:
        val["bytes"] = value
    elif action == 2:
        val["uint"] = int(value)

    on_complete = transaction.OnComplete.NoOpOC
    if context.dryrun_case_kind == "clearp":
        on_complete = transaction.OnComplete.ClearStateOC

    app_idx = 1
    accounts = [
        Account(
            address=ts.default_address(),
            status="Offline",
            apps_local_state=[
                ApplicationLocalState(
                    id=app_idx
                )
            ]
        )
    ] * 2
    accounts[int(index)].address = account

    drr = ts.dryrun_request(
        context.dryrun_case_program,
        sender=accounts[0].address,
        app=dict(
            app_idx=app_idx,
            on_complete=on_complete,
            accounts=accounts
        )
    )

    ts.assertNoError(drr)
    ts.assertLocalStateContains(drr, account, dict(key=key, value=val))

