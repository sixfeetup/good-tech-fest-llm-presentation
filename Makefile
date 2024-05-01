.PHONY: help clean clean-reveal start watch

.EXPORT_ALL_VARIABLES:

LLM_USER_PATH = ./llm-config

# colors
BLUE:=$(shell echo "\033[0;36m")
GREEN:=$(shell echo "\033[0;32m")
YELLOW:=$(shell echo "\033[0;33m")
RED:=$(shell echo "\033[0;31m")
END:=$(shell echo "\033[0m")

BASE_DOMAIN = www.goodtechfest.com
BASE_URI = https://$(BASE_DOMAIN)
URI_PATHS = /ai-data-science-track /cyber-security-track /engineering-track /technical-leadership-management-track /product-development-management-track /governance-collaboration-track /ethics-responsibility-track

## Before you start
check: ## System check
	@python -c "import sys; assert sys.version_info >= (3,9), 'You need at least python 3.9'"
	@echo "$(GREEN)Looks good.$(END)"

persist:
	@mkdir persist

.venv:
	@echo "$(GREEN)Setting up environment...$(END)"
	python -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@echo "$(GREEN)... Done.$(END)"
	@echo

clean:
	-rm -rf .venv
	-rm -rf data
	-rm -rf persist

setup: check .venv persist ## Setup the development environment.  You should only have to run this once.
	@echo "$(GREEN)Setting up development environment...$(END)"
	@cp -r canned_index/* persist
	@echo
	@echo "Now you need your OpenAI API key.  Go to https://beta.openai.com/account/api-keys and create a new key."
	@.venv/bin/llm keys set openai
	@.venv/bin/llm logs off
	@echo "$(GREEN)... Done. (psst, if that went badly the keys should be in llm-config/keys.json)$(END)"

## Beginner
ask-openai: ## Ask a question using the naive approach.  ( may throw an ignorable error on macOS )
	@echo "$(GREEN)Starting the presentation...$(END)"
	@.venv/bin/llm "What's the easiest way to get started with large language models?" 2>/dev/null
	@echo "$(GREEN)... Done.$(END)"


ask-llama: ## Ask a question using the Meta-Llama-3-8B-Instruct model.
	@if [ "$$(.venv/bin/llm plugins | jq -r '.[0].name')" != "llm-gpt4all" ]; then \
	  	echo "$(GREEN)Install llm-gpt4all...$(END)"; \
	  	.venv/bin/llm install llm-gpt4all 2>/dev/null; \
    else \
        echo "$(GREEN)llm-gpt4all found ✨..."; \
    fi
	@echo "$(GREEN)... Now ask the model ...$(END)"
	.venv/bin/llm prompt -m Meta-Llama-3-8B-Instruct "What's the easiest way to get started with large language models?" 2>/dev/null || true
	@echo "$(GREEN)... Done.$(END)"

## Intermediate
as-code:  ## LLM use as code
	@.venv/bin/llm keys path
	@.venv/bin/python as_code.py

data: ## crawl the site
	@echo "$(GREEN)Setting up Good Tech Fest data...$(END)"
	@#rm -rf data
	@mkdir data || true
	@cd data && wget \
		 --mirror \
		 --wait 10 \
		 --random-wait \
		 --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" \
		 --no-check-certificate \
		 --retry-connrefused \
		 --retry-on-http-error=429 \
		 --no-parent \
		 --reject='*.js,*.css,*.ico,*.txt,*.gif,*.jpg,*.jpeg,*.png,*.mp3,*.pdf,*.tgz,*.flv,*.avi,*.mpeg,*.iso' \
		 --header="Accept: text/html" \
		"$(BASE_URI)";
	@# because squarespace uses dirs for pages, we need to pull urls directly and rename
	@for path in $(URI_PATHS); do \
  		wget \
		 --wait 10 \
		 --random-wait \
		 --user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36" \
		 --no-check-certificate \
		 --retry-connrefused \
		 --retry-on-http-error=429 \
		 --no-parent \
		 --reject='*.js,*.css,*.ico,*.txt,*.gif,*.jpg,*.jpeg,*.png,*.mp3,*.pdf,*.tgz,*.flv,*.avi,*.mpeg,*.iso' \
		 --header="Accept: text/html" \
		"$(BASE_URI)$$path" -O "data/$(BASE_DOMAIN)$${path}.html"; \
  	  done


extract: data  ## extract the data
	@echo "$(GREEN)Extracting...$(END)"
	@LLM_USER_PATH=./llm-config .venv/bin/python data_load.py
	@echo "$(GREEN)... Done.$(END)"

run:
	@# this is based on the open ai libs
	@LLM_USER_PATH=./llm-config .venv/bin/python data_query.py

## Advanced
contact:  ## Contact us to make more than toys.
	@echo "We can be reached at $(BLUE)https://sixfeetup.com$(END)."

## Documentation
help:  ## Render the readme and getting started guide.
	@mdn README.md || cat README.md

slide-theme := minions_dark

index.html: slides.md js/reveal.js dist/theme/$(slide-theme).css ## build presentation and theme
	pandoc -t revealjs -s -V revealjs-url=. \
		-V theme=$(slide-theme) \
		-V width=1200 \
		-V center=false \
		-V autoPlayMedia=false \
		-V hash=true \
		-o "$@" "$<"

js/reveal.js:
	curl -LO https://github.com/hakimel/reveal.js/archive/master.zip
	bsdtar --strip-components=1 --exclude .gitignore --exclude LICENSE --exclude README.md --exclude demo.html --exclude index.html -xf master.zip
	rm master.zip
	npm install

css/theme/source/$(slide-theme).scss: themes/$(slide-theme).scss
	cp "$<" "$@"

dist/theme/$(slide-theme).css: css/theme/source/$(slide-theme).scss
	npm run build -- css-themes

start: index.html ## bulid presentation and start server
	@echo "Starting the local presentation server 🚀"
	@npm start

clean-reveal: ## clean up the working directory
	rm CONTRIBUTING.md || true
	rm LICENSE || true
	rm .npmignore || true
	rm -rf css/ || true
	rm gulpfile.js || true
	rm index.html || true
	rm -rf examples/ || true
	rm -rf js/ || true
	rm -rf lib/ || true
	rm package-lock.json || true
	rm package.json || true
	rm -rf plugin/ || true
	rm -rf test/ || true
	rm -rf node_modules/ || true
	rm -rf dist/ || true

watch: ## Watch for changes and rebuild
	@echo "♻️ Watching for changes..."
	@watchmedo tricks-from tricks.yaml

usage: ## This help.
	@awk 'BEGIN     { FS = ":.*##"; target="";printf "\nUsage:\n  make $(BLUE)<target>\033[33m\n\nTargets:$(END)" } \
		/^[.a-zA-Z_-]+:.*?##/ { if(target=="")print ""; target=$$1; printf " $(BLUE)%-10s$(END) %s\n\n", $$1, $$2 } \
		/^([.a-zA-Z_-]+):/ {if(target=="")print "";match($$0, "(.*):"); target=substr($$0,RSTART,RLENGTH) } \
		/^\t## (.*)/ { match($$0, "[^\t#:\\\\]+"); txt=substr($$0,RSTART,RLENGTH);printf " $(BLUE)%-10s$(END)", target; printf " %s\n", txt ; target=""} \
		/^## (.*)/ {match($$0, "[^\t#\\\\]+"); txt=substr($$0,RSTART,RLENGTH);printf "\n$(YELLOW)%s$(END)\n", txt ; target=""} \
	' $(MAKEFILE_LIST)
	@# https://gist.github.com/gfranxman/73b5dc6369dc684db6848198290330c7#file-makefile

.DEFAULT_GOAL := usage
