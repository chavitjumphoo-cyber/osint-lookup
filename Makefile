.PHONY: install lint test test-network doctor run

install:
	python -m pip install -r requirements.txt

lint:
	python -m ruff check osint_agent tests

test:
	python -m pytest -q -m "not network"

test-network:
	python -m pytest -q -m network

doctor:
	python -m osint_agent.cli doctor

run:
	python -m osint_agent.cli scan --help
