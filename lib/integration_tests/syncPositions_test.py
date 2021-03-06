from .. import MetaApi
import os
import pytest
import asyncio

token = os.getenv('TOKEN')
login = os.getenv('LOGIN_MT4')
password = os.getenv('PASSWORD_MT4')
server_name = os.getenv('SERVER_MT4') or 'Tradeview-Demo'
broker_srv_file = os.getenv('PATH_TO_BROKER_SRV') or './lib/integration_tests/files/tradeview-demo.broker.srv'
api = MetaApi(token, {'application': 'MetaApi', 'domain': 'project-stock.v2.agiliumlabs.cloud'})


async def check_positions(connection):
    return {'local': len(connection.terminal_state.positions), 'real': len(await connection.get_positions())}


class TestSyncPositions:
    @pytest.mark.asyncio
    async def test_show_correct_positions(self):
        """Should show correct positions amount after opening and closing."""
        if token and login:
            profiles = await api.provisioning_profile_api.get_provisioning_profiles()
            profile = None
            for item in profiles:
                if item.name == server_name:
                    profile = item
                    break
            if not profile:
                profile = await api.provisioning_profile_api.create_provisioning_profile({
                    'name': server_name,
                    'version': 4,
                    'brokerTimezone': 'EET',
                    'brokerDSTSwitchTimezone': 'EET'
                })
                await profile.upload_file('broker.srv', broker_srv_file)
            if profile and profile.status == 'new':
                await profile.upload_file('broker.srv', broker_srv_file)
            accounts = await api.metatrader_account_api.get_accounts()
            account = None
            for item in accounts:
                if item.login == login and item.type.startswith('cloud-g2'):
                    account = item
                    break
            if not account:
                account = await api.metatrader_account_api.create_account({
                    'name': 'Test account-mt4',
                    'type': 'cloud-g2',
                    'login': login,
                    'password': password,
                    'server': server_name,
                    'provisioningProfileId': profile.id,
                    'application': 'MetaApi',
                    'magic': 1000
                })
            await account.deploy()
            await account.wait_connected()
            connection = await account.connect()
            await connection.wait_synchronized({'timeoutInSeconds': 600})
            start_positions = len(connection.terminal_state.positions)
            position_ids = []
            positions = await check_positions(connection)
            assert positions['local'] == positions['real']
            for i in range(10):
                result = await connection.create_market_buy_order('GBPUSD', 0.01, 0.9, 2.0)
                position_ids.append(result['positionId'])
                await asyncio.sleep(0.2)
            positions = await check_positions(connection)
            await asyncio.sleep(3)
            assert positions['local'] == start_positions + 10
            assert positions['real'] == start_positions + 10
            await asyncio.sleep(5)
            await asyncio.gather(*list(map(lambda id: connection.close_position(id), position_ids)))
            await asyncio.sleep(1)

            async def close_position_test(id):
                try:
                    await connection.get_position(id)
                    pytest.fail()
                except Exception as err:
                    pass
            await asyncio.gather(*list(map(lambda id: close_position_test(id), position_ids)))
            positions = await check_positions(connection)
            await asyncio.sleep(3)
            assert positions['local'] == start_positions
            assert positions['real'] == start_positions
            await account.undeploy()
