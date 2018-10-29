from pyrameter.domain import Domain
from pyrameter.models.model_factory import get_model_class

import copy
import uuid
import warnings
import weakref

import numpy as np
from six import string_types
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF


class InvalidModelError(Exception):
    """Raised when a supplied domain is not an instance of pyrameter.models.Model."""
    def __init__(self, model):
        msg = '{} is not a valid pyrameter.models.Model.'.format(model)
        msg += '\nDid you set up your models with pyrameter.build()?'
        super(InvalidModelError, self).__init__(msg)


class InvalidDomainError(Exception):
    """Raised when a supplied domain is not an instance of pyrameter.Domain."""
    def __init__(self, domain):
        msg = '{} is not a valid pyrameter.Domain.'.format(domain)
        msg += '\nDid you set up your models with pyrameter.build()?'
        super(InvalidDomainError, self).__init__(msg)


class InvalidResultError(Exception):
    """Raised when a supplied result is not an instance of pyrameter.models.Result."""
    def __init__(self, result):
        msg = '{} is not a valid pyrameter.models.Result.'.format(result)
        msg += '\nDid you set up your models with pyrameter.build()?'
        super(InvalidResultError, self).__init__(msg)


class InvalidValueError(Exception):
    """Raised when a supplied value is not an instance of pyrameter.models.Value."""
    def __init__(self, valie):
        msg = '{} is not a valid pyrameter.models.Value.'.format(value)
        msg += '\nDid you set up your models with pyrameter.build()?'
        super(InvalidResultError, self).__init__(msg)


class Model(object):
    """Hierarchical hyperparameter search tree matching a learning model.

    This class manages hyperparameter domains and search information for a
    single machine learning model (e.g., SVM with RBF kernel, 5-layer vs
    10-layer neural network, etc.).

    Parameters
    ----------
    id : str, optional
        The id of this model. If not supplied, an id will be generated.
    domains : list of ``pyrameter.Domain``, optional
        The domains contained within this model.
    results : list of ``pyrameter.models.Result``, optional
        The results observed from evaluting different hyperparameterizations of
        this model.
    update_complexity : bool, optional
        Whether to update model complexity when adding a new domain. Enabled by
        default.
    priority_update_freq : int, optional
        How often the priority heuristic is updated, based on the number of
        results. Values less than or equal to 0 disable priority updates.
        Default: update every 10 results.

    Notes
    -----
    The complexity and priority heuristics are computed as described by
    Kinnison *et al.* [1]_ .

    References
    ----------
    .. [1] Kinnison, J., Kremer-Herman, N., Thain, D., & Scheirer, W. (2017).
       SHADHO: Massively Scalable Hardware-Aware Distributed Hyperparameter
       Optimization. arXiv preprint arXiv:1707.01428.
    """

    TYPE = 'random'

    def __init__(self, id=None, domains=None, results=None,
                 update_complexity=True, priority_update_freq=10):
        self.id = str(uuid.uuid4()) if id is None else id
        self.domains = [] if domains is None else domains
        self.results = [] if results is None else results

        self._priority = 1.0
        self._complexity = 1.0
        self.jhibshma_rank = 1
        self.rank = None

        # Used to update models this was copied from.
        self.parent = None

        self.update_complexity = update_complexity
        self.domain_added = bool(self.domains)
        self.priority_update_freq = priority_update_freq
        self.recompute_priority = False

    def __eq__(self, other):
        eq_domains = all(
            map(lambda s: any(
                    map(lambda o: s == o,
                        other.domains)),
                self.domains))
        return isinstance(other, Model) and len(self) == len(other) and \
               eq_domains

    def __len__(self):
        return len(self.domains)

    def __str__(self):
        d = '\n\t'.join([str(domain) for domain in self.domains])
        return '\n'.join(['{', d, '}'])

    def __repr__(self):
        return str(self)

    def __call__(self):
        params = self.generate()
        r = Result(model=self)
        self.add_result(r)

        outparams = {}
        for i in range(len(params)):
            r.add_value(Value(params[i], self.domains[i]))
            path = self.domains[i].path.split('/')
            curr = outparams
            for p in path[:-1]:
                if p != '':
                    if p not in curr:
                        curr[p] = {}
                    curr = curr[p]
            curr[path[-1]] = params[i]
        return r.id, outparams

    def add_domain(self, domain):
        """Add a domain to this model.

        Parameters
        ----------
        domain : pyrameter.Domain
            The new domain to include in this model.

        Notes
        -----
        If complexity updates are enabled, adding a domain with this method
        will trigger a recalculation of the complexity.
        """
        self.domains.append(domain)
        self.domain_added = True
        self.domains.sort(key=lambda x: x.path)

    def add_result(self, result):
        """Add a result to this model.

        Parameters
        ----------
        domain : pyrameter.Domain
            The new domain to include in this model.

        Notes
        -----
        If complexity updates are enabled, adding a domain with this method
        will trigger a recalculation of the complexity.
        """
        self.results.append(result)
        should_update = (len(self.results) % self.priority_update_freq == 0)
        if not self.recompute_priority and should_update:
            self.recompute_priority = True
        if self.parent is not None:
            self.parent.add_result(result)

    def register_result(self, result_id, loss, results=None):
        """Update an existing Result by id.

        Parameters
        ----------
        result_id : str
            The result to update.
        loss : float
            The loss value of this result.
        results : dict, optional
            Key/value pairs of additional information to store with the result.

        Notes
        -----
        If the given result does not exist, a new result will be created with
        the supplied loss and results dictionary.
        """
        found = None
        for r in self.results:
            if r.id == result_id:
                r.loss = loss
                r.results = results
                r.submissions += 1
                found = r

        if found is None:
            msg = 'No result with id {} found in this model.'.format(result_id)
            msg += ' Did you generate the hyperparameter values with '
            msg += '`Model.generate()`?'
            raise KeyError(msg)

        params = {}
        if loss is None:
            for value in found.values:
                domain = value.domain()
                curr = params
                path = domain.path.split('/')
                for p in path[:-1]:
                    if p not in params:
                        curr[p] = {}
                    curr = curr[p]
                curr[path[-1]] = value.value

        if self.parent is not None:
            self.parent.register_result(result_id, loss, results)

        return found.submissions, params

    def copy(self, parent_inherits_results=False):
        """Make a copy of this model.

        Returns
        -------
        A new ``pyrameter.models.Model`` instance with copies of all model
        attributes.
        """
        m = self.__class__(id=self.id,
                           domains=[d for d in self.domains],
                           results=[r for r in self.results],
                           update_complexity=self.update_complexity,
                           priority_update_freq=self.priority_update_freq)
        if parent_inherits_results:
            m.parent = self
        return m

    def merge(self, other):
        """Merge the domains of two models."""
        # TODO: Implement results merging in a sane way (placeholder vals?)
        self.domains.extend(other.domains)
        # self.results.extend(other.results)

    def results_to_feature_vector(self):
        """Convert hyperparameter values to a feature vector.

        For use with methods that model the function mapping hyperparameter
        values to their performance.

        Returns
        -------
        An array with shape (r, v + 1), where r is the number of results in
        this model and v is the number of hyperparameter values. The last
        entry in each row is the performance (e.g. loss).
        """
        vec = np.zeros((len(self.results), len(self.results[0].values) + 1),
                       dtype=np.float32)
        for i in range(len(self.results)):
            loss = self.results[i].loss
            if loss is not None and loss not in [np.inf, -np.inf, np.nan]:
                vec[i, -1] += self.results[i].loss
                for j in range(len(self.results[i].values)):
                    vec[i, j] += self.results[i].values[j].to_numeric()
        return vec

    def generate(self):
        """Generate hyperparameter values for this model.

        This method must be overridden in subclasses to implement
        hyperparameter generation methods.

        Raises
        ------
        NotImplementedError
        """
        raise NotImplementedError

    @property
    def complexity(self):
        # Only compute complexity if requested and an update is necessary
        if self.update_complexity and self.domain_added:
            self._complexity = 1.0
            for domain in self.domains:
                self._complexity *= domain.complexity
        return self._complexity

    @property
    def priority(self):
        # Only compute priority if requested and an update is necessary
        if self.priority_update_freq >= 0 and self.recompute_priority:
            vec = self.results_to_feature_vector()

            split = int(np.ceil(vec.shape[0] *
                        (0.8 if vec.shape[0] < 10 else 1.0)))
            scales = np.zeros((50,), dtype=np.float32)

            for i in range(scales.shape[0]):
                np.random.shuffle(vec)
                features = np.copy(vec[:split, :-1])
                losses = np.reshape(np.copy(vec[:split, -1]), (-1, 1))
                est = np.random.uniform(0.1, 2.0)
                gp = GaussianProcessRegressor(kernel=RBF(length_scale=est),
                                              alpha=1e-5)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    gp.fit(features, losses)
                scales[i] += (1.0 / gp.kernel.theta[0])

            self._priority = np.linalg.norm(scales.max() - scales.min())

        return self._priority

    def to_json(self):
        """Convert the model into a JSON-serializable format.

        Returns
        -------
        A dictionary containing all relevant model attributes in a valid
        JSON-serializable format.
        """
        return {
            'type': self.TYPE,
            'id': self.id,
            'domains': [d.to_json() for d in self.domains],
            'results': [r.to_json() for r in self.results],
            'priority': float(self.priority),
            'complexity': self.complexity,
            'rank': self.rank,
            'model_parameters': {
                'update_complexity': self.update_complexity,
                'priority_update_freq': self.priority_update_freq
            }
        }

    @staticmethod
    def from_json(spec):
        """Create a model from a JSON-serialized format.

        Parameters
        ----------
        spec : dict
            The dictionary of metadata needed to create a model.

        Returns
        -------
        model : pyrameter.models.Model
            The model created from ``spec``.

        See Also
        --------
        pyrameter.models.Model.to_json

        Notes
        -----
        This method should be able to create a model from any dictionary output
        by the ``to_json`` class or any of its subclasses.
        """
        # Recreate the domains and results, get the model class
        domains = [Domain.from_json(d) for d in spec['domains']]
        results = [Result.from_json(r, domains) for r in spec['results']]
        model_class = get_model_class(spec['type'])
        model = model_class(domains=domains,
                            results=results,
                            **spec['model_parameters'])
        for r in model.results:
            r.model = model
        return model


class Result(object):
    """A hyperparameter evaluation result for a given model.

    Parameters
    ----------
    model : ``pyrameter.models.Model``
        The model associated with this result.
    loss : float, optional
        The performance of the hyperparameterized model.
    results : dict, optional
        Additional performance inforamtion and results (e.g., accuracy, recall,
        running time, etc.).
    values : list of ``pyrameter.models.Value``, optional
        The values that generated this result.

    Attributes
    ----------
    id : str or int

    """
    def __init__(self, model=None, loss=None, results=None, values=None):
        self.id = str(uuid.uuid4())
        self.model = model
        self.loss = loss
        self.results = results
        self.values = []
        self.submissions = 0
        values = [] if values is None else values
        values = [values] if not isinstance(values, list) else values
        for value in values:
            self.add_value(value)

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, val):
        if isinstance(val, Model):
            self._model = weakref.ref(val)
        elif isinstance(val, string_types) or val is None:
            self._model = val
        else:
            raise InvalidModelError(val)

    def add_value(self, value):
        """Add a value to this result.

        Parameters
        ----------
        value : `pyrameter.models.model.Value`
            A value associated with this result.

        Raises
        ------
        InvalidValueError
            If ``value`` is not an instance of `pyrameter.models.model.Value`.
        """
        if isinstance(value, Value):
            self.values.append(value)
        else:
            raise InvalidValueError(value)

    def to_json(self):
        """Convert this result into a JSON-serializable format.

        Returns
        -------
        A dictionary containing all relevant result attributes in a valid
        JSON-serializable format.
        """
        return {
            'id': self.id,
            'loss': self.loss,
            'results': self.results,
            'values': [v.to_json() for v in self.values],
            'model': self.model().id if isinstance(self.model, weakref.ref) \
                     else self.model
        }

    @staticmethod
    def from_json(spec, domains):
        values = [Value(spec['values'][i]['value'], domains[i], spec['id'])
                  for i in range(len(spec['values']))]
        result = Result(model=spec['model'],
                        loss=spec['loss'],
                        results=spec['results'],
                        values=values)
        return result


class Value(object):
    """Container for generated hyperparameter values.

    This class exists as a convenient means of mapping hyperparameter values
    to both the generating domain and the returned performance.

    Parameters
    ----------
    value
        The hyperparameter value.
    domain : ``pyrameter.domains.Domain``
        The domain that generated this value.
    result : ``pyrameter.models.Result``
        The result generated by this value.
    """
    def __init__(self, value, domain, result=None):
        self.value = value
        if isinstance(domain, Domain):
            self.domain = weakref.ref(domain)
        elif isinstance(domain, string_types):
            self.domain = domain
        else:
            raise InvalidDomainError(domain)

        if isinstance(result, Result):
            self.result = weakref.ref(result)
        elif isinstance(result, string_types) or result is None:
            self.result = result
        else:
            raise InvalidResultError(result)

    def to_numeric(self):
        return self.domain().map_to_index(self.value)

    def to_json(self):
        """Convert this result into a JSON-serializable format.

        Returns
        -------
        A dictionary containing all relevant result attributes in a valid
        JSON-serializable format.
        """
        return {
            'value': self.value,
            'domain': self.domain().id if isinstance(self.domain, weakref.ref) \
                      else self.domain,
            'result': self.result().id if isinstance(self.result, weakref.ref) \
                      else self.result
        }
