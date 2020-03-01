from setuptools import setup

setup(
    name='ftrack_widgets',
    version='0.0.2',
    packages=['ftrack_widgets'],
    install_requires=[
        'PyQt5>=5.14.1',
        'Qt.py',
        'ftrack-python-api>=2.0.0rc2',
    ],
    author='John Su',
    author_email='',
    description='PyQt widgets for ftrack.'
)
