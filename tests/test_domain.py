import pytest

from pyrameter.domain import Domain, ContinuousDomain, DiscreteDomain, \
                             ExhaustiveDomain

import warnings

import numpy as np
from scipy.stats import norm, uniform


warnings.filterwarnings('ignore', category=UserWarning)


class TestDomain(object):
    """Base class for Domain object unit tests."""
    __domain_class__ = Domain
    __default_domain__ = 0

    def test_init(self):
        d = self.__domain_class__(self.__default_domain__)
        assert d.domain == self.__default_domain__
        assert d.path is ''

        d = self.__domain_class__(self.__default_domain__, path='/a/b')

    def test_generate(self):
        d = self.__domain_class__(self.__default_domain__)
        with pytest.raises(NotImplementedError):
            d.generate()

    def test_map_to_domain(self):
        d = self.__domain_class__(self.__default_domain__)
        test_cases = [None, True, False, 0, 1.0, '1', [1], {'1': 1}, (1,)]
        for case in test_cases:
            assert d.map_to_domain(case) is case

    def test_to_json(self):
        d = self.__domain_class__(self.__default_domain__)
        assert d.to_json() == {'type': d.__class__.__name__, 'path': ''}

        d = self.__domain_class__(self.__default_domain__, path='a')
        assert d.to_json() == {'type': d.__class__.__name__, 'path': 'a'}


class TestContinuousDomain(TestDomain):
    """ContinuousDomain object unit tests."""
    __domain_class__ = ContinuousDomain
    __default_domain__ = uniform

    def test_init(self):
        d = self.__domain_class__(self.__default_domain__)
        assert 'uniform' in d.domain.name
        assert d.domain_args == tuple()
        assert d.domain_kwargs == {}

        d = self.__domain_class__(norm)
        assert 'norm' in d.domain.name
        assert d.domain_args == tuple()
        assert d.domain_kwargs == {}

    def test_generate(self):
        d = self.__domain_class__(self.__default_domain__,
                                  random_state=np.random.RandomState(42))
        # d.random_state = np.random.RandomState(42)
        x = self.__default_domain__()
        x.dist.random_state = np.random.RandomState(42)

        src = np.array([d.generate() for _ in range(1000)])
        ref = x.rvs(size=1000)
        assert np.all(src == ref)

        src = np.array([d.generate(index=True) for _ in range(1000)])
        ref = x.rvs(size=1000)
        assert np.all(src == ref)

    def test_to_json(self):
        d = self.__domain_class__(self.__default_domain__)
        res = {
            'type': d.__class__.__name__,
            'path': '',
            'distribution': 'uniform',
            'args': tuple(),
            'kws': {}
        }
        assert d.to_json() == res


class TestDiscreteDomain(TestDomain):
    """DiscreteDomain object unit tests."""
    __domain_class__ = DiscreteDomain
    __default_domain__ = [1, 2, 3, 4, 5]

    def test_generate(self):
        d = self.__domain_class__(self.__default_domain__)
        for i in range(1000):
            assert d.generate() in self.__default_domain__

            val, idx = d.generate(index=True)
            assert val in self.__default_domain__
            assert idx in range(len(self.__default_domain__))

    def test_map_to_domain(self):
        pass

    def test_to_json(self):
        d = self.__domain_class__(self.__default_domain__)
        res = {
            'type': d.__class__.__name__,
            'path': '',
            'domain': self.__default_domain__
        }
        assert d.to_json() == res


class TestExhaustiveDomain(TestDomain):
    """DiscreteDomain object unit tests."""
    __domain_class__ = ExhaustiveDomain
    __default_domain__ = [1, 2, 3, 4, 5]

    def test_generate(self):
        pass

    def test_map_to_domain(self):
        d = self.__domain_class__(self.__default_domain__)
        d2 = self.__domain_class__(self.__default_domain__)
        for i in range(1000):
            assert d.generate() in self.__default_domain__

            val, idx = d2.generate(index=True)
            assert val in self.__default_domain__
            assert idx == (i % len(self.__default_domain__))

    def test_to_json(self):
        d = self.__domain_class__(self.__default_domain__)
        res = {
            'type': d.__class__.__name__,
            'path': '',
            'domain': self.__default_domain__,
            'idx': 0
        }
        assert d.to_json() == res
