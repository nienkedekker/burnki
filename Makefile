.PHONY: build clean

ADDON_DIR := burnki
DIST_DIR := dist
ADDON_FILE := $(DIST_DIR)/burnki.ankiaddon

build:
	@mkdir -p $(DIST_DIR)
	@cd $(ADDON_DIR) && zip -r ../$(ADDON_FILE) . -x "*.pyc" -x "__pycache__/*" -x ".DS_Store"
	@echo "Built $(ADDON_FILE)"

clean:
	rm -rf $(DIST_DIR)
