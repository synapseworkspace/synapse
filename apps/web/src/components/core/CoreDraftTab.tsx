import { Badge, Button, Group, SimpleGrid, Stack, Title } from "@mantine/core";
import type { ReactNode } from "react";

type CoreDraftTabProps = {
  isOperationsRoute: boolean;
  visibleDraftCount: number;
  onToggleOperationsRoute: () => void;
  migrationPanel: ReactNode;
  draftListContent: ReactNode;
  detailContent: ReactNode;
};

export default function CoreDraftTab({
  isOperationsRoute,
  visibleDraftCount,
  onToggleOperationsRoute,
  migrationPanel,
  draftListContent,
  detailContent,
}: CoreDraftTabProps) {
  return (
    <Stack gap="sm">
      <Group justify="space-between" align="center">
        <Title order={3}>Draft Inbox</Title>
        <Group gap="xs" wrap="wrap">
          <Badge variant="light" color="cyan">
            {visibleDraftCount}
          </Badge>
          <Button
            size="compact-sm"
            variant="light"
            color={isOperationsRoute ? "gray" : "orange"}
            onClick={onToggleOperationsRoute}
          >
            {isOperationsRoute ? "Back to Drafts" : "Open operations"}
          </Button>
        </Group>
      </Group>
      {migrationPanel}
      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
        {draftListContent}
        {detailContent}
      </SimpleGrid>
    </Stack>
  );
}
