.PHONY: lint fmt test

lint:
	poetry run ruff check --fix

format:
	poetry run black . && poetry run isort .

test:
	poetry run pytest
