# Makefile for menu-go
BINARY_NAME=menu
BUILD_DIR=.
INSTALL_DIR=$(HOME)/.local/bin
CMD_DIR=./cmd/menu

VERSION=$(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT=$(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
LDFLAGS=-ldflags "-X main.Version=$(VERSION) -X main.Commit=$(COMMIT)"

.PHONY: build
build:
	@echo "Building $(BINARY_NAME)..."
	go build $(LDFLAGS) -o $(BUILD_DIR)/$(BINARY_NAME) $(CMD_DIR)
	@echo "Build complete: $(BUILD_DIR)/$(BINARY_NAME)"

.PHONY: test
test:
	@echo "Running tests..."
	go test -v ./...

.PHONY: install
install: build
	@echo "Installing $(BINARY_NAME) to $(INSTALL_DIR)..."
	mkdir -p $(INSTALL_DIR)
	cp $(BUILD_DIR)/$(BINARY_NAME) $(INSTALL_DIR)/$(BINARY_NAME)
	chmod +x $(INSTALL_DIR)/$(BINARY_NAME)
	@echo "Installed: $(INSTALL_DIR)/$(BINARY_NAME)"

.PHONY: clean
clean:
	@echo "Cleaning..."
	rm -f $(BUILD_DIR)/$(BINARY_NAME)
	@echo "Clean complete"

.PHONY: run
run: build
	./$(BINARY_NAME)

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  build   - Build the binary"
	@echo "  test    - Run tests"
	@echo "  install - Build and install to ~/.local/bin"
	@echo "  clean   - Remove build artifacts"
	@echo "  run     - Build and run"
	@echo "  help    - Show this help"
