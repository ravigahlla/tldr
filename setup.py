from setuptools import setup, find_packages

setup(
    name='stratecheryGPT',
    version='0.1',
    packages=[''],
    install_requires=[
        'requests>=2.24.0',
        'tiktoken>=0.1.0',  # Adjust the version as necessary
        'openai>=0.10.2'  # Adjust the version as necessary
    ],
    url='',
    license='MIT',
    author='Ravinder Singh',
    author_email='ravigahlla@gmail.com',
    description='a summarizer for Stratechery emails, using GPT',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
