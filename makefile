.PHONY: install lint fmt check test

install:
	poetry install

lint:
	poetry run flake8 .

format:
	poetry run black . && poetry run isort .

test:
	poetry run pytest
