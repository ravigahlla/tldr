from setuptools import setup

setup(
    name='stratecheryGPT',
    version='0.1',
    packages=[''],
    install_requires=[
        'urllib3<2.0'  # a macOS issue, see https://github.com/urllib3/urllib3/issues/3020
    ],
    url='',
    license='MIT',
    author='Ravinder Singh',
    author_email='ravigahlla@gmail.com',
    description='a summarizer for Stratechery emails, using GPT'
)
