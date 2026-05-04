import { Badge, Button, Group, Paper, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import type { ReactNode } from "react";

type CoreDraftTabProps = {
  isOperationsRoute: boolean;
  visibleDraftCount: number;
  onToggleOperationsRoute: () => void;
  summaryContent?: ReactNode;
  attentionContent?: ReactNode;
  draftListContent: ReactNode;
  detailContent: ReactNode;
  advancedContent?: ReactNode;
  showAdvancedContent?: boolean;
  onToggleAdvancedContent?: () => void;
};

export default function CoreDraftTab({
  isOperationsRoute,
  visibleDraftCount,
  onToggleOperationsRoute,
  summaryContent,
  attentionContent,
  draftListContent,
  detailContent,
  advancedContent,
  showAdvancedContent = false,
  onToggleAdvancedContent,
}: CoreDraftTabProps) {
  return (
    <Stack gap="sm">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap={2}>
          <Title order={3}>Draft Inbox</Title>
          <Text size="sm" c="dimmed">
            What needs human attention now: review items, contradictions, assignments, and quick decisions.
          </Text>
        </Stack>
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
            {isOperationsRoute ? "Back to inbox" : "Open operations"}
          </Button>
        </Group>
      </Group>
      {summaryContent}
      {attentionContent ? (
        <Paper withBorder p="sm" radius="md">
          <Stack gap="sm">
            <Group justify="space-between" align="center" wrap="wrap">
              <Stack gap={0}>
                <Text size="sm" fw={700}>
                  Needs attention
                </Text>
                <Text size="xs" c="dimmed">
                  Focus on the items that need a human decision, not on the system controls behind them.
                </Text>
              </Stack>
              <Badge size="xs" variant="light" color="orange">
                review workflow
              </Badge>
            </Group>
            {attentionContent}
          </Stack>
        </Paper>
      ) : null}
      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="sm">
        {draftListContent}
        {detailContent}
      </SimpleGrid>
      {isOperationsRoute && advancedContent ? (
        <Paper withBorder p="sm" radius="md">
          <Stack gap="sm">
            <Group justify="space-between" align="center" wrap="wrap">
              <Stack gap={0}>
                <Text size="sm" fw={700}>
                  Advanced operations & diagnostics
                </Text>
                <Text size="xs" c="dimmed">
                  Secondary path for migration, policy tuning, diagnostics, and system maintenance.
                </Text>
              </Stack>
              <Button
                size="xs"
                variant={showAdvancedContent ? "light" : "subtle"}
                color="gray"
                onClick={onToggleAdvancedContent}
              >
                {showAdvancedContent ? "Hide advanced" : "Show advanced"}
              </Button>
            </Group>
            {showAdvancedContent ? (
              advancedContent
            ) : (
              <Text size="xs" c="dimmed">
                Hidden by default so the inbox stays centered on review work, not on control-plane surfaces.
              </Text>
            )}
          </Stack>
        </Paper>
      ) : null}
    </Stack>
  );
}
