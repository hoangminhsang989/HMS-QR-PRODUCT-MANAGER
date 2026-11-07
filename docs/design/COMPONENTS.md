# Reusable components

<!-- NOT YET ADOPTED: this vocabulary is a proposal, not a description. Of the
     30 names below, 28 are not defined anywhere in the product - not as a
     class, not as a function, not as a CSS class. Only `StatusBadge` and
     `Toast` have anything resembling a definition, and both are the incidental
     kebab-case CSS selectors `status-badge` and `toast`, not components in the
     sense this list means. The sentence below says these "are the shared
     vocabulary" and that the existing windows "use these semantics", which
     reads as a statement about what exists. It is not one.
     tests/stage6/test_design_document_matches_code.py reads the two numbers
     above and asserts they match what it measures, so the marker cannot drift
     from the truth. It also asserts this marker is present while the names are
     undefined, and demands every name be defined the moment it is removed. -->

AppShell, TopBar, SideNavigation, TabBar, StatusBadge, DataTable, SearchField, FilterBar, FormField, Select, DateField, QuantityField, PrimaryButton, SecondaryButton, DangerButton, ActionMenu, Dialog, ConfirmationDialog, Toast, EmptyState, LoadingState, ErrorState, HistoryTimeline, ProductCard, TrackingCard, QRCard, UserChip, MachiningTypeSelector, AttemptButtonGroup and WorkflowActionGrid are the shared vocabulary. Existing PySide6 windows and the mobile page use these semantics while retaining existing service/API contracts.
