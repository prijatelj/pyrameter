import json
import os


from pyrameter.db.base import BaseStorage
from pyrameter.models.model import Model


class JsonStorage(BaseStorage):
    """Local JSON-based model storage.

    Parameters
    ----------
    path : str
        Path to save the models to. If a directory, will be saved to
        <``path``>/results.json
    keep_previous : int, optional
        The maximum number of checkpoints to keep. Default 1.

    Attributes
    ----------
    path : str
        Path to save the models to.
    backups : int
        The maximum number of checkpoints to keep.

    See Also
    --------
    `pyrameter.db.base.BaseStorage`
    `pyrameter.models.model.Model.to_json`
    `pyrameter.models.model.Result.to_json`
    `pyrameter.models.model.Value.to_json`
    `pyrameter.domains.Domain.to_json`
    """

    def __init__(self, path=None, keep_previous=1):
        if path is None:
            path = os.getcwd()

        self.path = os.path.abspath(path)

        if os.path.isdir(self.path):
            self.path = os.path.join(self.path, 'results.json')
            f = open(self.path, 'a')
            f.close()

        if not os.path.exists(os.path.dirname(self.path)):
            raise OSError('Invalid save path: {}'.format(self.path))

        self.backups = keep_previous
        self.n_checkpoints = 0

    def load(self):
        """Load model state from file.

        Returns
        -------
        models : list of `pyrameter.models.model.Model`
            Models loaded from the JSON store.

        Raises
        ------
        OSError
            Raised when the files cannot be read.
        """
        models = None
        path, fname = os.path.split(self.path)
        name, ext = os.path.splitext(fname)

        current_path = self.path
        current_backup = 1

        while models is None and os.path.isfile(current_path):
            try:
                with open(current_path, 'r') as f:
                    models = json.load(f)
            except (OSError, json.JSONDecodeError):
                models = None
                current_path = os.path.join(
                    path, ''.join([path, '_{}'.format(current_backup), ext]))

        if models is None:
            raise OSError('Could not load files from {}.'.format(self.path))

        model_objs = []
        for m in models:
            model = Model.from_json(m)
            model_objs.append(model)

        return model_objs

    def save(self, models):
        """Save the state of a set of models.

        Parameters
        ----------
        models : list of `pyrameter.models.model.Model`
            The models to save.

        Raises
        ------
        TypeError
            Raised if a non-subclass of `pyramerter.models.model.Model` is
            encountered.
        """
        if not isinstance(models, list):
            models = [models]
        json_compatible = []
        for model in models:
            if isinstance(model, Model):
                m = model.to_json()
            else:
                raise TypeError('{} is not a valid pyrameter model.'.format(
                    model))
            json_compatible.append(m)

        with open(self.path, 'w') as f:
            json.dump(json_compatible, f)
