#!/usr/bin/env python
from setuptools import setup

setup(
    name='pyrameter',
    version='0.1a1',
    description='Structure, sample, and savor hyperparameter searches',
    url='https://github.com/jeffkinnison/pyrameter',
    author='Jeff Kinnison',
    author_email='jkinniso@nd.edu',
    packages=['pyrameter',
              'pyrameter.models',
              'pyrameter.db'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Users',
        'License :: MIT',
        'Topic :: Machine Learning :: Hyperparameter Optimization',
        'Topic :: Distributed Systems :: Task Allocation',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Operating System :: MacOS',
    ],
    keywords='machine_learning hyperparameters',
    install_requires=[
        'scipy>=0.18.1',
        'numpy>=1.12.0',
        'scikit-learn>=0.18.1',
        'sqlalchemy>=1.1.11',
        'pymongo',
        'six',
    ],
)
