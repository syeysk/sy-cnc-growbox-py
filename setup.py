import os

with open('requirements.txt') as file_requirements:
    install_requires = file_requirements.read().split('\n')

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_long_description():
    path = os.path.join(os.path.dirname(__file__), 'README.md')

    try:
        import pypandoc
        return pypandoc.convert(path, 'rst')
    except(IOError, ImportError, RuntimeError):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

setup(
    name='growbox',
    version='0.0.1',
    license='LGPL-3.0',
    description='Python interfaces for CNC Growbox',
    packages=[
        'growbox',
    ],
    long_description=get_long_description(),
    author='Konstantin Polyakov',
    author_email='shyzik93@mail.ru',
    maintainer='Konstantin Polyakov',
    maintainer_email='shyzik93@mail.ru',
    url='https://github.com/syeysk/sy-cnc-growbox-py',
    download_url='https://github.com/syeysk/sy-cnc-growbox-py/archive/master.zip',

    install_requires=install_requires,

    entry_points={
        'gui_scripts': [
            'growbox = growbox.gui:run',
        ]
    },

    include_package_data=True,
    classifiers=[  # source: https://pypi.org/classifiers/
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Scientific/Engineering',
    ]
)
