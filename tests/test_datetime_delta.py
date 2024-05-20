import pickle
import re
from copy import copy, deepcopy

import pytest

from whenever import DateDelta, DateTimeDelta, TimeDelta

from .common import AlwaysEqual, NeverEqual


class TestInit:

    def test_happy_path(self):
        d = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=11,
            hours=4,
            minutes=5,
            seconds=6,
            milliseconds=7,
            microseconds=8,
            nanoseconds=9,
        )
        assert d.date_part() == DateDelta(years=1, months=2, weeks=3, days=11)
        assert d.time_part() == TimeDelta(
            hours=4, minutes=5, seconds=6, nanoseconds=7008009
        )

    def test_zero(self):
        assert DateTimeDelta() == DateTimeDelta(
            years=0,
            months=0,
            weeks=0,
            days=0,
            hours=0,
            minutes=0,
            seconds=0,
            nanoseconds=0,
        )

    def test_negative(self):
        d = DateTimeDelta(
            years=-1,
            months=-2,
            weeks=-3,
            days=-11,
            hours=-4,
            minutes=-5,
            seconds=-6,
            milliseconds=-7,
            microseconds=-8,
            nanoseconds=-9,
        )
        assert d.date_part() == DateDelta(
            years=-1, months=-2, weeks=-3, days=-11
        )
        assert d.time_part() == TimeDelta(
            hours=-4, minutes=-5, seconds=-6, nanoseconds=-7008009
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"years": 1, "days": -2},
            {"years": 1e9, "days": 2},
            {"years": 8, "nanoseconds": 2, "milliseconds": -3},
        ],
    )
    def test_invalid(self, kwargs):
        with pytest.raises((ValueError, OverflowError)):
            DateTimeDelta(**kwargs)


def test_immutable():
    p = DateTimeDelta(
        years=1,
        months=2,
        weeks=3,
        hours=4,
    )
    with pytest.raises(AttributeError):
        p.date_part = DateDelta()  # type: ignore[misc]


def test_equality():
    p = DateTimeDelta(
        years=1,
        months=2,
        weeks=3,
        hours=4,
    )
    same = DateTimeDelta(
        years=1,
        months=2,
        weeks=3,
        hours=4,
    )
    same_total = DateTimeDelta(
        years=1,
        months=2,
        days=3 * 7,
        minutes=60 * 4,
    )
    different = DateTimeDelta(
        years=1,
        months=2,
        weeks=3,
        days=5,
    )
    assert p == same
    assert p == same_total
    assert not p == different
    assert not p == NeverEqual()
    assert p == AlwaysEqual()
    assert not p != same
    assert not p != same_total
    assert p != different
    assert p != NeverEqual()
    assert not p != AlwaysEqual()
    assert hash(p) == hash(same)
    assert hash(p) == hash(same_total)
    assert hash(p) != hash(different)


def test_zero():
    assert DateTimeDelta.ZERO == DateTimeDelta()


def test_bool():
    assert not DateTimeDelta()
    assert DateTimeDelta(days=1)
    assert DateTimeDelta(nanoseconds=1)


@pytest.mark.parametrize(
    "p, expect",
    [
        (DateTimeDelta(), "P0D"),
        (DateTimeDelta(years=-2), "-P2Y"),
        (DateTimeDelta(days=1), "P1D"),
        (DateTimeDelta(hours=1), "PT1H"),
        (DateTimeDelta(minutes=1), "PT1M"),
        (DateTimeDelta(seconds=1), "PT1S"),
        (DateTimeDelta(microseconds=1), "PT0.000001S"),
        (DateTimeDelta(microseconds=4300), "PT0.0043S"),
        (DateTimeDelta(weeks=1), "P7D"),
        (DateTimeDelta(months=1), "P1M"),
        (DateTimeDelta(years=1), "P1Y"),
        (
            DateTimeDelta(
                years=1,
                months=2,
                weeks=3,
                days=4,
                hours=5,
                minutes=6,
                seconds=7,
                microseconds=800_000,
            ),
            "P1Y2M25DT5H6M7.8S",
        ),
        (
            DateTimeDelta(
                years=1,
                months=2,
                weeks=3,
                days=4,
                hours=5,
                minutes=6,
                seconds=7,
                microseconds=8,
                nanoseconds=9,
            ),
            "P1Y2M25DT5H6M7.000008009S",
        ),
        (
            DateTimeDelta(months=2, weeks=3, minutes=6, seconds=7),
            "P2M21DT6M7S",
        ),
        (DateTimeDelta(microseconds=-45), "-PT0.000045S"),
        (
            DateTimeDelta(
                years=-3,
                months=2,
                weeks=-3,
                minutes=-6,
                seconds=7,
                microseconds=-45,
            ),
            "-P2Y10M21DT5M53.000045S",
        ),
    ],
)
def test_default_format(p, expect):
    assert p.default_format() == expect
    assert p.common_iso8601() == expect
    assert str(p) == expect


class TestFromDefaultFormatAndCommonISO8601:

    def test_empty(self):
        assert DateTimeDelta.from_default_format("P0D") == DateTimeDelta()
        assert DateTimeDelta.from_common_iso8601("P0D") == DateTimeDelta()

    @pytest.mark.parametrize(
        "input, expect",
        [
            ("P0D", DateTimeDelta()),
            ("PT0S", DateTimeDelta()),
            ("P2Y", DateTimeDelta(years=2)),
            ("P1M", DateTimeDelta(months=1)),
            ("P1W", DateTimeDelta(weeks=1)),
            ("P1D", DateTimeDelta(days=1)),
            ("PT1H", DateTimeDelta(hours=1)),
            ("PT0H", DateTimeDelta()),
            ("PT1M", DateTimeDelta(minutes=1)),
            ("PT1S", DateTimeDelta(seconds=1)),
            ("PT0.000001S", DateTimeDelta(microseconds=1)),
            ("PT0.0043S", DateTimeDelta(microseconds=4300)),
        ],
    )
    def test_single_unit(self, input, expect):
        assert DateTimeDelta.from_default_format(input) == expect
        assert DateTimeDelta.from_common_iso8601(input) == expect

    @pytest.mark.parametrize(
        "input, expect",
        [
            (
                "P1Y2M3W4DT5H6M7S",
                DateTimeDelta(
                    years=1,
                    months=2,
                    weeks=3,
                    days=4,
                    hours=5,
                    minutes=6,
                    seconds=7,
                ),
            ),
            (
                "P1Y2M3W4DT5H6M7.000008S",
                DateTimeDelta(
                    years=1,
                    months=2,
                    weeks=3,
                    days=4,
                    hours=5,
                    minutes=6,
                    seconds=7,
                    microseconds=8,
                ),
            ),
            (
                "P2M3WT6M7S",
                DateTimeDelta(months=2, weeks=3, minutes=6, seconds=7),
            ),
            ("-PT0.00004501S", DateTimeDelta(nanoseconds=-45_010)),
            (
                "-P3Y2M3WT6M6.999955S",
                DateTimeDelta(
                    years=-3,
                    months=-2,
                    weeks=-3,
                    minutes=-6,
                    seconds=-7,
                    microseconds=45,
                ),
            ),
            ("-P2MT1M", DateTimeDelta(months=-2, minutes=-1)),
            (
                "+P2Y3W0DT0.999S",
                DateTimeDelta(
                    years=2, weeks=3, seconds=1, microseconds=-1_000
                ),
            ),
            (
                "-P1Y3MT4.999S",
                DateTimeDelta(
                    years=-1, months=-3, seconds=-4, microseconds=-999_000
                ),
            ),
        ],
    )
    def test_multiple_units(self, input, expect):
        assert DateTimeDelta.from_default_format(input) == expect
        assert DateTimeDelta.from_common_iso8601(input) == expect

    @pytest.mark.parametrize(
        "s",
        [
            "P",
            "PT0.0000000001S",  # too many decimal places
            "",
            "3D",
            "-PT",
            "PT",
            "+PT",
            "P1YX3M",  # invalid separator
        ],
    )
    def test_invalid(self, s):
        with pytest.raises(
            ValueError, match=r"Invalid format.*" + re.escape(repr(s))
        ):
            DateTimeDelta.from_default_format(s)


class TestAdd:

    def test_same_type(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=800_000,
        )
        q = DateTimeDelta(
            years=-1,
            months=3,
            weeks=-1,
            minutes=0,
            seconds=-1,
            microseconds=-300_000,
        )
        assert p + q == DateTimeDelta(
            months=5,
            weeks=2,
            days=4,
            hours=5,
            minutes=6,
            seconds=6,
            microseconds=500_000,
        )

    def test_time_delta(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=800_000,
        )
        q = TimeDelta(
            hours=1,
            minutes=2,
            seconds=3,
            microseconds=400_000,
        )
        assert p + q == DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=6,
            minutes=8,
            seconds=11,
            microseconds=200_000,
        )
        assert q + p == p + q

    def test_date_delta(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=800_000,
        )
        q = DateDelta(months=9, days=1)
        assert p + q == DateTimeDelta(
            years=1,
            months=11,
            weeks=3,
            days=5,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=800_000,
        )
        assert q + p == p + q

    def test_unsupported(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=800_000,
        )
        with pytest.raises(TypeError, match="unsupported operand"):
            p + 32  # type: ignore[operator]

        with pytest.raises(TypeError, match="unsupported operand"):
            32 + p  # type: ignore[operator]


class TestSubtract:

    def test_same_type(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=300_000,
        )
        q = DateTimeDelta(
            years=-1,
            months=3,
            weeks=-1,
            minutes=0,
            seconds=-1,
            microseconds=800_000,
        )
        assert p - q == DateTimeDelta(
            years=1,
            months=11,
            weeks=4,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=500_000,
        )
        assert q - p == DateTimeDelta(
            years=-1,
            months=-11,
            weeks=-4,
            days=-4,
            hours=-5,
            minutes=-6,
            seconds=-7,
            microseconds=-500_000,
        )

    def test_timedelta(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=300_000,
        )
        q = TimeDelta(
            hours=1,
            minutes=2,
            seconds=3,
            microseconds=800_000,
        )
        assert p - q == DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=4,
            minutes=4,
            seconds=3,
            microseconds=500_000,
        )
        assert q - p == DateTimeDelta(
            years=-1,
            months=-2,
            weeks=-3,
            days=-4,
            hours=-4,
            minutes=-4,
            seconds=-3,
            microseconds=-500_000,
        )

    def test_datedelta(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=300_000,
        )
        q = DateDelta(
            years=-1,
            months=2,
            weeks=-1,
            days=0,
        )
        assert p - q == DateTimeDelta(
            years=2,
            weeks=4,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=300_000,
        )
        assert q - p == DateTimeDelta(
            years=-2,
            weeks=-4,
            days=-4,
            hours=-5,
            minutes=-6,
            seconds=-7,
            microseconds=-300_000,
        )

    def test_datetimedelta_mixed_sign(self):
        # ok
        assert (
            DateTimeDelta(months=-1) - DateTimeDelta(months=-1)
            == DateTimeDelta()
        )
        assert DateTimeDelta(months=-1, seconds=-34) - DateTimeDelta(
            months=-1, seconds=-35
        ) == DateTimeDelta(seconds=1)

        # not ok
        with pytest.raises(ValueError, match="sign"):
            DateTimeDelta(months=2, seconds=3) - DateTimeDelta(
                months=1, seconds=4
            )

    def test_unsupported(self):
        p = DateTimeDelta(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=300_000,
        )
        with pytest.raises(TypeError, match="unsupported operand"):
            p - 32  # type: ignore[operator]

        with pytest.raises(TypeError, match="unsupported operand"):
            32 - p  # type: ignore[operator]


def test_multiplication():
    p = DateTimeDelta(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=300_000,
    )
    assert p * 3 == DateTimeDelta(
        years=3,
        months=6,
        weeks=9,
        days=12,
        hours=15,
        minutes=18,
        seconds=21,
        microseconds=900_000,
    )
    assert 3 * p == p * 3


def test_negate():
    p = DateTimeDelta(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert -p == DateTimeDelta(
        years=-1,
        months=-2,
        weeks=-3,
        days=-4,
        hours=-5,
        minutes=-6,
        seconds=-7,
        microseconds=-800_000,
    )


@pytest.mark.parametrize(
    "d",
    [DateTimeDelta.ZERO, DateTimeDelta(years=1, seconds=7)],
)
def test_positive(d):
    assert +d is d


def test_abs():
    p = DateTimeDelta(
        years=-1,
        months=-2,
        weeks=-3,
        days=-4,
        hours=-5,
        minutes=-6,
        seconds=-7,
        microseconds=-800_000,
    )
    assert abs(p) == DateTimeDelta(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert abs(-p) == -p


def test_in_months_days_secs_nanos():
    p = DateTimeDelta(
        years=1,
        months=-2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.in_months_days_secs_nanos() == (
        10,
        3 * 7 + 4,
        5 * 3_600 + 6 * 60 + 7,
        800_000_000,
    )
    assert DateTimeDelta(
        seconds=-3, nanoseconds=2
    ).in_months_days_secs_nanos() == (0, 0, -2, -999_999_998)


def test_copy():
    p = DateTimeDelta(
        years=1,
        months=-2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert copy(p) is p
    assert deepcopy(p) is p


def test_pickle():
    p = DateTimeDelta(
        years=1,
        months=-2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    dumped = pickle.dumps(p)
    assert len(dumped) < 60
    assert pickle.loads(dumped) == p


def test_compatible_unpickle():
    dumped = (
        b"\x80\x04\x950\x00\x00\x00\x00\x00\x00\x00\x8c\x08whenever\x94\x8c\x0e_unp"
        b"kl_dtdelta\x94\x93\x94(K\nK\x19M\xbfGJ\x00\x08\xaf/t\x94R\x94."
    )
    assert pickle.loads(dumped) == DateTimeDelta(
        years=1,
        months=-2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
