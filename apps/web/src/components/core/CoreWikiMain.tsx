import { Breadcrumbs, Button, Group, Stack, Text } from "@mantine/core";
import { IconFilePlus, IconHistory, IconRefresh } from "@tabler/icons-react";
import type { ReactNode } from "react";

type BreadcrumbItem = {
  label: string;
  slug: string | null;
};

type CoreWikiMainProps = {
  isOperationsRoute: boolean;
  wikiPageBreadcrumb: BreadcrumbItem[];
  selectedPageSlug: string | null;
  pageEditMode: boolean;
  showCreatePanel: boolean;
  onSelectBreadcrumb: (slug: string | null) => void;
  onToggleCreatePanel: () => void;
  onRefreshPage: () => void;
  onEnterEdit: () => void;
  onOpenHistory: () => void;
  createPanel: ReactNode;
  children: ReactNode;
};

export default function CoreWikiMain({
  isOperationsRoute,
  wikiPageBreadcrumb,
  selectedPageSlug,
  pageEditMode,
  showCreatePanel,
  onSelectBreadcrumb,
  onToggleCreatePanel,
  onRefreshPage,
  onEnterEdit,
  onOpenHistory,
  createPanel,
  children,
}: CoreWikiMainProps) {
  return (
    <Stack gap="sm" className="confluence-page-view">
      <Group justify="space-between" align="center" wrap="wrap" className="confluence-page-toolbar">
        <Breadcrumbs separator="›">
          {wikiPageBreadcrumb.map((crumb, index) => (
            <Text
              key={`confluence-crumb-${index}-${crumb.slug || "root"}`}
              size="sm"
              c={crumb.slug ? "dimmed" : "gray"}
              style={crumb.slug ? { cursor: "pointer" } : undefined}
              onClick={() => onSelectBreadcrumb(crumb.slug)}
            >
              {crumb.label}
            </Text>
          ))}
        </Breadcrumbs>
        <Group gap="xs" className="confluence-page-actions">
          {isOperationsRoute ? (
            <Button size="compact-sm" variant="light" leftSection={<IconFilePlus size={14} />} onClick={onToggleCreatePanel}>
              Create
            </Button>
          ) : null}
          {selectedPageSlug ? (
            <Button size="compact-sm" variant="light" leftSection={<IconRefresh size={14} />} onClick={onRefreshPage}>
              Refresh page
            </Button>
          ) : null}
          {selectedPageSlug ? (
            <Button size="compact-sm" variant="light" leftSection={<IconHistory size={14} />} onClick={onOpenHistory}>
              History
            </Button>
          ) : null}
          {isOperationsRoute && selectedPageSlug && !pageEditMode ? (
            <Button size="compact-sm" variant="filled" color="blue" onClick={onEnterEdit}>
              Edit
            </Button>
          ) : null}
        </Group>
      </Group>

      {showCreatePanel ? createPanel : null}
      {children}
    </Stack>
  );
}
