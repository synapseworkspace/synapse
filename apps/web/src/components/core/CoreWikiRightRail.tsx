import {
  Accordion,
  Badge,
  Button,
  Checkbox,
  Divider,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";

type SectionItem = {
  section_key: string;
  heading: string;
  statement_count: number;
};

type ReviewAssignmentItem = {
  id: string;
  assignee: string;
  role: string;
  status: string;
};

type PolicyAuditItem = {
  id: string;
  changed_by: string;
  changed_fields: string[];
  created_at: string | null;
};

type RelatedPageItem = {
  slug: string;
  title: string;
  updated_at: string | null;
};

type PageVersionItem = {
  version: number;
  created_by: string;
  change_summary: string | null;
  created_at: string | null;
};

type ChecklistOption = {
  value: string;
  label: string;
};

type CoreWikiRightRailProps = {
  isOperationsRoute: boolean;
  selectedPageSlug: string | null;
  selectedPageStatus: string | null;
  selectedPageVersion: number | null;
  sections: SectionItem[];
  openDraftCount: number;
  onOpenDrafts: () => void;
  reviewAssignments: ReviewAssignmentItem[];
  assignmentAssigneeInput: string;
  assignmentNoteInput: string;
  onAssignmentAssigneeChange: (value: string) => void;
  onAssignmentNoteChange: (value: string) => void;
  onCreateReviewTask: () => void;
  onAssignReviewer: () => void;
  onResolveAssignment: (assignmentId: string) => void;
  runningLifecycleQuickAction: boolean;
  loadingPageReviewAssignments: boolean;
  savingPageAssignment: boolean;
  canCreateReviewTask: boolean;
  spaceKey: string;
  spaceWriteMode: "open" | "owners_only";
  onSpaceWriteModeChange: (value: "open" | "owners_only") => void;
  spacePublishChecklistPreset: "none" | "ops_standard" | "policy_strict";
  onSpacePublishChecklistPresetChange: (value: "none" | "ops_standard" | "policy_strict") => void;
  publishChecklistOptions: ChecklistOption[];
  spaceReviewRequired: boolean;
  onSpaceReviewRequiredChange: (checked: boolean) => void;
  loadingSpacePolicy: boolean;
  savingSpacePolicy: boolean;
  onSaveSpacePolicy: () => void;
  policyTimelineCount: number;
  policyTopActorText: string;
  policyCadenceText: string;
  policySourceText: string;
  loadingSpacePolicyAudit: boolean;
  loadingSpacePolicyAdoptionSummary: boolean;
  policyAuditItems: PolicyAuditItem[];
  relatedPages: RelatedPageItem[];
  onOpenRelatedPage: (slug: string) => void;
  recentVersions: PageVersionItem[];
  wikiQualitySummary: {
    pass: boolean | null;
    corePublished: number | null;
    coreRequired: number | null;
    placeholderRatioCore: number | null;
    dailySummaryDraftRatio: number | null;
  } | null;
  onOpenHistory: () => void;
  onOpenVersionHistory: (version: number) => void;
  formatDate: (value: string | null | undefined) => string;
  onOpenOperations: () => void;
};

export default function CoreWikiRightRail({
  isOperationsRoute,
  selectedPageSlug,
  selectedPageStatus,
  selectedPageVersion,
  sections,
  openDraftCount,
  onOpenDrafts,
  reviewAssignments,
  assignmentAssigneeInput,
  assignmentNoteInput,
  onAssignmentAssigneeChange,
  onAssignmentNoteChange,
  onCreateReviewTask,
  onAssignReviewer,
  onResolveAssignment,
  runningLifecycleQuickAction,
  loadingPageReviewAssignments,
  savingPageAssignment,
  canCreateReviewTask,
  spaceKey,
  spaceWriteMode,
  onSpaceWriteModeChange,
  spacePublishChecklistPreset,
  onSpacePublishChecklistPresetChange,
  publishChecklistOptions,
  spaceReviewRequired,
  onSpaceReviewRequiredChange,
  loadingSpacePolicy,
  savingSpacePolicy,
  onSaveSpacePolicy,
  policyTimelineCount,
  policyTopActorText,
  policyCadenceText,
  policySourceText,
  loadingSpacePolicyAudit,
  loadingSpacePolicyAdoptionSummary,
  policyAuditItems,
  relatedPages,
  onOpenRelatedPage,
  recentVersions,
  wikiQualitySummary,
  onOpenHistory,
  onOpenVersionHistory,
  formatDate,
  onOpenOperations,
}: CoreWikiRightRailProps) {
  return (
    <Paper className="confluence-right-rail" withBorder>
      {!selectedPageSlug ? (
        <Text size="sm" c="dimmed">
          Select a page to see details.
        </Text>
      ) : (
        <Stack gap="sm">
          <Group justify="space-between" align="center">
            <Text fw={700} size="sm">
              Page Details
            </Text>
            <Badge variant="light" color="blue">
              {selectedPageStatus || "n/a"}
            </Badge>
          </Group>
          <Text size="xs" c="dimmed" style={{ overflowWrap: "anywhere" }}>
            slug: {selectedPageSlug}
          </Text>
          <Text size="xs" c="dimmed">
            version: v{selectedPageVersion ?? "—"}
          </Text>
          <Divider />
          <Text size="xs" fw={700}>
            Sections
          </Text>
          {sections.length === 0 ? (
            <Text size="xs" c="dimmed">
              No sections.
            </Text>
          ) : (
            <Stack gap={4}>
              {sections.slice(0, 8).map((section) => (
                <Text key={`core-side-section-${section.section_key}`} size="xs" c="dimmed">
                  {section.heading} ({section.statement_count})
                </Text>
              ))}
            </Stack>
          )}
          <Divider />
          <Text size="xs" fw={700}>
            Open drafts
          </Text>
          <Badge size="sm" variant="light" color="orange">
            {openDraftCount}
          </Badge>
          <Button size="compact-sm" variant="filled" color="cyan" fullWidth onClick={onOpenDrafts}>
            Open Drafts
          </Button>
          <Divider />
          <Text size="xs" fw={700}>
            Wiki quality
          </Text>
          {wikiQualitySummary ? (
            <Stack gap={4}>
              <Group gap={6} wrap="wrap">
                <Badge size="xs" variant="light" color={wikiQualitySummary.pass ? "teal" : "orange"}>
                  {wikiQualitySummary.pass ? "healthy" : "attention"}
                </Badge>
                <Badge size="xs" variant="light" color="gray">
                  core {wikiQualitySummary.corePublished ?? "—"}/{wikiQualitySummary.coreRequired ?? "—"}
                </Badge>
              </Group>
              <Text size="xs" c="dimmed">
                placeholders{" "}
                {Number.isFinite(Number(wikiQualitySummary.placeholderRatioCore))
                  ? `${Math.round(Number(wikiQualitySummary.placeholderRatioCore) * 100)}%`
                  : "—"}
                {" · "}daily-summary drafts{" "}
                {Number.isFinite(Number(wikiQualitySummary.dailySummaryDraftRatio))
                  ? `${Math.round(Number(wikiQualitySummary.dailySummaryDraftRatio) * 100)}%`
                  : "—"}
              </Text>
            </Stack>
          ) : (
            <Text size="xs" c="dimmed">
              Quality report appears after bootstrap + KPI refresh.
            </Text>
          )}
          <Divider />
          {isOperationsRoute ? (
            <Accordion multiple variant="separated" radius="md" chevronPosition="right" defaultValue={[]}>
              <Accordion.Item value="review-workflow">
                <Accordion.Control>
                  <Group justify="space-between" wrap="nowrap" style={{ width: "100%" }}>
                    <Text size="xs" fw={700}>
                      Review workflow
                    </Text>
                    <Badge size="xs" variant="light" color="orange">
                      {reviewAssignments.filter((item) => item.status === "open").length}
                    </Badge>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel>
                  <Paper withBorder p="xs" radius="md" id="wiki-review-assignments">
                    <Stack gap={6}>
                      <TextInput
                        size="xs"
                        placeholder="assignee_id"
                        value={assignmentAssigneeInput}
                        onChange={(event) => onAssignmentAssigneeChange(event.currentTarget.value)}
                      />
                      <TextInput
                        size="xs"
                        placeholder="Note (optional)"
                        value={assignmentNoteInput}
                        onChange={(event) => onAssignmentNoteChange(event.currentTarget.value)}
                      />
                      <Group gap={6} justify="flex-end" wrap="wrap">
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="blue"
                          loading={runningLifecycleQuickAction}
                          disabled={!canCreateReviewTask}
                          onClick={onCreateReviewTask}
                        >
                          Create review task
                        </Button>
                        <Button
                          size="compact-xs"
                          variant="light"
                          color="orange"
                          loading={savingPageAssignment}
                          onClick={onAssignReviewer}
                        >
                          Assign reviewer
                        </Button>
                      </Group>
                      {loadingPageReviewAssignments ? (
                        <Group gap={6}>
                          <Loader size="xs" />
                          <Text size="xs" c="dimmed">
                            loading assignments…
                          </Text>
                        </Group>
                      ) : reviewAssignments.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No assignments yet.
                        </Text>
                      ) : (
                        <Stack gap={4}>
                          {reviewAssignments.slice(0, 6).map((assignment) => (
                            <Group key={`core-assignment-${assignment.id}`} justify="space-between" align="center" wrap="nowrap">
                              <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                                <Text size="xs" fw={700} lineClamp={1}>
                                  {assignment.assignee}
                                </Text>
                                <Text size="xs" c="dimmed">
                                  {assignment.status} • {assignment.role}
                                </Text>
                              </Stack>
                              {assignment.status === "open" ? (
                                <Button
                                  size="compact-xs"
                                  variant="subtle"
                                  color="teal"
                                  loading={savingPageAssignment}
                                  onClick={() => onResolveAssignment(assignment.id)}
                                >
                                  Resolve
                                </Button>
                              ) : (
                                <Badge size="xs" variant="light" color="gray">
                                  resolved
                                </Badge>
                              )}
                            </Group>
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </Paper>
                </Accordion.Panel>
              </Accordion.Item>

              <Accordion.Item value="space-governance">
                <Accordion.Control>
                  <Group justify="space-between" wrap="nowrap" style={{ width: "100%" }}>
                    <Text size="xs" fw={700}>
                      Space governance
                    </Text>
                    <Badge size="xs" variant="light" color="violet">
                      {spaceKey}
                    </Badge>
                  </Group>
                </Accordion.Control>
                <Accordion.Panel>
                  <Paper withBorder p="xs" radius="md" id="wiki-governance-panel">
                    <Stack gap={6}>
                      <Select
                        size="xs"
                        label="Write mode"
                        value={spaceWriteMode}
                        onChange={(value) => {
                          if (value === "open" || value === "owners_only") onSpaceWriteModeChange(value);
                        }}
                        data={[
                          { value: "open", label: "open" },
                          { value: "owners_only", label: "owners_only" },
                        ]}
                        allowDeselect={false}
                        disabled={loadingSpacePolicy}
                      />
                      <Select
                        size="xs"
                        label="Publish checklist"
                        value={spacePublishChecklistPreset}
                        onChange={(value) => {
                          if (value === "none" || value === "ops_standard" || value === "policy_strict") {
                            onSpacePublishChecklistPresetChange(value);
                          }
                        }}
                        data={publishChecklistOptions}
                        allowDeselect={false}
                        disabled={loadingSpacePolicy}
                      />
                      <Checkbox
                        size="xs"
                        checked={spaceReviewRequired}
                        onChange={(event) => onSpaceReviewRequiredChange(event.currentTarget.checked)}
                        label="Require review assignment"
                        disabled={loadingSpacePolicy}
                      />
                      <Group justify="flex-end">
                        <Button size="compact-xs" variant="light" color="violet" loading={savingSpacePolicy} onClick={onSaveSpacePolicy}>
                          Save policy
                        </Button>
                      </Group>
                      <Paper withBorder p="xs" radius="md" id="wiki-policy-timeline">
                        <Group justify="space-between" align="center" mb={4}>
                          <Text size="xs" fw={700}>
                            Policy timeline
                          </Text>
                          <Badge size="xs" variant="light" color="blue">
                            {policyTimelineCount}
                          </Badge>
                        </Group>
                        <Text size="xs" c="dimmed">
                          top actor: {policyTopActorText}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {policyCadenceText}
                        </Text>
                        <Text size="xs" c="dimmed" mb={6}>
                          source: {policySourceText}
                        </Text>
                        {loadingSpacePolicyAudit || loadingSpacePolicyAdoptionSummary ? (
                          <Group gap={6}>
                            <Loader size="xs" />
                            <Text size="xs" c="dimmed">
                              loading policy timeline…
                            </Text>
                          </Group>
                        ) : policyAuditItems.length === 0 ? (
                          <Text size="xs" c="dimmed">
                            No policy changes yet.
                          </Text>
                        ) : (
                          <Stack gap={4}>
                            {policyAuditItems.slice(0, 4).map((item) => (
                              <Text key={`core-policy-audit-${item.id}`} size="xs" c="dimmed">
                                {formatDate(item.created_at)} • {item.changed_by || "unknown"} • {item.changed_fields.join(", ") || "metadata"}
                              </Text>
                            ))}
                          </Stack>
                        )}
                      </Paper>
                    </Stack>
                  </Paper>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          ) : (
            <Stack gap={8}>
              <Paper withBorder p="xs" radius="md">
                <Stack gap={6}>
                  <Group justify="space-between" align="center">
                    <Text size="xs" fw={700}>
                      Related pages
                    </Text>
                    <Badge size="xs" variant="light" color="blue">
                      {relatedPages.length}
                    </Badge>
                  </Group>
                  {relatedPages.length === 0 ? (
                    <Text size="xs" c="dimmed">
                      No related pages in this space.
                    </Text>
                  ) : (
                    <Stack gap={4}>
                      {relatedPages.slice(0, 5).map((page) => (
                        <Button
                          key={`core-right-related-${page.slug}`}
                          size="compact-xs"
                          variant="subtle"
                          color="gray"
                          justify="flex-start"
                          onClick={() => onOpenRelatedPage(page.slug)}
                        >
                          <Text size="xs" lineClamp={1}>
                            {page.title || page.slug}
                          </Text>
                        </Button>
                      ))}
                    </Stack>
                  )}
                </Stack>
              </Paper>
              <Paper withBorder p="xs" radius="md" data-testid="core-right-recent-versions">
                <Stack gap={6}>
                  <Group justify="space-between" align="center">
                    <Text size="xs" fw={700}>
                      Recent versions
                    </Text>
                    <Group gap={6} wrap="nowrap">
                      <Badge size="xs" variant="light" color="teal">
                        {recentVersions.length}
                      </Badge>
                      <Button size="compact-xs" variant="subtle" color="gray" onClick={onOpenHistory}>
                        Open
                      </Button>
                    </Group>
                  </Group>
                  {recentVersions.length === 0 ? (
                    <Text size="xs" c="dimmed">
                      No history available.
                    </Text>
                  ) : (
                    <Stack gap={4}>
                      {recentVersions.slice(0, 4).map((version) => (
                        <Button
                          key={`core-right-version-${version.version}`}
                          data-testid={`core-right-version-open-${version.version}`}
                          size="compact-xs"
                          variant="subtle"
                          color="gray"
                          justify="flex-start"
                          onClick={() => onOpenVersionHistory(version.version)}
                        >
                          <Text size="xs" lineClamp={1}>
                            v{version.version} • {version.created_by || "unknown"} • {formatDate(version.created_at)}
                            {version.change_summary ? ` • ${version.change_summary}` : ""}
                          </Text>
                        </Button>
                      ))}
                    </Stack>
                  )}
                </Stack>
              </Paper>
              <Paper withBorder p="xs" radius="md">
                <Stack gap={6}>
                  <Text size="xs" c="dimmed">
                    Review workflow and space governance are available in Operations.
                  </Text>
                  <Button size="compact-xs" variant="light" color="indigo" onClick={onOpenOperations}>
                    Open operations
                  </Button>
                </Stack>
              </Paper>
            </Stack>
          )}
        </Stack>
      )}
    </Paper>
  );
}
