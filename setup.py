from setuptools import setup

setup(
    name='ftrack_widgets',
    version='0.0.2',
    packages=['ftrack_widgets'],
    install_requires=[
        'Qt.py',
        'six',
        'ftrack-python-api>=2.0.0rc2',
        'requests',
    ],
    author='John Su',
    author_email='',
    description='PyQt widgets for ftrack.'
)
