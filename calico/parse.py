# Copyright (C) 2016-2018 H. Turgut Uyar <uyar@itu.edu.tr>
#
# Calico is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Calico is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Calico.  If not, see <http://www.gnu.org/licenses/>.

"""The module that contains specification parsing components."""

import logging

from ruamel import yaml
from ruamel.yaml import comments

from .base import Action, ActionType, Calico, TestCase


# sigalias: SpecNode = comments.CommentedMap


_logger = logging.getLogger(__name__)


def get_comment_value(node, *, name, field):
    """Get the value of a comment field.

    :sig: (SpecNode, str, str) -> str
    :param node: Node to get the comment from.
    :param name: Name of setting in the node.
    :param field: Name of comment field.
    :return: Value of comment field.
    """
    try:
        comment = node.ca.items[name][2].value[1:].strip()  # remove the leading hash
    except KeyError:
        comment = None
    if comment is not None:
        delim = field + ":"
        if comment.startswith(delim):
            return comment[len(delim) :].strip()
    return None


def parse_spec(content):
    """Parse a test specification.

    :sig: (str) -> Calico
    :param content: Specification to parse.
    :return: Created Calico runner.
    :raise AssertionError: When given specification is invalid.
    """
    try:
        spec = yaml.round_trip_load(content)
    except yaml.YAMLError as e:
        raise AssertionError(str(e))

    if spec is None:
        raise AssertionError("no test specification")

    if not isinstance(spec, comments.CommentedSeq):
        raise AssertionError("invalid test specification")

    action_types = {i: m for m in ActionType for i in m.value}

    runner = Calico()

    tests = [(n, t) for c in spec for n, t in c.items()]
    for test_name, test in tests:
        run = test.get("run")
        assert run is not None, f"{test_name}: no run command"
        assert isinstance(run, str), f"{test_name}: run command must be a string"

        kwargs = {}

        ret = test.get("return")
        if ret is not None:
            assert isinstance(ret, int), f"{test_name}: return value must be an integer"
            kwargs["returns"] = ret

        timeout = get_comment_value(test, name="run", field="timeout")
        if timeout is not None:
            assert timeout.isdigit(), f"{test_name}: timeout value must be an integer"
            kwargs["timeout"] = int(timeout)

        points = test.get("points")
        if points is not None:
            assert isinstance(
                points, (int, float)
            ), f"{test_name}: points value must be numeric"
            kwargs["points"] = points

        blocker = test.get("blocker")
        if blocker is not None:
            assert isinstance(
                blocker, bool
            ), f"{test_name}: blocker value must be true or false"
            kwargs["blocker"] = blocker

        visible = test.get("visible")
        if visible is not None:
            assert isinstance(
                visible, bool
            ), f"{test_name}: visibility value must be true or false"
            kwargs["visible"] = visible

        case = TestCase(test_name, command=run, **kwargs)

        script = test.get("script")
        if script is None:
            # If there's no script, just expect EOF.
            action = Action(ActionType.EXPECT, "_EOF_", timeout=case.timeout)
            case.add_action(action)
        else:
            for step in script:
                action_type, data = [(k, v) for k, v in step.items()][0]
                assert action_type in action_types, f"{test_name}: unknown action type"
                assert isinstance(data, str), f"{test_name}: action data must be a string"

                kwargs = {}

                timeout = get_comment_value(step, name=action_type, field="timeout")
                if timeout is not None:
                    assert timeout.isdigit(), f"{test_name}: timeout value must be an integer"
                    kwargs["timeout"] = int(timeout)

                action = Action(action_types[action_type], data, **kwargs)
                case.add_action(action)

        runner.add_case(case)

    return runner
