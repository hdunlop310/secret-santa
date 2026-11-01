"""Unit tests for the draw. No database."""

import itertools
import random
import time
from collections import Counter

import pytest

from app import matching
from app.matching import Bottleneck, NoValidDraw, draw, find_bottleneck, has_swap, is_valid


def mirrored(*pairs):
    return {p for a, b in pairs for p in ((a, b), (b, a))}


def group_block(*members):
    return {(a, b) for a, b in itertools.permutations(members, 2)}


def assert_valid(result, people, blocked):
    assert is_valid(result, people, blocked), result


class TestSecureRandom:
    def test_default_source_is_system_random(self):
        assert isinstance(matching._secure_rng, random.SystemRandom)

    def test_draw_uses_the_secure_source_by_default(self, monkeypatch):
        calls = []

        class Spy(random.SystemRandom):
            def shuffle(self, x):
                calls.append(len(x))
                super().shuffle(x)

        monkeypatch.setattr(matching, "_secure_rng", Spy())
        draw([1, 2, 3, 4], set())
        assert calls


class TestThreePeople:
    def test_always_a_three_cycle(self):
        for _ in range(50):
            result = draw([1, 2, 3], set())
            assert_valid(result, [1, 2, 3], set())
            assert not has_swap(result)

    def test_both_three_cycles_happen(self):
        seen = Counter(tuple(sorted(draw([1, 2, 3], set()).items())) for _ in range(200))
        assert len(seen) == 2

    def test_one_exclusion_forces_the_other_cycle(self):
        for _ in range(20):
            assert draw([1, 2, 3], {(1, 2)}) == {1: 3, 3: 2, 2: 1}

    def test_mirrored_exclusion_makes_three_impossible(self):
        # 1 and 2 can't give to each other, so 1 -> 3 and 2 -> 3: 3 is wanted twice.
        with pytest.raises(NoValidDraw) as exc:
            draw([1, 2, 3], mirrored((1, 2)))
        b = exc.value.bottleneck
        assert b == Bottleneck("give", (1, 2), (3,)) or b == Bottleneck("receive", (1, 2), (3,))

    def test_fewer_than_three_people(self):
        for people in ([], [1], [1, 2]):
            with pytest.raises(NoValidDraw) as exc:
                draw(people, set())
            assert exc.value.bottleneck is None


class TestImpossible:
    def test_someone_blocked_from_everyone(self):
        people = [1, 2, 3, 4, 5]
        blocked = {(1, t) for t in people if t != 1}
        assert find_bottleneck(people, blocked) == Bottleneck("give", (1,), ())

    def test_nobody_can_give_to_someone(self):
        people = [1, 2, 3, 4, 5]
        blocked = {(g, 5) for g in people if g != 5}
        assert find_bottleneck(people, blocked) == Bottleneck("receive", (5,), ())

    def test_two_people_share_their_only_option(self):
        # 1 and 2 can each only give to 3.
        people = [1, 2, 3, 4, 5]
        blocked = {(1, 2), (1, 4), (1, 5), (2, 1), (2, 4), (2, 5)}
        assert find_bottleneck(people, blocked) == Bottleneck("give", (1, 2), (3,))

    def test_household_bigger_than_half_the_group(self):
        # Four of six people are one household: they need four outside giftees, there are two.
        people = list(range(1, 7))
        b = find_bottleneck(people, group_block(1, 2, 3, 4))
        assert b is not None and set(b.people) == {1, 2, 3, 4} and set(b.options) == {5, 6}

    def test_bottleneck_is_reported_as_the_smallest_set(self):
        people = list(range(1, 11))
        blocked = {(g, 10) for g in people if g != 10}  # nobody can give to 10
        b = find_bottleneck(people, blocked)
        assert b == Bottleneck("receive", (10,), ())

    def test_draw_raises_with_bottleneck(self):
        with pytest.raises(NoValidDraw) as exc:
            draw([1, 2, 3, 4], {(1, 2), (1, 3), (1, 4)})
        assert exc.value.bottleneck == Bottleneck("give", (1,), ())

    def test_feasible_sets_report_no_bottleneck(self):
        assert find_bottleneck([1, 2, 3, 4], mirrored((1, 2), (3, 4))) is None


class TestOneWay:
    def test_one_way_exclusion_only_blocks_one_direction(self):
        people = [1, 2, 3, 4]
        blocked = {(1, 2)}
        gave_2_to_1 = False
        for _ in range(100):
            result = draw(people, blocked)
            assert_valid(result, people, blocked)
            assert result[1] != 2
            gave_2_to_1 |= result[2] == 1
        assert gave_2_to_1, "the reverse direction should still be possible"

    def test_one_way_chain_still_drawable(self):
        # 1 can only give to 2, 2 only to 3, ... a forced single cycle.
        people = [1, 2, 3, 4, 5]
        forced = {g: g % 5 + 1 for g in people}
        blocked = {(g, t) for g in people for t in people if g != t and forced[g] != t}
        assert draw(people, blocked) == forced


class TestSwaps:
    def test_no_swaps_in_groups_of_four_or_more_without_exclusions(self):
        for n in (4, 5, 6, 8, 12):
            for _ in range(30):
                result = draw(list(range(n)), set())
                assert not has_swap(result)

    def test_no_swaps_when_only_a_multi_cycle_cover_exists(self):
        # Two households that can't give across: no single cycle through everyone,
        # but two 3-cycles exist, so swaps are avoidable.
        people = list(range(1, 7))
        blocked = {(a, b) for a in (1, 2, 3) for b in (4, 5, 6)} | {
            (b, a) for a in (1, 2, 3) for b in (4, 5, 6)
        }
        for _ in range(30):
            result = draw(people, blocked)
            assert_valid(result, people, blocked)
            assert not has_swap(result)

    def test_swaps_used_only_when_unavoidable(self):
        # 1<->2 and 3<->4 are the only allowed pairs: swaps are the only valid draw.
        people = [1, 2, 3, 4]
        blocked = mirrored((1, 3), (1, 4), (2, 3), (2, 4))
        assert draw(people, blocked) == {1: 2, 2: 1, 3: 4, 4: 3}


class TestLargeGroups:
    def test_fifty_people_with_couples_and_random_exclusions(self):
        rng = random.Random(1234)  # deterministic exclusions; the draw itself stays secure
        people = list(range(1, 51))
        blocked = mirrored(*[(i, i + 1) for i in range(1, 51, 2)])  # 25 couples
        for g, t in itertools.permutations(people, 2):
            if rng.random() < 0.4:
                blocked.add((g, t))
        assert find_bottleneck(people, blocked) is None
        for _ in range(5):
            start = time.monotonic()
            result = draw(people, blocked)
            assert time.monotonic() - start < 1.5
            assert_valid(result, people, blocked)
            assert not has_swap(result)

    def test_fifty_people_sparse_graph(self):
        # Each person may only give to 3 specific others: hard for naive search.
        rng = random.Random(99)
        people = list(range(50))
        cycle = people[:]
        rng.shuffle(cycle)
        allowed = {cycle[i]: {cycle[(i + 1) % 50]} for i in range(50)}  # a hidden cycle
        for g in people:
            while len(allowed[g]) < 3:
                t = rng.choice(people)
                if t != g:
                    allowed[g].add(t)
        blocked = {(g, t) for g in people for t in people if g != t and t not in allowed[g]}
        start = time.monotonic()
        result = draw(people, blocked)
        assert time.monotonic() - start < 1.5
        assert_valid(result, people, blocked)

    def test_fifty_people_impossible(self):
        people = list(range(50))
        blocked = group_block(*range(30))  # a 30-person household in a group of 50
        start = time.monotonic()
        with pytest.raises(NoValidDraw) as exc:
            draw(people, blocked)
        assert time.monotonic() - start < 0.5
        assert len(exc.value.bottleneck.options) < len(exc.value.bottleneck.people)


class TestRandomness:
    def test_every_allowed_giftee_turns_up(self):
        people = list(range(6))
        seen: dict[int, set[int]] = {p: set() for p in people}
        for _ in range(300):
            for g, t in draw(people, set()).items():
                seen[g].add(t)
        assert all(seen[p] == set(people) - {p} for p in people)

    def test_input_order_does_not_decide_the_result(self):
        results = {tuple(sorted(draw([1, 2, 3, 4, 5], set()).items())) for _ in range(50)}
        assert len(results) > 5
