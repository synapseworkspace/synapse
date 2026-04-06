import { Box, Breadcrumbs, Button, Code, Group, Kbd, Text, TextInput } from "@mantine/core";
import { IconArrowsShuffle, IconFilePlus, IconLink, IconSearch } from "@tabler/icons-react";

type CoreWorkspaceTab = "wiki" | "drafts" | "tasks";

type CoreWorkspaceTopBarProps = {
  isOperationsRoute: boolean;
  coreWorkspaceTab: CoreWorkspaceTab;
  pageFilter: string;
  selectedPageSlug: string | null;
  pageEditMode: boolean;
  projectId: string;
  scopeSpaceLabel: string | null;
  scopePageLabel: string | null;
  selectedSpaceKey: string | null;
  onOpenWiki: () => void;
  onOpenDrafts: () => void;
  onOpenTasks: () => void;
  onOpenOperations: () => void;
  onPageFilterChange: (value: string) => void;
  onToggleCreate: () => void;
  onShareCurrentPage: () => void;
  onEditPage: () => void;
  onOpenPublish: () => void;
  onSync: () => void;
  onCopyScopeLink: () => void;
  onClearSpaceScope: () => void;
  onOpenRolesGuide: () => void;
};

export default function CoreWorkspaceTopBar({
  isOperationsRoute,
  coreWorkspaceTab,
  pageFilter,
  selectedPageSlug,
  pageEditMode,
  projectId,
  scopeSpaceLabel,
  scopePageLabel,
  selectedSpaceKey,
  onOpenWiki,
  onOpenDrafts,
  onOpenTasks,
  onOpenOperations,
  onPageFilterChange,
  onToggleCreate,
  onShareCurrentPage,
  onEditPage,
  onOpenPublish,
  onSync,
  onCopyScopeLink,
  onClearSpaceScope,
  onOpenRolesGuide,
}: CoreWorkspaceTopBarProps) {
  const hasSelectedPage = Boolean(selectedPageSlug);

  return (
    <Box className="confluence-topbar">
      <Group justify="space-between" align="center" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <Text className="eyebrow">Synapse Wiki</Text>
          <Button size="compact-sm" variant={!isOperationsRoute && coreWorkspaceTab === "wiki" ? "filled" : "light"} color={!isOperationsRoute && coreWorkspaceTab === "wiki" ? "blue" : "gray"} onClick={onOpenWiki}>
            Wiki
          </Button>
          <Button size="compact-sm" variant={!isOperationsRoute && coreWorkspaceTab === "drafts" ? "filled" : "light"} color={!isOperationsRoute && coreWorkspaceTab === "drafts" ? "blue" : "gray"} onClick={onOpenDrafts}>
            Drafts
          </Button>
          <Button size="compact-sm" variant={!isOperationsRoute && coreWorkspaceTab === "tasks" ? "filled" : "light"} color={!isOperationsRoute && coreWorkspaceTab === "tasks" ? "blue" : "gray"} onClick={onOpenTasks}>
            Tasks
          </Button>
          <Button size="compact-sm" variant={isOperationsRoute ? "filled" : "light"} color={isOperationsRoute ? "orange" : "gray"} onClick={onOpenOperations}>
            Operations
          </Button>
        </Group>
        <Group gap="xs" wrap="nowrap" className="confluence-topbar-actions">
          <TextInput
            size="sm"
            placeholder="Search page title or slug"
            value={pageFilter}
            onChange={(event) => onPageFilterChange(event.currentTarget.value)}
            leftSection={<IconSearch size={14} />}
            w={300}
            rightSection={<Kbd size="xs">⌘/Ctrl+K</Kbd>}
            className="confluence-topbar-search"
          />
          {!isOperationsRoute ? (
            <>
              <Button size="sm" variant="light" leftSection={<IconFilePlus size={14} />} onClick={onToggleCreate}>
                New page
              </Button>
              <Button
                size="sm"
                variant="light"
                leftSection={<IconLink size={14} />}
                onClick={onShareCurrentPage}
                disabled={!hasSelectedPage}
              >
                Share
              </Button>
              {hasSelectedPage && !pageEditMode ? (
                <Button size="sm" variant="light" color="blue" onClick={onEditPage}>
                  Edit
                </Button>
              ) : null}
              {hasSelectedPage ? (
                <Button size="sm" variant="filled" color="blue" onClick={onOpenPublish} disabled={pageEditMode}>
                  Publish
                </Button>
              ) : null}
            </>
          ) : (
            <Button size="sm" variant="light" color="orange" onClick={onOpenWiki}>
              Back to Wiki
            </Button>
          )}
          <Button size="sm" variant="light" leftSection={<IconArrowsShuffle size={14} />} onClick={onSync}>
            Sync
          </Button>
        </Group>
      </Group>
      <Group id="core-scope-breadcrumb" justify="space-between" align="center" mt={8} wrap="wrap">
        <Breadcrumbs separator="›">
          <Code>{projectId.trim() || "workspace"}</Code>
          <Code>{scopeSpaceLabel || "all-spaces"}</Code>
          <Text size="sm" c={scopePageLabel ? undefined : "dimmed"}>
            {scopePageLabel || "no-page-selected"}
          </Text>
        </Breadcrumbs>
        <Group gap={6} wrap="wrap">
          <Button size="compact-sm" variant="subtle" data-testid="core-copy-scope-link" onClick={onCopyScopeLink}>
            Copy scope link
          </Button>
          {selectedSpaceKey ? (
            <Button size="compact-sm" variant="subtle" data-testid="core-clear-space-scope" onClick={onClearSpaceScope}>
              Clear space scope
            </Button>
          ) : null}
          <Button size="compact-sm" variant="subtle" onClick={onOpenRolesGuide}>
            Roles & access
          </Button>
        </Group>
      </Group>
    </Box>
  );
}
