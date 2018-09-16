from setuptools import setup


setup(
    name='minigraph',
    version='0.0.2',
    description='minigraph',
    long_description=open('readme.md').read(),
    author='Ruslan Zhenetl',
    url='https://github.com/c6401/minigraph',
    license='MIT',
    packages=['minigraph'],
    install_requires=[
        "pyyaml",
        "graphviz",
        "xmltodict",
    ],
)
