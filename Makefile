# Everything is started from here, by hand. Nothing runs on a timer: the news refreshes when a
# visit finds it stale.
#
#   make            list the targets
#   make api + make dev    API on :8000 and the site with reload on :4321
#   make deploy     build and deploy the portal to Cloud Run

SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help install env test check site api dev serve deploy film covers

help: ## List the targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

install: env ## Install the Python and site dependencies
	uv sync
	cd site && npm ci

env: ## Create .env if missing, with the client id and a new SESSION_SECRET (keeps existing values)
	@./scripts/init-env.sh

test: ## Run the tests
	uv run pytest

check: test ## Tests plus the site's type check and build
	cd site && npx astro check && npm run build

site: ## Build the site into site/dist
	cd site && npm run build

api: env ## Run the API alone at http://localhost:8000, with reload (pair it with `make dev`)
	MARKETHUB_ALLOWED_ORIGINS=http://localhost:4321 uv run uvicorn markethub.api:create_app --factory --reload --port 8000

dev: ## Run the site at http://localhost:4321 with reload (it calls the API on port 8000)
	cd site && PUBLIC_API_URL=http://localhost:8000 npm run dev

serve: env site ## Run site and API together at http://localhost:8080, as in production
	MARKETHUB_STATIC_DIR=site/dist uv run uvicorn markethub.api:create_app --factory --port 8080

film: ## Draw, score and encode the landing page's film into site/public (uses this machine's Chrome); CUT=adventure for that cut, as a trial in film/out
	cd film && npm ci && node render.mjs $(if $(CUT),--cut=$(CUT)) && node check.mjs $(if $(CUT),--cut=$(CUT))

covers: ## Draw the library of news covers into site/public (uses this machine's Chrome); ONLY=Energy for one scope
	cd covers && npm ci && node render.mjs --sheet $(if $(ONLY),--only "$(ONLY)") && node overview.mjs

deploy: env ## Build and deploy the portal to Cloud Run (see scripts/deploy-cloudrun.sh)
	./scripts/deploy-cloudrun.sh
