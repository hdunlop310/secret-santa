"""The draw: who gives to whom.

A derangement on a directed graph. Each person gives to exactly one person and receives
from exactly one, never themselves and never across a blocked (giver, giftee) pair.

1. Check a draw exists at all with bipartite matching. If not, Hall's theorem gives a
   set of people who are stuck, which is what we show the admin.
2. Shuffle with a cryptographically secure source.
3. Look for one directed cycle through everyone (randomised backtracking with
   restarts). A single cycle has no two-person swaps.
4. Failing that, in groups of 4 or more look for any cover by cycles of length 3+.
5. Failing that, any perfect matching (swaps allowed, because nothing else exists).

Steps 3 and 4 share a time budget of about a second; step 5 is polynomial.
"""

import random
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Pair = tuple[int, int]
Allowed = dict[int, set[int]]

MIN_PEOPLE = 3
TIME_LIMIT = 1.0

_secure_rng = random.SystemRandom()


@dataclass(frozen=True)
class Bottleneck:
    """A set of people with fewer options than members.

    side="give": everyone in `people` can only give to someone in `options`.
    side="receive": everyone in `people` can only receive from someone in `options`.
    len(options) < len(people), so they can't all be served.
    """

    side: Literal["give", "receive"]
    people: tuple[int, ...]
    options: tuple[int, ...]


class NoValidDraw(Exception):
    def __init__(self, bottleneck: Bottleneck | None) -> None:
        super().__init__("no valid draw")
        self.bottleneck = bottleneck


class _OutOfTime(Exception):
    pass


def allowed_map(people: Iterable[int], blocked: Iterable[Pair]) -> Allowed:
    people = list(people)
    blocked_set = set(blocked)
    return {g: {t for t in people if t != g and (g, t) not in blocked_set} for g in people}


def _reverse(allowed: Allowed) -> Allowed:
    reverse: Allowed = {p: set() for p in allowed}
    for g, giftees in allowed.items():
        for t in giftees:
            reverse[t].add(g)
    return reverse


def max_matching(
    allowed: Allowed, order: list[int] | None = None, rng: random.Random | None = None
) -> dict[int, int]:
    """Kuhn's augmenting-path algorithm. Returns giver -> giftee for a maximum matching.

    With `rng`, neighbour order is shuffled so the matching is a random one.
    """
    givers = order if order is not None else list(allowed)
    neighbours = {g: list(allowed[g]) for g in givers}
    if rng is not None:
        for options in neighbours.values():
            rng.shuffle(options)
    owner: dict[int, int] = {}  # giftee -> giver

    def augment(g: int, seen: set[int]) -> bool:
        for t in neighbours[g]:
            if t in seen:
                continue
            seen.add(t)
            if t not in owner or augment(owner[t], seen):
                owner[t] = g
                return True
        return False

    for g in givers:
        augment(g, set())
    return {g: t for t, g in owner.items()}


def _hall_violator(allowed: Allowed, side: Literal["give", "receive"]) -> Bottleneck | None:
    matching = max_matching(allowed)
    if len(matching) == len(allowed):
        return None
    giver_of = {t: g for g, t in matching.items()}
    # Alternating BFS from unmatched givers: allowed edges forward, matched edges back.
    stuck = deque(g for g in allowed if g not in matching)
    seen_givers = set(stuck)
    seen_giftees: set[int] = set()
    while stuck:
        g = stuck.popleft()
        for t in allowed[g]:
            if t in seen_giftees:
                continue
            seen_giftees.add(t)
            back = giver_of.get(t)
            if back is not None and back not in seen_givers:
                seen_givers.add(back)
                stuck.append(back)
    return Bottleneck(side, tuple(sorted(seen_givers)), tuple(sorted(seen_giftees)))


def find_bottleneck(people: Iterable[int], blocked: Iterable[Pair]) -> Bottleneck | None:
    """None if a valid draw exists, else the smallest stuck group we can find."""
    allowed = allowed_map(people, blocked)
    give = _hall_violator(allowed, "give")
    if give is None:
        return None
    receive = _hall_violator(_reverse(allowed), "receive")
    candidates = [b for b in (give, receive) if b is not None]
    return min(candidates, key=lambda b: (len(b.people) + len(b.options), b.side != "give"))


def _hamiltonian_cycle(
    order: list[int], allowed: Allowed, rng: random.Random, deadline: float
) -> list[int] | None:
    n = len(order)
    preds = _reverse(allowed)
    start = order[0]

    def run(step_budget: int) -> list[int] | None:
        path = [start]
        visited = {start}
        steps = 0

        def still_possible(current: int) -> bool:
            unvisited = [p for p in order if p not in visited]
            if not unvisited:
                return start in allowed[current]
            if not (preds[start] - visited):
                return False  # nobody left who could close the cycle back to start
            for u in unvisited:
                if not any(v == start or v not in visited for v in allowed[u]):
                    return False
                if not any(v == current or v not in visited for v in preds[u]):
                    return False
            return True

        def extend(current: int) -> bool:
            nonlocal steps
            steps += 1
            if steps > step_budget:
                raise _OutOfTime
            if steps % 64 == 0 and time.monotonic() > deadline:
                raise _OutOfTime
            if len(path) == n:
                return start in allowed[current]
            options = [v for v in allowed[current] if v not in visited]
            rng.shuffle(options)
            # Warnsdorff's rule: go where onward choices are scarcest first.
            options.sort(key=lambda v: sum(1 for w in allowed[v] if w not in visited))
            for v in options:
                visited.add(v)
                path.append(v)
                if still_possible(v) and extend(v):
                    return True
                visited.remove(v)
                path.pop()
            return False

        return path if extend(start) else None

    budget = 200
    while time.monotonic() < deadline:
        try:
            # A complete search that fails proves no single cycle exists.
            return run(budget)
        except _OutOfTime:
            rng.shuffle(order)
            start = order[0]
            budget *= 2
    return None


def _cover_without_swaps(
    order: list[int], allowed: Allowed, rng: random.Random, deadline: float
) -> dict[int, int] | None:
    """Every giver gets a giftee, no two people swap. Backtracking with restarts."""
    n = len(order)
    preds = _reverse(allowed)

    def run(step_budget: int) -> dict[int, int] | None:
        assign: dict[int, int] = {}
        taken: set[int] = set()
        steps = 0

        def options(g: int) -> list[int]:
            return [t for t in allowed[g] if t not in taken and assign.get(t) != g]

        def solve() -> bool:
            nonlocal steps
            steps += 1
            if steps > step_budget or (steps % 64 == 0 and time.monotonic() > deadline):
                raise _OutOfTime
            if len(assign) == n:
                return True
            free = [g for g in order if g not in assign]
            if any(not any(g not in assign for g in preds[t]) for t in order if t not in taken):
                return False  # some giftee has no giver left
            g = min(free, key=lambda x: (len(options(x)), rng.random()))
            choices = options(g)
            rng.shuffle(choices)
            for t in choices:
                assign[g] = t
                taken.add(t)
                if solve():
                    return True
                del assign[g]
                taken.discard(t)
            return False

        return dict(assign) if solve() else None

    budget = 200
    while time.monotonic() < deadline:
        try:
            return run(budget)
        except _OutOfTime:
            budget *= 2
    return None


def is_valid(assignment: dict[int, int], people: Iterable[int], blocked: Iterable[Pair]) -> bool:
    people = set(people)
    blocked_set = set(blocked)
    return (
        set(assignment) == people
        and set(assignment.values()) == people
        and all(g != t and (g, t) not in blocked_set for g, t in assignment.items())
    )


def has_swap(assignment: dict[int, int]) -> bool:
    return any(assignment.get(t) == g for g, t in assignment.items())


def draw(
    people: Iterable[int],
    blocked: Iterable[Pair],
    *,
    rng: random.Random | None = None,
    time_limit: float = TIME_LIMIT,
) -> dict[int, int]:
    """Return giver -> giftee. Raises NoValidDraw with the bottleneck if impossible."""
    rng = rng or _secure_rng
    people = list(dict.fromkeys(people))
    blocked = set(blocked)
    if len(people) < MIN_PEOPLE:
        raise NoValidDraw(None)
    bottleneck = find_bottleneck(people, blocked)
    if bottleneck is not None:
        raise NoValidDraw(bottleneck)

    allowed = allowed_map(people, blocked)
    order = people[:]
    rng.shuffle(order)
    start = time.monotonic()

    cycle = _hamiltonian_cycle(order[:], allowed, rng, start + time_limit * 0.6)
    if cycle is not None:
        result = {g: cycle[(i + 1) % len(cycle)] for i, g in enumerate(cycle)}
    else:
        result = None
        if len(people) >= 4:
            result = _cover_without_swaps(order, allowed, rng, start + time_limit)
        if result is None:
            rng.shuffle(order)
            result = max_matching(allowed, order, rng)

    if not is_valid(result, people, blocked):  # pragma: no cover - defensive
        raise RuntimeError("matching produced an invalid draw")
    return result
