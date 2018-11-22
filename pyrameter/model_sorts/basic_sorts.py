"""
Basic ranking/sorting methods
"""

import numpy as np

def random_order(model_group):
    """
    Random sort that will randomly sort the models. This serves as a baseline
    for modifying the existing ranking with or without complexity and priority.

    This is for use to compare models to random chance. It is possible that our
    local sorting methods are worse than SHADHOs and then it would be good to
    know how they relate to random chance.
    """
    return np.random.uniform(size=len(model_groups.model_ids))
