from setuptools import setup, find_packages

setup(
    name='tldr',
    version='0.1',
    packages=[''],
    install_requires=[
        'urllib3<2.0',  # a macOS issue, see https://github.com/urllib3/urllib3/issues/3020
        'requests>=2.24.0',
        'tiktoken>=0.1.0',  # Please check the actual version needed
        'openai>=0.10.2'    # Please check the actual version needed
    ],
    url='',
    license='MIT',
    author='Ravinder Singh',
    author_email='ravigahlla@gmail.com',
    description='a summarizer for Stratechery emails, using GPT',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
