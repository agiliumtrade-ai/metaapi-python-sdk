import pytest
from mock import patch
from .packetLogger import PacketLogger
from typing import Dict
from copy import deepcopy
from ...metaApi.models import date
from asyncio import sleep
import shutil
import json
import os
from freezegun import freeze_time
start_time = '2020-10-10 00:00:01.000'
packets = {}
packet_logger: PacketLogger = None
folder = './.metaapi/logs/'


def change_sn(obj: Dict, sequence_number: int):
    new_obj = deepcopy(obj)
    new_obj['sequenceNumber'] = sequence_number
    return new_obj


@pytest.fixture(autouse=True)
async def run_around_tests():
    with patch('lib.clients.metaApi.packetLogger.asyncio.sleep', new=lambda x: sleep(x / 50)):
        global packet_logger
        packet_logger = PacketLogger({'fileNumberLimit': 3, 'logFileSizeInHours': 4})
        packet_logger.start()
        global packets
        packets = {
            'accountInformation': {
                'type': 'accountInformation',
                'accountInformation': {
                    'broker': 'Broker',
                    'currency': 'USD',
                    'server': 'Broker-Demo',
                    'balance': 20000,
                    'equity': 25000
                },
                'accountId': 'accountId'
            },
            'prices': {
                'type': 'prices',
                'prices': [{
                    'symbol': 'EURUSD',
                    'bid': 1.18,
                    'ask': 1.19
                },
                    {
                        'symbol': 'USDJPY',
                        'bid': 103.222,
                        'ask': 103.25
                    }],
                'accountId': 'accountId',
                'sequenceNumber': 1
            },
            'status': {
                'status': 'connected',
                'type': 'status',
                'accountId': 'accountId'
            },
            'specifications': {
                'specifications': [],
                'type': 'specifications',
                'accountId': 'accountId',
                'sequenceNumber': 1
            }
        }
        yield
        packet_logger.stop()
        shutil.rmtree(folder)


class TestPacketLogger:
    @pytest.mark.asyncio
    async def test_record_packet(self):
        """Should record packet."""
        packet_logger.log_packet(packets['accountInformation'])
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == packets['accountInformation']

    @pytest.mark.asyncio
    async def test_record_price_packets_without_sn(self):
        """Should record price packets without sequence number."""
        packet = packets['prices']
        del packet['sequenceNumber']
        packet_logger.log_packet(packet)
        packet_logger.log_packet(packets['prices'])
        packet_logger.log_packet(packet)
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == packet

    @pytest.mark.asyncio
    async def test_not_record_status(self):
        """Should not record status."""
        packet_logger.log_packet(packets['status'])
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_record_short_specifications(self):
        """Should record shortened specifications."""
        packet_logger.log_packet(packets['specifications'])
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == {'type': 'specifications', 'sequenceNumber': 1}

    @pytest.mark.asyncio
    async def test_record_full_specifications(self):
        """Should record full specifications if compress disabled."""
        global packet_logger
        packet_logger.stop()
        packet_logger = PacketLogger({'compressSpecifications': False})
        packet_logger.start()
        packet_logger.log_packet(packets['specifications'])
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == packets['specifications']

    @pytest.mark.asyncio
    async def test_record_single_price_packet(self):
        """Should record single price packet."""
        packet_logger.log_packet(packets['prices'])
        packet_logger.log_packet(packets['accountInformation'])
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == packets['prices']
        assert json.loads(result[1]['message']) == packets['accountInformation']

    @pytest.mark.asyncio
    async def test_record_range_of_price_packets(self):
        """Should record range of price packets."""
        packet_logger.log_packet(packets['prices'])
        packet_logger.log_packet(change_sn(packets['prices'], 2))
        packet_logger.log_packet(change_sn(packets['prices'], 3))
        packet_logger.log_packet(change_sn(packets['prices'], 4))
        packet_logger.log_packet(change_sn(packets['prices'], 5))
        packet_logger.log_packet(packets['accountInformation'])
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == packets['prices']
        assert json.loads(result[1]['message']) == change_sn(packets['prices'], 5)
        assert result[2]['message'] == 'Recorded price packets 1-5'
        assert json.loads(result[3]['message']) == packets['accountInformation']

    @pytest.mark.asyncio
    async def test_record_all_price_packets(self):
        """Should record all price packets if compress disabled."""
        global packet_logger
        packet_logger.stop()
        packet_logger = PacketLogger({'compressPrices': False})
        packet_logger.start()
        packet_logger.log_packet(packets['prices'])
        packet_logger.log_packet(change_sn(packets['prices'], 2))
        packet_logger.log_packet(change_sn(packets['prices'], 3))
        packet_logger.log_packet(change_sn(packets['prices'], 4))
        packet_logger.log_packet(change_sn(packets['prices'], 5))
        packet_logger.log_packet(packets['accountInformation'])
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == packets['prices']
        assert json.loads(result[1]['message']) == change_sn(packets['prices'], 2)
        assert json.loads(result[2]['message']) == change_sn(packets['prices'], 3)
        assert json.loads(result[3]['message']) == change_sn(packets['prices'], 4)
        assert json.loads(result[4]['message']) == change_sn(packets['prices'], 5)
        assert json.loads(result[5]['message']) == packets['accountInformation']

    @pytest.mark.asyncio
    async def test_stop_price_if_sn_doesnt_match(self):
        """Should stop price packet sequence if price sequence number doesnt match."""
        packet_logger.log_packet(packets['prices'])
        packet_logger.log_packet(change_sn(packets['prices'], 2))
        packet_logger.log_packet(change_sn(packets['prices'], 3))
        packet_logger.log_packet(change_sn(packets['prices'], 4))
        packet_logger.log_packet(change_sn(packets['prices'], 6))
        await sleep(0.04)
        result = await packet_logger.read_logs('accountId')
        assert json.loads(result[0]['message']) == packets['prices']
        assert json.loads(result[1]['message']) == change_sn(packets['prices'], 4)
        assert result[2]['message'] == 'Recorded price packets 1-4'
        assert json.loads(result[3]['message']) == change_sn(packets['prices'], 6)

    @pytest.mark.asyncio
    async def test_read_logs_within_bounds(self):
        """Should read logs within bounds."""
        with freeze_time(start_time) as frozen_datetime:
            packet_logger.log_packet(packets['accountInformation'])
            packet_logger.log_packet(packets['accountInformation'])
            await sleep(0.04)
            frozen_datetime.move_to('2020-10-10 01:00:01.000')
            packet_logger.log_packet(packets['accountInformation'])
            packet_logger.log_packet(packets['accountInformation'])
            packet_logger.log_packet(packets['accountInformation'])
            packet_logger.log_packet(packets['accountInformation'])
            packet_logger.log_packet(packets['accountInformation'])
            await sleep(0.04)
            frozen_datetime.move_to('2020-10-10 01:30:01.000')
            packet_logger.log_packet(packets['accountInformation'])
            packet_logger.log_packet(packets['accountInformation'])
            packet_logger.log_packet(packets['accountInformation'])
            await sleep(0.04)
            result = await packet_logger.read_logs('accountId', date('2020-10-10 00:30:00.000'),
                                                   date('2020-10-10 01:30:00.000'))
            assert len(result) == 5
            result_after = await packet_logger.read_logs('accountId', date('2020-10-10 00:30:00.000'))
            assert len(result_after) == 8
            result_before = await packet_logger.read_logs('accountId', None, date('2020-10-10 01:30:00.000'))
            assert len(result_before) == 7

    @pytest.mark.asyncio
    async def test_delete_expired_folders(self):
        """Should delete expired folders."""
        with freeze_time(start_time) as frozen_datetime:
            packet_logger.log_packet(packets['accountInformation'])
            await sleep(0.21)
            folder_list = os.listdir(folder)
            assert folder_list == ['2020-10-10-00']

            frozen_datetime.move_to('2020-10-10 05:00:01.000')
            packet_logger.log_packet(packets['accountInformation'])
            await sleep(0.21)
            folder_list = os.listdir(folder)
            folder_list.sort()
            assert os.listdir(folder) == ['2020-10-10-00', '2020-10-10-01']

            frozen_datetime.move_to('2020-10-10 09:00:01.000')
            packet_logger.log_packet(packets['accountInformation'])
            await sleep(0.21)
            folder_list = os.listdir(folder)
            folder_list.sort()
            assert folder_list == ['2020-10-10-00', '2020-10-10-01', '2020-10-10-02']

            frozen_datetime.move_to('2020-10-10 13:00:01.000')
            packet_logger.log_packet(packets['accountInformation'])
            await sleep(0.21)
            folder_list = os.listdir(folder)
            folder_list.sort()
            assert folder_list == ['2020-10-10-01', '2020-10-10-02', '2020-10-10-03']
