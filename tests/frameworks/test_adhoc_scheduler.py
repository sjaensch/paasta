from __future__ import absolute_import
from __future__ import unicode_literals

import mock
import pytest
from mesos.interface import mesos_pb2

from paasta_tools import utils
from paasta_tools.frameworks import adhoc_scheduler
from paasta_tools.frameworks import native_scheduler


@pytest.fixture
def system_paasta_config():
    return utils.SystemPaastaConfig({
        "docker_registry": "fake",
        "volumes": [],
    }, "/fake/system/configs")


def make_fake_offer(cpu=50000, mem=50000, port_begin=31000, port_end=32000, pool='default'):
    offer = mesos_pb2.Offer()
    offer.slave_id.value = "super big slave"

    cpus_resource = offer.resources.add()
    cpus_resource.name = "cpus"
    cpus_resource.scalar.value = cpu

    mem_resource = offer.resources.add()
    mem_resource.name = "mem"
    mem_resource.scalar.value = mem

    ports_resource = offer.resources.add()
    ports_resource.name = "ports"
    ports_range = ports_resource.ranges.range.add()
    ports_range.begin = port_begin
    ports_range.end = port_end

    if pool is not None:
        pool_attribute = offer.attributes.add()
        pool_attribute.name = "pool"
        pool_attribute.text.value = pool

    return offer


class TestAdhocScheduler(object):
    def test_can_only_launch_task_once(self, system_paasta_config):
        service_name = "service_name"
        instance_name = "instance_name"
        cluster = "cluster"

        service_configs = [
            native_scheduler.NativeServiceConfig(
                service=service_name,
                instance=instance_name,
                cluster=cluster,
                config_dict={
                    "cpus": 0.1,
                    "mem": 50,
                    "instances": 3,
                    "cmd": 'sleep 50',
                    "drain_method": "test"
                },
                branch_dict={
                    'docker_image': 'busybox',
                    'desired_state': 'start',
                },
            )
        ]

        scheduler = adhoc_scheduler.AdhocScheduler(
            service_name=service_name,
            instance_name=instance_name,
            cluster=cluster,
            system_paasta_config=system_paasta_config,
            service_config=service_configs[0],
            dry_run=False
        )

        fake_driver = mock.Mock()

        # Check that offers with invalid pool don't get accepted
        scheduler.start_task(fake_driver, make_fake_offer(pool='notdefault'))
        scheduler.start_task(fake_driver, make_fake_offer(pool=None))
        assert len(scheduler.tasks_with_flags) == 0
        assert scheduler.need_more_tasks() is True
        assert scheduler.task_started is False

        tasks = scheduler.start_task(fake_driver, make_fake_offer())
        assert len(scheduler.tasks_with_flags) == 1
        assert scheduler.need_more_tasks() is False
        assert scheduler.task_started is True

        scheduler.start_task(fake_driver, make_fake_offer())
        assert len(scheduler.tasks_with_flags) == 1
        assert scheduler.need_more_tasks() is False
        assert scheduler.task_started is True

        scheduler.statusUpdate(
            fake_driver,
            mock.Mock(task_id=tasks[0].task_id,
                      state=native_scheduler.TASK_FINISHED))
        assert len(scheduler.tasks_with_flags) == 0
        assert scheduler.need_more_tasks() is True
        assert scheduler.task_started is True

        scheduler.start_task(fake_driver, make_fake_offer())
        assert len(scheduler.tasks_with_flags) == 0
