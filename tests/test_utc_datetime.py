import pickle
import re
from copy import copy, deepcopy
from datetime import datetime as py_datetime, timedelta, timezone
from unittest import mock

import pytest
from hypothesis import given
from hypothesis.strategies import integers, text

from whenever import (
    Date,
    LocalSystemDateTime,
    NaiveDateTime,
    OffsetDateTime,
    Time,
    UTCDateTime,
    ZonedDateTime,
    days,
    hours,
    seconds,
    years,
)

from .common import (
    AlwaysEqual,
    AlwaysLarger,
    AlwaysSmaller,
    NeverEqual,
    local_ams_tz,
    local_nyc_tz,
)

BIG_INT = 1 << 64 + 1  # a big int that may cause an overflow error


class TestInit:
    def test_basic(self):
        d = UTCDateTime(2020, 8, 15, 5, 12, 30, 450)
        assert d.year == 2020
        assert d.month == 8
        assert d.day == 15
        assert d.hour == 5
        assert d.minute == 12
        assert d.second == 30
        assert d.nanosecond == 450

    def test_defaults(self):
        assert UTCDateTime(2020, 8, 15) == UTCDateTime(2020, 8, 15, 0, 0, 0, 0)

    @pytest.mark.parametrize(
        "kwargs, keyword",
        [
            (dict(year=0), "date"),
            (dict(year=10_000), "date"),
            (dict(year=BIG_INT), "too large|date"),
            (dict(year=-BIG_INT), "too large|date"),
            (dict(month=0), "date"),
            (dict(month=13), "date"),
            (dict(month=BIG_INT), "too large|date"),
            (dict(month=-BIG_INT), "too large|date"),
            (dict(day=0), "date"),
            (dict(day=32), "date"),
            (dict(day=BIG_INT), "too large|date"),
            (dict(day=-BIG_INT), "too large|date"),
            (dict(hour=-1), "time"),
            (dict(hour=24), "time"),
            (dict(hour=BIG_INT), "too large|time"),
            (dict(hour=-BIG_INT), "too large|time"),
            (dict(minute=-1), "time"),
            (dict(minute=60), "time"),
            (dict(minute=BIG_INT), "too large|time"),
            (dict(minute=-BIG_INT), "too large|time"),
            (dict(second=-1), "time"),
            (dict(second=60), "time"),
            (dict(second=BIG_INT), "too large|time"),
            (dict(second=-BIG_INT), "too large|time"),
            (dict(nanosecond=-1), "time"),
            (dict(nanosecond=1_000_000_000), "time"),
            (dict(nanosecond=BIG_INT), "too large|time"),
            (dict(nanosecond=-BIG_INT), "too large|time"),
        ],
    )
    def test_bounds(self, kwargs, keyword):
        defaults = {
            "year": 1,
            "month": 1,
            "day": 1,
            "hour": 0,
            "minute": 0,
            "second": 0,
            "nanosecond": 0,
        }

        with pytest.raises((ValueError, OverflowError), match=keyword):
            UTCDateTime(**{**defaults, **kwargs})

    def test_kwargs(self):
        d = UTCDateTime(
            year=2020, month=8, day=15, hour=5, minute=12, second=30
        )
        assert d == UTCDateTime(2020, 8, 15, 5, 12, 30)

    def test_wrong_types(self):
        with pytest.raises(TypeError):
            UTCDateTime("2020", 8, 15, 5, 12, 30)  # type: ignore[arg-type]

    @given(
        integers(),
        integers(),
        integers(),
        integers(),
        integers(),
        integers(),
        integers(),
    )
    def test_fuzzing(
        self, year, month, day, hour, minute, second, microsecond
    ):
        try:
            UTCDateTime(year, month, day, hour, minute, second, microsecond)
        except (ValueError, OverflowError):
            pass


def test_offset():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert d.offset == hours(0)


def test_immutable():
    d = UTCDateTime(2020, 8, 15)
    with pytest.raises(AttributeError):
        d.year = 2021  # type: ignore[misc]


def test_date_and_time():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert d.date() == Date(2020, 8, 15)
    assert d.time() == Time(23, 12, 9, 987_654)


@pytest.mark.parametrize(
    "d, expected",
    [
        (
            UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654),
            "2020-08-15T23:12:09.000987654Z",
        ),
        (
            UTCDateTime(2020, 8, 15, 23, 12, 9, 980_000_000),
            "2020-08-15T23:12:09.98Z",
        ),
        (UTCDateTime(2020, 8, 15), "2020-08-15T00:00:00Z"),
        (UTCDateTime(2020, 8, 15, 23, 12, 9), "2020-08-15T23:12:09Z"),
    ],
)
def test_default_format(d: UTCDateTime, expected: str):
    assert str(d) == expected
    assert d.default_format() == expected


class TestFromDefaultFormat:
    @pytest.mark.parametrize(
        "s, expect",
        [
            # full precision
            (
                "2020-08-15T23:12:09.987654001Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654_001),
            ),
            # microsecond precision
            (
                "2020-08-15T23:12:09.987654Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654_000),
            ),
            # no fractions
            ("2020-08-15T23:12:09Z", UTCDateTime(2020, 8, 15, 23, 12, 9)),
            # no time
            ("2020-08-15T00:00:00Z", UTCDateTime(2020, 8, 15)),
            # millisecond precision
            (
                "2020-08-15T23:12:09.344Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 344_000_000),
            ),
            # single fraction
            (
                "2020-08-15T23:12:09.3Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 300_000_000),
            ),
            ("2020-08-15T23:12:09Z", UTCDateTime(2020, 8, 15, 23, 12, 9)),
        ],
    )
    def test_valid(self, s, expect):
        assert UTCDateTime.from_default_format(s) == expect

    @pytest.mark.parametrize(
        "s",
        [
            "2020-8-15 T23:12:45Z",  # invalid padding
            "2020-8-15 T23:12:45Z",  # invalid padding
            "2020-08-15 23:12:45Z",  # missing separator
            "2020-08-15T23:12Z",  # no seconds
            "2020-08-15Z",  # no time
            "2020-08Z",
            "2020Z",  # no time or date
            "Z",  # no time or date
            "",  # empty
            "garbage",  # garbage
            "2020-08-15T23:12:09.1234567890Z",  # too precise
            "2020-09-15T22:44:20z",  # lowercase z
            "2020-09-15T22:44:20",  # no trailing z
        ],
    )
    def test_invalid(self, s):
        with pytest.raises(
            ValueError,
            match=r"Invalid format.*" + re.escape(s),
        ):
            UTCDateTime.from_default_format(s)

    @given(text())
    def test_fuzzing(self, s: str):
        with pytest.raises(
            ValueError,
            match=r"Invalid format.*" + re.escape(repr(s)),
        ):
            UTCDateTime.from_default_format(s)


class TestEquality:
    def test_same(self):
        d = UTCDateTime(2020, 8, 15)
        same = UTCDateTime(2020, 8, 15)
        assert d == same
        assert not d != same
        assert hash(d) == hash(same)

    def test_different(self):
        d = UTCDateTime(2020, 8, 15)
        different = UTCDateTime(2020, 8, 16)
        assert d != different
        assert not d == different
        assert hash(d) != hash(different)

    def test_notimplemented(self):
        d = UTCDateTime(2020, 8, 15)
        assert d == AlwaysEqual()
        assert d != NeverEqual()
        assert not d == NeverEqual()
        assert not d != AlwaysEqual()

        assert not d == 3  # type: ignore[comparison-overlap]
        assert d != 3  # type: ignore[comparison-overlap]
        assert not 3 == d  # type: ignore[comparison-overlap]
        assert 3 != d  # type: ignore[comparison-overlap]
        assert not None == d  # type: ignore[comparison-overlap]
        assert None != d  # type: ignore[comparison-overlap]

    def test_zoned(self):
        d: UTCDateTime | ZonedDateTime = UTCDateTime(2023, 10, 29, 1, 15)
        zoned_same = ZonedDateTime(
            2023, 10, 29, 2, 15, tz="Europe/Paris", disambiguate="later"
        )
        zoned_different = ZonedDateTime(
            2023, 10, 29, 2, 15, tz="Europe/Paris", disambiguate="earlier"
        )
        assert d == zoned_same
        assert not d != zoned_same
        assert not d == zoned_different
        assert d != zoned_different

        assert hash(d) == hash(zoned_same)
        assert hash(d) != hash(zoned_different)

    @local_ams_tz()
    def test_local(self):
        d: UTCDateTime | LocalSystemDateTime = UTCDateTime(2023, 10, 29, 1, 15)
        local_same = LocalSystemDateTime(
            2023, 10, 29, 2, 15, disambiguate="later"
        )
        local_different = LocalSystemDateTime(
            2023, 10, 29, 2, 15, disambiguate="earlier"
        )
        assert d == local_same
        assert not d != local_same
        assert not d == local_different
        assert d != local_different

        assert hash(d) == hash(local_same)
        assert hash(d) != hash(local_different)

    def test_offset(self):
        d: UTCDateTime | OffsetDateTime = UTCDateTime(2023, 4, 5, 4)
        offset_same = OffsetDateTime(2023, 4, 5, 6, offset=+2)
        offset_different = OffsetDateTime(2023, 4, 5, 4, offset=-3)
        assert d == offset_same
        assert not d != offset_same
        assert not d == offset_different
        assert d != offset_different

        assert hash(d) == hash(offset_same)
        assert hash(d) != hash(offset_different)


class TestTimestamp:

    def test_default_seconds(self):
        assert UTCDateTime(1970, 1, 1).timestamp() == 0
        assert (
            UTCDateTime(2020, 8, 15, 12, 8, 30, 45_123).timestamp()
            == 1_597_493_310
        )
        assert UTCDateTime.MAX.timestamp() == 253402300799
        assert UTCDateTime.MIN.timestamp() == -62135596800

    def test_millis(self):
        assert UTCDateTime(1970, 1, 1).timestamp_millis() == 0
        assert (
            UTCDateTime(2020, 8, 15, 12, 8, 30, 45_123_987).timestamp_millis()
            == 1_597_493_310_045
        )
        assert UTCDateTime.MAX.timestamp_millis() == 253402300799999
        assert UTCDateTime.MIN.timestamp_millis() == -62135596800000

    def test_nanos(self):
        assert UTCDateTime(1970, 1, 1).timestamp_nanos() == 0
        assert (
            UTCDateTime(2020, 8, 15, 12, 8, 30, 45_123_789).timestamp_nanos()
            == 1_597_493_310_045_123_789
        )
        assert UTCDateTime.MAX.timestamp_nanos() == 253402300799_999_999_999
        assert UTCDateTime.MIN.timestamp_nanos() == -62135596800_000_000_000


class TestFromTimestamp:

    @pytest.mark.parametrize(
        "method, factor",
        [
            (UTCDateTime.from_timestamp, 1),
            (UTCDateTime.from_timestamp_millis, 1_000),
            (UTCDateTime.from_timestamp_nanos, 1_000_000_000),
        ],
    )
    def test_all(self, method, factor):
        assert method(0) == UTCDateTime(1970, 1, 1)
        assert method(1_597_493_310 * factor) == UTCDateTime(
            2020, 8, 15, 12, 8, 30
        )
        with pytest.raises((OSError, OverflowError, ValueError)):
            method(1_000_000_000_000_000_000 * factor)

        with pytest.raises((OSError, OverflowError, ValueError)):
            method(-1_000_000_000_000_000_000 * factor)

    def test_extremes(self):
        assert UTCDateTime.from_timestamp(
            UTCDateTime.MAX.timestamp()
        ) == UTCDateTime.MAX.replace(nanosecond=0)
        assert (
            UTCDateTime.from_timestamp(UTCDateTime.MIN.timestamp())
            == UTCDateTime.MIN
        )

        assert UTCDateTime.from_timestamp_millis(
            UTCDateTime.MAX.timestamp_millis()
        ) == UTCDateTime.MAX.replace(nanosecond=999_000_000)
        assert (
            UTCDateTime.from_timestamp_millis(
                UTCDateTime.MIN.timestamp_millis()
            )
            == UTCDateTime.MIN
        )

        assert (
            UTCDateTime.from_timestamp_nanos(UTCDateTime.MAX.timestamp_nanos())
            == UTCDateTime.MAX
        )
        assert (
            UTCDateTime.from_timestamp_nanos(UTCDateTime.MIN.timestamp_nanos())
            == UTCDateTime.MIN
        )


def test_repr():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert repr(d) == "UTCDateTime(2020-08-15 23:12:09.000987654Z)"
    assert (
        repr(UTCDateTime(2020, 8, 15, 23, 12))
        == "UTCDateTime(2020-08-15 23:12:00Z)"
    )


class TestComparison:
    def test_utc(self):
        d = UTCDateTime(2020, 8, 15, 23, 12, 9)
        same = UTCDateTime(2020, 8, 15, 23, 12, 9)
        later = UTCDateTime(2020, 8, 16)

        assert not d > same
        assert d >= same
        assert not d < same
        assert d <= same

        assert d < later
        assert d <= later
        assert not d > later
        assert not d >= later

        assert later > d
        assert later >= d
        assert not later < d
        assert not later <= d

        assert d < AlwaysLarger()
        assert d <= AlwaysLarger()
        assert not d > AlwaysLarger()
        assert not d >= AlwaysLarger()
        assert not d < AlwaysSmaller()
        assert not d <= AlwaysSmaller()
        assert d > AlwaysSmaller()
        assert d >= AlwaysSmaller()

    def test_offset(self):
        d = UTCDateTime(2020, 8, 15, 12, 30)

        offset_eq = d.in_fixed_offset(4)
        offset_gt = offset_eq.replace(minute=31)
        offset_lt = offset_eq.replace(minute=29)
        assert d >= offset_eq
        assert d <= offset_eq
        assert not d > offset_eq
        assert not d < offset_eq

        assert d > offset_lt
        assert d >= offset_lt
        assert not d < offset_lt
        assert not d <= offset_lt

        assert d < offset_gt
        assert d <= offset_gt
        assert not d > offset_gt
        assert not d >= offset_gt

    def test_zoned(self):
        d = UTCDateTime(2023, 10, 29, 1, 15)
        zoned_eq = ZonedDateTime(
            2023, 10, 29, 2, 15, tz="Europe/Paris", disambiguate="later"
        )

        zoned_gt = zoned_eq.replace(minute=16, disambiguate="later")
        zoned_lt = zoned_eq.replace(minute=14, disambiguate="later")
        assert d >= zoned_eq
        assert d <= zoned_eq
        assert not d > zoned_eq
        assert not d < zoned_eq

        assert d > zoned_lt
        assert d >= zoned_lt
        assert not d < zoned_lt
        assert not d <= zoned_lt

        assert d < zoned_gt
        assert d <= zoned_gt
        assert not d > zoned_gt
        assert not d >= zoned_gt

    @local_nyc_tz()
    def test_local(self):
        d = UTCDateTime(2020, 8, 15, 12, 30)

        local_eq = d.in_local_system()
        local_gt = local_eq.replace(minute=31)
        local_lt = local_eq.replace(minute=29)
        assert d >= local_eq
        assert d <= local_eq
        assert not d > local_eq
        assert not d < local_eq

        assert d > local_lt
        assert d >= local_lt
        assert not d < local_lt
        assert not d <= local_lt

        assert d < local_gt
        assert d <= local_gt
        assert not d > local_gt
        assert not d >= local_gt

    def test_notimplemented(self):
        d = UTCDateTime(2020, 8, 15)
        assert d < AlwaysLarger()
        assert d <= AlwaysLarger()
        assert not d > AlwaysLarger()
        assert not d >= AlwaysLarger()
        assert not d < AlwaysSmaller()
        assert not d <= AlwaysSmaller()
        assert d > AlwaysSmaller()
        assert d >= AlwaysSmaller()

        with pytest.raises(TypeError):
            d < 42  # type: ignore[operator]
        with pytest.raises(TypeError):
            d <= 42  # type: ignore[operator]
        with pytest.raises(TypeError):
            d > 42  # type: ignore[operator]
        with pytest.raises(TypeError):
            d >= 42  # type: ignore[operator]
        with pytest.raises(TypeError):
            42 < d  # type: ignore[operator]
        with pytest.raises(TypeError):
            42 <= d  # type: ignore[operator]
        with pytest.raises(TypeError):
            42 > d  # type: ignore[operator]
        with pytest.raises(TypeError):
            42 >= d  # type: ignore[operator]
        with pytest.raises(TypeError):
            None < d  # type: ignore[operator]
        with pytest.raises(TypeError):
            None <= d  # type: ignore[operator]
        with pytest.raises(TypeError):
            None > d  # type: ignore[operator]
        with pytest.raises(TypeError):
            None >= d  # type: ignore[operator]


def test_py_datetime():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, nanosecond=987_654)
    assert d.py_datetime() == py_datetime(
        2020, 8, 15, 23, 12, 9, 987, tzinfo=timezone.utc
    )


def test_from_py_datetime():
    d = py_datetime(2020, 8, 15, 23, 12, 9, 987_654, tzinfo=timezone.utc)
    assert UTCDateTime.from_py_datetime(d) == UTCDateTime(
        2020, 8, 15, 23, 12, 9, nanosecond=987_654_000
    )

    with pytest.raises(ValueError, match="utc.*timedelta"):
        UTCDateTime.from_py_datetime(
            d.replace(tzinfo=timezone(-timedelta(hours=4)))
        )


def test_now():
    now = UTCDateTime.now()
    py_now = py_datetime.now(timezone.utc)
    assert py_now - now.py_datetime() < timedelta(seconds=1)


def test_patchable_now():
    with mock.patch.object(
        UTCDateTime, "now", return_value=UTCDateTime(2020, 8, 15, 14)
    ):
        assert UTCDateTime.now() == UTCDateTime(2020, 8, 15, 14)


def test_min_max():
    assert UTCDateTime.MIN == UTCDateTime(1, 1, 1)
    assert UTCDateTime.MAX == UTCDateTime(
        9999, 12, 31, 23, 59, 59, 999_999_999
    )


def test_replace():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert d.replace(year=2021) == UTCDateTime(2021, 8, 15, 23, 12, 9, 987_654)
    assert d.replace(month=9) == UTCDateTime(2020, 9, 15, 23, 12, 9, 987_654)
    assert d.replace(day=16) == UTCDateTime(2020, 8, 16, 23, 12, 9, 987_654)
    assert d.replace(hour=0) == UTCDateTime(2020, 8, 15, 0, 12, 9, 987_654)
    assert d.replace(minute=0) == UTCDateTime(2020, 8, 15, 23, 0, 9, 987_654)
    assert d.replace(second=0) == UTCDateTime(2020, 8, 15, 23, 12, 0, 987_654)
    assert d.replace(nanosecond=0) == UTCDateTime(2020, 8, 15, 23, 12, 9, 0)

    with pytest.raises(TypeError, match="tzinfo"):
        d.replace(tzinfo=timezone.utc)  # type: ignore[call-arg]


def test_with_date():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert d.with_date(Date(2019, 1, 1)) == UTCDateTime(
        2019, 1, 1, 23, 12, 9, 987_654
    )
    assert d == UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)


def test_with_time():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert d.with_time(Time(1, 2, 3, 4)) == UTCDateTime(
        2020, 8, 15, 1, 2, 3, 4
    )
    assert d == UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)


def test_add_method():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert d.add(hours=24, seconds=5) == UTCDateTime(
        2020, 8, 16, 23, 12, 14, 987_654
    )
    assert d.add(years=1, days=4, minutes=-4) == UTCDateTime(
        2021, 8, 19, 23, 8, 9, 987_654
    )


class TestAddOperator:
    def test_time_units(self):
        d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
        assert d + hours(24) + seconds(5) == UTCDateTime(
            2020, 8, 16, 23, 12, 14, 987_654
        )

        with pytest.raises(ValueError, match="range"):
            d + hours(9_000 * 366 * 24)

    # TODO
    # def test_mix(self):
    #     d = UTCDateTime(2020, 8, 15, 23, 30)
    #     assert d + years(1) + days(4) - minutes(4) == UTCDateTime(
    #         2021, 8, 19, 23, 26
    #     )

    def test_date_units(self):
        d = UTCDateTime(2020, 8, 15, 23, 30)
        assert d + years(1) + days(4) == UTCDateTime(2021, 8, 19, 23, 30)

    def test_invalid(self):
        d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
        with pytest.raises(TypeError, match="unsupported operand type"):
            d + 42  # type: ignore[operator]

        with pytest.raises(TypeError, match="unsupported operand type"):
            42 + d  # type: ignore[operator]

        with pytest.raises(TypeError, match="unsupported operand type"):
            None + d  # type: ignore[operator]


def test_subtract_method():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
    assert d.subtract(hours=24, seconds=5) == UTCDateTime(
        2020, 8, 14, 23, 12, 4, 987_654
    )
    assert d.subtract(years=1, days=4, minutes=-4) == UTCDateTime(
        2019, 8, 11, 23, 16, 9, 987_654
    )


class TestSubtractOperator:
    def test_time_units(self):
        d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
        assert d - hours(24) - seconds(5) == UTCDateTime(
            2020, 8, 14, 23, 12, 4, 987_654
        )

    def test_date_units(self):
        d = UTCDateTime(2020, 8, 15, 23, 30)
        assert d - years(1) - days(4) == UTCDateTime(2019, 8, 11, 23, 30)

    # TODO
    # def test_mixed_units(self):
    #     d = UTCDateTime(2020, 8, 15, 23, 30)
    #     assert d - years(1) - days(4) - minutes(-4) == UTCDateTime(
    #         2019, 8, 11, 23, 34
    #     )

    def test_utc(self):
        d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
        other = UTCDateTime(2020, 8, 14, 23, 12, 4, 987_654)
        assert d - other == hours(24) + seconds(5)

    def test_offset(self):
        d = UTCDateTime(2020, 8, 15, 23)
        assert d - OffsetDateTime(2020, 8, 15, 20, offset=2) == hours(5)

    def test_zoned(self):
        d = UTCDateTime(2023, 10, 29, 6)
        assert d - ZonedDateTime(
            2023, 10, 29, 3, tz="Europe/Paris", disambiguate="later"
        ) == hours(4)
        assert d - ZonedDateTime(
            2023, 10, 29, 2, tz="Europe/Paris", disambiguate="later"
        ) == hours(5)
        assert d - ZonedDateTime(
            2023, 10, 29, 2, tz="Europe/Paris", disambiguate="earlier"
        ) == hours(6)
        assert d - ZonedDateTime(2023, 10, 29, 1, tz="Europe/Paris") == hours(
            7
        )

    @local_ams_tz()
    def test_local(self):
        d = UTCDateTime(2023, 10, 29, 6)
        assert d - LocalSystemDateTime(
            2023, 10, 29, 3, disambiguate="later"
        ) == hours(4)
        assert d - LocalSystemDateTime(
            2023, 10, 29, 2, disambiguate="later"
        ) == hours(5)
        assert d - LocalSystemDateTime(
            2023, 10, 29, 2, disambiguate="earlier"
        ) == hours(6)
        assert d - LocalSystemDateTime(2023, 10, 29, 1) == hours(7)

    def test_invalid(self):
        d = UTCDateTime(2020, 8, 15, 23, 12, 9, 987_654)
        with pytest.raises(TypeError, match="unsupported operand type"):
            d - 42  # type: ignore[operator]

        with pytest.raises(TypeError, match="unsupported operand type"):
            42 - d  # type: ignore[operator]

        with pytest.raises(TypeError, match="unsupported operand type"):
            None - d  # type: ignore[operator]


def test_pickle():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, nanosecond=987_654_200)
    dumped = pickle.dumps(d)
    assert len(dumped) <= len(pickle.dumps(d.py_datetime()))
    assert pickle.loads(pickle.dumps(d)) == d


def test_old_pickle_data_remains_unpicklable():
    # Don't update this value after 1.x release -- the whole idea is that it's
    # a pickle at a specific version of the library.
    dumped = (
        b"\x80\x04\x95.\x00\x00\x00\x00\x00\x00\x00\x8c\x08whenever\x94\x8c\n_unpkl_u"
        b"tc\x94\x93\x94C\x0cI\xb4\xcb\xd6\x0e\x00\x00\x008h\xde:\x94\x85\x94R\x94."
    )
    assert pickle.loads(dumped) == UTCDateTime(
        2020, 8, 15, 23, 12, 9, nanosecond=987_654_200
    )


def test_copy():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, nanosecond=987_654)
    assert copy(d) is d
    assert deepcopy(d) is d


def test_in_utc():
    d = UTCDateTime(2020, 8, 15, 20)
    assert d.in_utc() is d


def test_in_fixed_offset():
    d = UTCDateTime(2020, 8, 15, 20)
    assert d.in_fixed_offset().exact_eq(
        OffsetDateTime(2020, 8, 15, 20, offset=0)
    )
    assert d.in_fixed_offset(hours(3)).exact_eq(
        OffsetDateTime(2020, 8, 15, 23, offset=3)
    )
    assert d.in_fixed_offset(-3).exact_eq(
        OffsetDateTime(2020, 8, 15, 17, offset=-3)
    )


def test_in_tz():
    d = UTCDateTime(2020, 8, 15, 20)
    assert d.in_tz("America/New_York").exact_eq(
        ZonedDateTime(2020, 8, 15, 16, tz="America/New_York")
    )


@local_nyc_tz()
def test_in_local_system():
    d = UTCDateTime(2020, 8, 15, 20)
    assert d.in_local_system().exact_eq(LocalSystemDateTime(2020, 8, 15, 16))
    # ensure disembiguation is correct
    d = UTCDateTime(2022, 11, 6, 5)
    assert d.in_local_system().exact_eq(
        LocalSystemDateTime(2022, 11, 6, 1, disambiguate="earlier")
    )
    assert d.replace(hour=6).in_local_system() == LocalSystemDateTime(
        2022, 11, 6, 1, disambiguate="later"
    )


def test_naive():
    d = UTCDateTime(2020, 8, 15, 20)
    assert d.naive() == NaiveDateTime(2020, 8, 15, 20)


class TestStrptime:

    @pytest.mark.parametrize(
        "string, fmt, expected",
        [
            (
                "2020-08-15 23:12+0000",
                "%Y-%m-%d %H:%M%z",
                UTCDateTime(2020, 8, 15, 23, 12),
            ),
            (
                "2020-08-15 23:12:09+0000",
                "%Y-%m-%d %H:%M:%S%z",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            (
                "2020-08-15 23:12:09Z",
                "%Y-%m-%d %H:%M:%S%z",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            ("2020-08-15 23", "%Y-%m-%d %H", UTCDateTime(2020, 8, 15, 23)),
        ],
    )
    def test_strptime(self, string, fmt, expected):
        assert UTCDateTime.strptime(string, fmt) == expected

    def test_strptime_invalid(self):
        with pytest.raises(ValueError):
            UTCDateTime.strptime(
                "2020-08-15 23:12:09+0200", "%Y-%m-%d %H:%M:%S%z"
            )


def test_rfc2822():
    assert (
        UTCDateTime(2020, 8, 15, 23, 12, 9, nanosecond=450).rfc2822()
        == "Sat, 15 Aug 2020 23:12:09 GMT"
    )


class TestFromRFC2822:

    @pytest.mark.parametrize(
        "s, expected",
        [
            (
                "Sat, 15 Aug 2020 23:12:09 GMT",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            (
                "Sat, 15 Aug 2020 23:12:09 +0000",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            # TODO: fix
            # (
            #     "Sat, 15 Aug 2020 23:12:09 -0000",
            #     UTCDateTime(2020, 8, 15, 23, 12, 9),
            # ),
            (
                "Sat, 15 Aug 2020 23:12:09 UTC",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            (
                "15      Aug 2020\n23:12 UTC",
                UTCDateTime(2020, 8, 15, 23, 12),
            ),
        ],
    )
    def test_valid(self, s, expected):
        assert UTCDateTime.from_rfc2822(s) == expected

    def test_invalid(self):
        # no offset
        with pytest.raises(
            ValueError,
            match=r"Could not parse.*RFC 2822.*'Sat, 15 Aug 2020 23:12:09'",
        ):
            UTCDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:09")

        # nonzero offset
        with pytest.raises(
            ValueError,
            match=r"Could not parse.*RFC 2822.*offset.*'Sat, 15 Aug 2020 23:12:09 \+0200'",
        ):
            UTCDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:09 +0200")

        # garbage
        with pytest.raises(
            ValueError,
            match=r"Invalid.*Blurb.*",
        ):
            UTCDateTime.from_rfc2822("Blurb, 2 Bla 2020 23:12:09,0")


def test_rfc3339():
    assert (
        UTCDateTime(2020, 8, 15, 23, 12, 9, 450).rfc3339()
        == "2020-08-15 23:12:09.00000045Z"
    )


class TestFromRFC3339:

    @pytest.mark.parametrize(
        "s, expect",
        [
            (
                "2020-08-15T23:12:09.000450Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, nanosecond=450_000),
            ),
            (
                "2020-08-15T23:12:09.000002001Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 2_001),
            ),
            (
                "2020-08-15t23:12:09z",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            (
                "2020-08-15_23:12:09-00:00",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            (
                "2020-08-15_23:12:09+00:00",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            # subsecond precision that isn't supported by older fromisoformat()
            (
                "2020-08-15T23:12:09.34Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 340_000_000),
            ),
        ],
    )
    def test_from_rfc3339(self, s, expect):
        assert UTCDateTime.from_rfc3339(s) == expect

    @pytest.mark.parametrize(
        "s",
        [
            "2020-8-15T23:12:45Z",  # invalid padding
            "2020-08-15T23:12Z",  # no seconds
            "2020-08-15_23Z",  # no time
            "2020-08Z",  # no time or date
            "",  # empty
            "garbage",  # garbage
            "2020-08-15T23:12:09.1234567890Z",  # too precise
            "2020-09-15T22:44:20+01:00",  # non-UTC offset
        ],
    )
    def test_invalid(self, s):
        # no timezone
        with pytest.raises(
            ValueError,
            match=r"Invalid.*RFC3339.*" + re.escape(s),
        ):
            UTCDateTime.from_rfc3339(s)


def test_common_iso8601():
    d = UTCDateTime(2020, 8, 15, 23, 12, 9, 450)
    assert d.common_iso8601() == "2020-08-15T23:12:09.00000045Z"


class TestFromCommonIso8601:

    @pytest.mark.parametrize(
        "s, expect",
        [
            (
                "2020-08-15T23:12:09.000450Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 450_000),
            ),
            (
                "2020-08-15T23:12:09+00:00",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            (
                "2020-08-15T23:12:09Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9),
            ),
            # subsecond precision that isn't supported by older fromisoformat()
            (
                "2020-08-15T23:12:09.34Z",
                UTCDateTime(2020, 8, 15, 23, 12, 9, 340_000_000),
            ),
        ],
    )
    def test_from_common_iso8601(self, s, expect):
        assert UTCDateTime.from_common_iso8601(s) == expect

    @pytest.mark.parametrize(
        "s",
        [
            "2020-08-15T23:12:09.000450",  # no offset
            "2020-08-15T23:12:09+02:00",  # non-UTC offset
            "2020-08-15 23:12:09Z",  # non-T separator
            "2020-08-15t23:12:09Z",  # non-T separator
            "2020-08-15T23:12:09z",  # lowercase Z
            "2020-08-15T23:12:09-00:00",  # forbidden offset
            "2020-08-15T23:12:09-02:00:03",  # seconds in offset
        ],
    )
    def test_invalid(self, s):
        with pytest.raises(
            ValueError,
            match=r"Invalid common.*ISO8601.*" + re.escape(repr(s)),
        ):
            UTCDateTime.from_common_iso8601(s)
