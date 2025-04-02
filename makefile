.PHONY: install lint fmt test

install:
	poetry install

lint:
	poetry run ruff check --fix

format:
	poetry run black . && poetry run isort .

test:
	poetry run pytest
