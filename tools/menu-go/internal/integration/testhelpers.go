package integration

import (
	"context"
	"testing"
)

// AssertItemsCount checks if items slice has expected count
func AssertItemsCount(t *testing.T, items []Item, expected int) {
	t.Helper()
	if len(items) != expected {
		t.Fatalf("expected %d items, got %d", expected, len(items))
	}
}

// AssertItemHasField checks if an item has a non-empty field
func AssertItemHasField(t *testing.T, item Item, field string, value interface{}) {
	t.Helper()
	switch field {
	case "Title":
		if item.Title != value {
			t.Fatalf("expected Title to be %v, got %v", value, item.Title)
		}
	case "Description":
		if item.Description != value {
			t.Fatalf("expected Description to be %v, got %v", value, item.Description)
		}
	case "Category":
		if item.Category != value {
			t.Fatalf("expected Category to be %v, got %v", value, item.Category)
		}
	case "Icon":
		if item.Icon != value {
			t.Fatalf("expected Icon to be %v, got %v", value, item.Icon)
		}
	case "Executable":
		if item.Executable != value {
			t.Fatalf("expected Executable to be %v, got %v", value, item.Executable)
		}
	}
}

// MockIntegration is a mock implementation of Integration interface for testing
type MockIntegration struct {
	NameVal              string
	TypeVal              IntegrationType
	LoadFunc             func(ctx context.Context) ([]Item, error)
	GetFunc              func(ctx context.Context, id string) (*Item, error)
	SearchFunc           func(ctx context.Context, query string) ([]Item, error)
	ExecuteFunc          func(ctx context.Context, item Item) (string, error)
	SupportsExecutionVal bool
	RefreshFunc          func(ctx context.Context) error
}

func (m *MockIntegration) Name() string {
	return m.NameVal
}

func (m *MockIntegration) Type() IntegrationType {
	return m.TypeVal
}

func (m *MockIntegration) Load(ctx context.Context) ([]Item, error) {
	if m.LoadFunc != nil {
		return m.LoadFunc(ctx)
	}
	return []Item{}, nil
}

func (m *MockIntegration) Get(ctx context.Context, id string) (*Item, error) {
	if m.GetFunc != nil {
		return m.GetFunc(ctx, id)
	}
	return nil, nil
}

func (m *MockIntegration) Search(ctx context.Context, query string) ([]Item, error) {
	if m.SearchFunc != nil {
		return m.SearchFunc(ctx, query)
	}
	return []Item{}, nil
}

func (m *MockIntegration) Execute(ctx context.Context, item Item) (string, error) {
	if m.ExecuteFunc != nil {
		return m.ExecuteFunc(ctx, item)
	}
	return "", nil
}

func (m *MockIntegration) SupportsExecution() bool {
	return m.SupportsExecutionVal
}

func (m *MockIntegration) Refresh(ctx context.Context) error {
	if m.RefreshFunc != nil {
		return m.RefreshFunc(ctx)
	}
	return nil
}
