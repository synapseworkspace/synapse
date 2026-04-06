import { Badge, Divider, Group, Paper, ScrollArea, Select, Stack, Text, TextInput } from "@mantine/core";
import type { ReactNode } from "react";

type CoreWorkspaceLeftRailProps = {
  projectId: string;
  reviewer: string;
  selectedSpaceKey: string | null;
  pageStatusFilter: string | null;
  spaceOptions: Array<{ value: string; label: string }>;
  pageCount: number;
  onProjectIdChange: (value: string) => void;
  onReviewerChange: (value: string) => void;
  onSpaceChange: (value: string | null) => void;
  onPageStatusChange: (value: string | null) => void;
  lifecyclePanel: ReactNode;
  treeContent: ReactNode;
};

export default function CoreWorkspaceLeftRail({
  projectId,
  reviewer,
  selectedSpaceKey,
  pageStatusFilter,
  spaceOptions,
  pageCount,
  onProjectIdChange,
  onReviewerChange,
  onSpaceChange,
  onPageStatusChange,
  lifecyclePanel,
  treeContent,
}: CoreWorkspaceLeftRailProps) {
  return (
    <Paper className="confluence-left-rail" withBorder>
      <Stack gap="sm">
        <TextInput
          size="xs"
          label="Workspace"
          value={projectId}
          onChange={(event) => onProjectIdChange(event.currentTarget.value)}
          placeholder="omega_demo"
        />
        <TextInput
          size="xs"
          label="Your name"
          value={reviewer}
          onChange={(event) => onReviewerChange(event.currentTarget.value)}
          placeholder="ops_manager"
        />
        <Select
          size="xs"
          label="Space"
          value={selectedSpaceKey}
          onChange={onSpaceChange}
          clearable
          data={spaceOptions}
          placeholder="All spaces"
        />
        <Select
          size="xs"
          label="Status"
          value={pageStatusFilter}
          onChange={onPageStatusChange}
          clearable
          data={[
            { value: "published", label: "Published" },
            { value: "reviewed", label: "Reviewed" },
            { value: "draft", label: "Draft" },
            { value: "archived", label: "Archived" },
          ]}
          placeholder="All statuses"
        />
        {lifecyclePanel}
      </Stack>
      <Divider my="sm" />
      <Group justify="space-between" mb={6}>
        <Text size="sm" fw={700}>
          Pages
        </Text>
        <Badge size="xs" variant="light" color="blue">
          {pageCount}
        </Badge>
      </Group>
      <ScrollArea h={760} type="auto">
        <Stack gap={2} className="confluence-tree">
          {treeContent}
        </Stack>
      </ScrollArea>
    </Paper>
  );
}
