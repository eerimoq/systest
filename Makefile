test:
	python2 setup.py test
	python3 setup.py test
	env PYTHONPATH=. python3 examples/basics.py

release-to-pypi:
	python setup.py sdist
	python setup.py bdist_wheel --universal
	twine upload dist/*
