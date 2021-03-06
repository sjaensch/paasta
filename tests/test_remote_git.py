# -*- coding: UTF-8 -*-
# Copyright 2015-2016 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import absolute_import
from __future__ import unicode_literals

import mock

from paasta_tools import remote_git


def test_make_determine_wants_func():
    refs = {
        b'refs/heads/foo': b'abcde',
        b'refs/tags/blah': b'12345',
    }
    # nothing changed, so nothing should change
    determine_wants = remote_git._make_determine_wants_func(lambda x: x)
    assert determine_wants(refs) == refs

    # don't delete anything.
    determine_wants = remote_git._make_determine_wants_func(lambda x: {})
    assert determine_wants(refs) == refs

    # don't modify anything existing.
    determine_wants = remote_git._make_determine_wants_func(
        lambda x: dict((k, v[::-1]) for k, v in x.items())
    )
    assert determine_wants(refs) == refs

    # only allow new things
    determine_wants = remote_git._make_determine_wants_func(
        lambda x: {'foo': 'bar'}
    )
    actual = determine_wants(refs)
    expected = dict(refs)
    expected.update({b'foo': b'bar'})
    assert actual == expected


def test_non_ascii_tags():
    """git tags can be UTF-8 encoded"""

    with mock.patch(
        'dulwich.client.get_transport_and_path',
        autospec=True,
        return_value=(
            mock.Mock(**{'fetch_pack.return_value': {'☃'.encode('UTF-8'): b'deadbeef'}}),
            'path',
        ),
    ):
        ret = remote_git.list_remote_refs('git-url')
        assert ret == {'☃': 'deadbeef'}


def test_make_force_push_mutate_refs_func_overwrites_shas():
    targets = ['refs/heads/targeta', 'refs/tags/targetb']
    input_refs = {
        b'refs/heads/foo': b'12345',
        b'refs/heads/targeta': b'12345',
        b'refs/tags/targetb': b'12345',
        b'refs/heads/ignored': b'12345',
        b'refs/tags/blah': b'12345',
    }
    expected = {
        b'refs/heads/foo': b'12345',
        b'refs/heads/targeta': b'newsha',
        b'refs/tags/targetb': b'newsha',
        b'refs/heads/ignored': b'12345',
        b'refs/tags/blah': b'12345',
    }

    mutate_refs_func = remote_git.make_force_push_mutate_refs_func(
        targets=targets,
        sha='newsha',
    )
    actual = mutate_refs_func(input_refs)
    assert actual == expected
    assert all([isinstance(k, bytes) for k in actual])


@mock.patch('dulwich.client', autospec=True)
@mock.patch('paasta_tools.remote_git._make_determine_wants_func', autospec=True)
def test_create_remote_refs_is_safe_by_default(mock_make_determine_wants_func, mock_dulwich_client):
    git_url = 'fake_git_url'
    fake_git_client = mock.Mock()
    mock_dulwich_client.get_transport_and_path.return_value = fake_git_client, 'fake_path'
    remote_git.create_remote_refs(
        git_url=git_url,
        ref_mutator=mock.sentinel.ref_mutator,
    )
    fake_git_client.send_pack.assert_called_once_with(
        'fake_path', mock_make_determine_wants_func.return_value, mock.ANY)


@mock.patch('dulwich.client', autospec=True)
def test_create_remote_refs_allows_force_and_uses_the_provided_mutator(mock_dulwich_client):
    git_url = 'fake_git_url'
    fake_git_client = mock.Mock()
    mock_dulwich_client.get_transport_and_path.return_value = fake_git_client, 'fake_path'
    remote_git.create_remote_refs(
        git_url=git_url,
        ref_mutator=mock.sentinel.ref_mutator,
        force=True,
    )
    fake_git_client.send_pack.assert_called_once_with(
        'fake_path', mock.sentinel.ref_mutator, mock.ANY)
