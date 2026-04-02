import {
  Badge,
  Button,
  Card,
  Code,
  Divider,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconRefresh } from "@tabler/icons-react";
import { useCallback, useEffect, useMemo, useState } from "react";

type TaskStatus = "todo" | "in_progress" | "blocked" | "done" | "canceled";
type TaskPriority = "low" | "normal" | "high" | "critical";

type TaskSummary = {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  source: "agent" | "human" | "system";
  assignee: string | null;
  entity_key: string | null;
  category: string | null;
  due_at: string | null;
  created_by: string | null;
  metadata: Record<string, unknown>;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
};

type TaskEvent = {
  id: string;
  task_id: string;
  project_id: string;
  event_type: string;
  actor: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

type TaskLink = {
  id: string;
  task_id: string;
  project_id: string;
  link_type: "claim" | "draft" | "page" | "event" | "external";
  link_ref: string;
  note: string | null;
  metadata: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
};

type TaskDetailPayload = {
  task: TaskSummary;
  events: TaskEvent[];
  links: TaskLink[];
};

type CreateTaskState = {
  title: string;
  description: string;
  priority: TaskPriority;
  assignee: string;
  entityKey: string;
  category: string;
  dueAt: string;
};

type LinkFormState = {
  linkType: "claim" | "draft" | "page" | "event" | "external";
  linkRef: string;
  note: string;
};

const DEFAULT_CREATE_TASK: CreateTaskState = {
  title: "",
  description: "",
  priority: "normal",
  assignee: "",
  entityKey: "",
  category: "",
  dueAt: "",
};

const DEFAULT_LINK_FORM: LinkFormState = {
  linkType: "draft",
  linkRef: "",
  note: "",
};

function fmtDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function statusColor(status: TaskStatus): string {
  if (status === "in_progress") return "cyan";
  if (status === "blocked") return "orange";
  if (status === "done") return "green";
  if (status === "canceled") return "red";
  return "blue";
}

function randomKey(): string {
  return `task-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function apiFetch<T>(
  apiUrl: string,
  path: string,
  options?: {
    method?: "GET" | "POST";
    body?: Record<string, unknown>;
    idempotencyKey?: string;
  },
): Promise<T> {
  const root = apiUrl.replace(/\/+$/, "");
  const response = await fetch(`${root}${path}`, {
    method: options?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options?.idempotencyKey ? { "Idempotency-Key": options.idempotencyKey } : {}),
    },
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });
  const raw = await response.text();
  const payload = raw ? (JSON.parse(raw) as T) : ({} as T);
  if (!response.ok) {
    throw new Error(`${response.status} ${raw}`);
  }
  return payload;
}

export default function TaskTrackerPanel({
  apiUrl,
  projectId,
  reviewer,
}: {
  apiUrl: string;
  projectId: string;
  reviewer: string;
}) {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [taskDetail, setTaskDetail] = useState<TaskDetailPayload | null>(null);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [runningAction, setRunningAction] = useState(false);
  const [createTask, setCreateTask] = useState<CreateTaskState>(DEFAULT_CREATE_TASK);
  const [comment, setComment] = useState("");
  const [linkForm, setLinkForm] = useState<LinkFormState>(DEFAULT_LINK_FORM);

  const taskStats = useMemo(() => {
    const total = tasks.length;
    const active = tasks.filter((item) => item.status === "todo" || item.status === "in_progress" || item.status === "blocked").length;
    const blocked = tasks.filter((item) => item.status === "blocked").length;
    const done = tasks.filter((item) => item.status === "done").length;
    return { total, active, blocked, done };
  }, [tasks]);

  const loadTasks = useCallback(async () => {
    if (!projectId.trim()) {
      notifications.show({
        color: "red",
        title: "Project ID required",
        message: "Set project id before loading tasks.",
      });
      return;
    }
    setLoadingTasks(true);
    try {
      const payload = await apiFetch<{ tasks: TaskSummary[] }>(
        apiUrl,
        `/v1/tasks?project_id=${encodeURIComponent(projectId)}&include_closed=true&limit=200`,
      );
      const loaded = payload.tasks ?? [];
      setTasks(loaded);
      if (selectedTaskId && !loaded.some((item) => item.id === selectedTaskId)) {
        setSelectedTaskId(null);
        setTaskDetail(null);
      }
      if (!selectedTaskId && loaded.length > 0) {
        setSelectedTaskId(loaded[0].id);
      }
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Task list failed",
        message: String(error),
      });
    } finally {
      setLoadingTasks(false);
    }
  }, [apiUrl, projectId, selectedTaskId]);

  const loadTaskDetail = useCallback(
    async (taskId: string) => {
      if (!projectId.trim()) return;
      setLoadingDetail(true);
      try {
        const payload = await apiFetch<TaskDetailPayload>(
          apiUrl,
          `/v1/tasks/${encodeURIComponent(taskId)}?project_id=${encodeURIComponent(projectId)}&events_limit=120&links_limit=120`,
        );
        setTaskDetail(payload);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Task detail failed",
          message: String(error),
        });
      } finally {
        setLoadingDetail(false);
      }
    },
    [apiUrl, projectId],
  );

  useEffect(() => {
    if (!selectedTaskId) {
      setTaskDetail(null);
      return;
    }
    void loadTaskDetail(selectedTaskId);
  }, [selectedTaskId, loadTaskDetail]);

  const createNewTask = useCallback(async () => {
    if (!projectId.trim()) return;
    if (!createTask.title.trim()) {
      notifications.show({
        color: "red",
        title: "Title required",
        message: "Add a task title before creating.",
      });
      return;
    }
    setRunningAction(true);
    try {
      const dueAtIso = createTask.dueAt.trim() ? new Date(createTask.dueAt).toISOString() : null;
      const payload = await apiFetch<{ task: TaskSummary }>(apiUrl, "/v1/tasks", {
        method: "POST",
        idempotencyKey: randomKey(),
        body: {
          project_id: projectId,
          title: createTask.title.trim(),
          description: createTask.description.trim() || null,
          status: "todo",
          priority: createTask.priority,
          source: "human",
          assignee: createTask.assignee.trim() || null,
          entity_key: createTask.entityKey.trim() || null,
          category: createTask.category.trim() || null,
          due_at: dueAtIso,
          metadata: {},
          created_by: reviewer.trim() || "ops_manager",
        },
      });
      notifications.show({
        color: "green",
        title: "Task created",
        message: payload.task.title,
      });
      setCreateTask(DEFAULT_CREATE_TASK);
      await loadTasks();
      setSelectedTaskId(payload.task.id);
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Create task failed",
        message: String(error),
      });
    } finally {
      setRunningAction(false);
    }
  }, [apiUrl, createTask, loadTasks, projectId, reviewer]);

  const transitionStatus = useCallback(
    async (status: TaskStatus) => {
      if (!selectedTaskId || !projectId.trim()) return;
      setRunningAction(true);
      try {
        await apiFetch(apiUrl, `/v1/tasks/${encodeURIComponent(selectedTaskId)}/status`, {
          method: "POST",
          idempotencyKey: randomKey(),
          body: {
            project_id: projectId,
            status,
            updated_by: reviewer.trim() || "ops_manager",
            note: null,
          },
        });
        await loadTasks();
        await loadTaskDetail(selectedTaskId);
      } catch (error) {
        notifications.show({
          color: "red",
          title: "Status update failed",
          message: String(error),
        });
      } finally {
        setRunningAction(false);
      }
    },
    [apiUrl, loadTaskDetail, loadTasks, projectId, reviewer, selectedTaskId],
  );

  const addComment = useCallback(async () => {
    if (!selectedTaskId || !projectId.trim()) return;
    if (!comment.trim()) return;
    setRunningAction(true);
    try {
      await apiFetch(apiUrl, `/v1/tasks/${encodeURIComponent(selectedTaskId)}/comments`, {
        method: "POST",
        idempotencyKey: randomKey(),
        body: {
          project_id: projectId,
          created_by: reviewer.trim() || "ops_manager",
          comment: comment.trim(),
          metadata: {},
        },
      });
      setComment("");
      await loadTaskDetail(selectedTaskId);
      await loadTasks();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Comment failed",
        message: String(error),
      });
    } finally {
      setRunningAction(false);
    }
  }, [apiUrl, comment, loadTaskDetail, loadTasks, projectId, reviewer, selectedTaskId]);

  const addLink = useCallback(async () => {
    if (!selectedTaskId || !projectId.trim()) return;
    if (!linkForm.linkRef.trim()) return;
    setRunningAction(true);
    try {
      await apiFetch(apiUrl, `/v1/tasks/${encodeURIComponent(selectedTaskId)}/links`, {
        method: "POST",
        idempotencyKey: randomKey(),
        body: {
          project_id: projectId,
          created_by: reviewer.trim() || "ops_manager",
          link_type: linkForm.linkType,
          link_ref: linkForm.linkRef.trim(),
          note: linkForm.note.trim() || null,
          metadata: {},
        },
      });
      setLinkForm(DEFAULT_LINK_FORM);
      await loadTaskDetail(selectedTaskId);
      await loadTasks();
    } catch (error) {
      notifications.show({
        color: "red",
        title: "Link failed",
        message: String(error),
      });
    } finally {
      setRunningAction(false);
    }
  }, [apiUrl, linkForm, loadTaskDetail, loadTasks, projectId, reviewer, selectedTaskId]);

  return (
    <Paper radius="xl" p="lg" className="intelligence-panel">
      <Group justify="space-between" align="center" mb="sm">
        <Stack gap={2}>
          <Text className="eyebrow">Agentic Todo Core</Text>
          <Title order={3}>Task Tracker</Title>
        </Stack>
        <Button
          size="xs"
          variant="light"
          leftSection={<IconRefresh size={14} />}
          onClick={() => void loadTasks()}
          loading={loadingTasks}
        >
          Refresh Tasks
        </Button>
      </Group>

      <Group gap="xs" mb="md">
        <Badge variant="light" color="teal">
          total {taskStats.total}
        </Badge>
        <Badge variant="light" color="cyan">
          active {taskStats.active}
        </Badge>
        <Badge variant="light" color="orange">
          blocked {taskStats.blocked}
        </Badge>
        <Badge variant="light" color="green">
          done {taskStats.done}
        </Badge>
      </Group>

      <SimpleGrid cols={{ base: 1, xl: 2 }} spacing="md">
        <Stack gap="md">
          <Card withBorder radius="lg">
            <Title order={5} mb="sm">
              Create Task
            </Title>
            <Stack>
              <TextInput
                label="Title"
                value={createTask.title}
                onChange={(event) => setCreateTask((prev) => ({ ...prev, title: event.currentTarget.value }))}
                placeholder="Investigate Omega gate access drift"
              />
              <Textarea
                label="Description"
                value={createTask.description}
                onChange={(event) => setCreateTask((prev) => ({ ...prev, description: event.currentTarget.value }))}
                minRows={2}
              />
              <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                <Select
                  label="Priority"
                  value={createTask.priority}
                  onChange={(value) =>
                    setCreateTask((prev) => ({ ...prev, priority: (value as TaskPriority | null) ?? "normal" }))
                  }
                  data={[
                    { label: "low", value: "low" },
                    { label: "normal", value: "normal" },
                    { label: "high", value: "high" },
                    { label: "critical", value: "critical" },
                  ]}
                />
                <TextInput
                  label="Assignee"
                  value={createTask.assignee}
                  onChange={(event) => setCreateTask((prev) => ({ ...prev, assignee: event.currentTarget.value }))}
                  placeholder="ops_manager"
                />
              </SimpleGrid>
              <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                <TextInput
                  label="Entity Key"
                  value={createTask.entityKey}
                  onChange={(event) => setCreateTask((prev) => ({ ...prev, entityKey: event.currentTarget.value }))}
                  placeholder="bc_omega"
                />
                <TextInput
                  label="Category"
                  value={createTask.category}
                  onChange={(event) => setCreateTask((prev) => ({ ...prev, category: event.currentTarget.value }))}
                  placeholder="access_policy"
                />
              </SimpleGrid>
              <TextInput
                label="Due at (ISO or browser-parseable)"
                value={createTask.dueAt}
                onChange={(event) => setCreateTask((prev) => ({ ...prev, dueAt: event.currentTarget.value }))}
                placeholder="2026-04-05T18:00:00+03:00"
              />
              <Button onClick={() => void createNewTask()} loading={runningAction}>
                Create Task
              </Button>
            </Stack>
          </Card>

          <Card withBorder radius="lg">
            <Group justify="space-between" mb="sm">
              <Title order={5}>Task Queue</Title>
              <Badge>{tasks.length}</Badge>
            </Group>
            <ScrollArea h={420} type="auto">
              <Stack gap="sm">
                {tasks.length === 0 && <Text c="dimmed">No tasks loaded yet.</Text>}
                {tasks.map((task) => (
                  <Card
                    key={task.id}
                    withBorder
                    radius="md"
                    onClick={() => setSelectedTaskId(task.id)}
                    style={{
                      cursor: "pointer",
                      borderColor: task.id === selectedTaskId ? "var(--mantine-color-cyan-6)" : undefined,
                    }}
                  >
                    <Group justify="space-between" align="center">
                      <Stack gap={2}>
                        <Text fw={700}>{task.title}</Text>
                        <Text size="xs" c="dimmed">
                          {task.assignee || "unassigned"} · {task.entity_key || "no-entity"} · {fmtDate(task.updated_at)}
                        </Text>
                      </Stack>
                      <Group gap={6}>
                        <Badge variant="light" color={statusColor(task.status)}>
                          {task.status}
                        </Badge>
                        <Badge variant="light">{task.priority}</Badge>
                      </Group>
                    </Group>
                  </Card>
                ))}
              </Stack>
            </ScrollArea>
          </Card>
        </Stack>

        <Card withBorder radius="lg">
          <Group justify="space-between" align="center" mb="sm">
            <Title order={5}>Task Detail</Title>
            {selectedTaskId ? <Code>{selectedTaskId}</Code> : <Badge color="gray">not selected</Badge>}
          </Group>
          {!selectedTaskId && <Text c="dimmed">Choose a task from queue.</Text>}
          {selectedTaskId && loadingDetail && (
            <Group justify="center" py="lg">
              <Loader size="sm" />
            </Group>
          )}
          {selectedTaskId && taskDetail && !loadingDetail && (
            <Stack gap="md">
              <Stack gap={2}>
                <Text fw={700}>{taskDetail.task.title}</Text>
                <Text size="sm" c="dimmed">
                  {taskDetail.task.description || "No description"}
                </Text>
              </Stack>
              <Group gap="xs">
                <Badge variant="light" color={statusColor(taskDetail.task.status)}>
                  {taskDetail.task.status}
                </Badge>
                <Badge variant="light">{taskDetail.task.priority}</Badge>
                <Badge variant="light">{taskDetail.task.source}</Badge>
                {taskDetail.task.due_at && <Badge variant="light">due {fmtDate(taskDetail.task.due_at)}</Badge>}
              </Group>

              <SimpleGrid cols={{ base: 2, md: 4 }} spacing="xs">
                <Button size="xs" variant="light" onClick={() => void transitionStatus("todo")} loading={runningAction}>
                  todo
                </Button>
                <Button size="xs" variant="light" onClick={() => void transitionStatus("in_progress")} loading={runningAction}>
                  in progress
                </Button>
                <Button size="xs" variant="light" color="orange" onClick={() => void transitionStatus("blocked")} loading={runningAction}>
                  blocked
                </Button>
                <Button size="xs" variant="light" color="green" onClick={() => void transitionStatus("done")} loading={runningAction}>
                  done
                </Button>
              </SimpleGrid>

              <Divider />

              <Title order={6}>Comment</Title>
              <Textarea value={comment} onChange={(event) => setComment(event.currentTarget.value)} minRows={2} />
              <Button size="xs" onClick={() => void addComment()} loading={runningAction}>
                Add Comment
              </Button>

              <Divider />

              <Title order={6}>Link Context</Title>
              <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
                <Select
                  label="Type"
                  value={linkForm.linkType}
                  onChange={(value) =>
                    setLinkForm((prev) => ({
                      ...prev,
                      linkType: (value as LinkFormState["linkType"] | null) ?? "draft",
                    }))
                  }
                  data={[
                    { label: "draft", value: "draft" },
                    { label: "claim", value: "claim" },
                    { label: "page", value: "page" },
                    { label: "event", value: "event" },
                    { label: "external", value: "external" },
                  ]}
                />
                <TextInput
                  label="Reference"
                  value={linkForm.linkRef}
                  onChange={(event) => setLinkForm((prev) => ({ ...prev, linkRef: event.currentTarget.value }))}
                  placeholder="uuid or url"
                />
              </SimpleGrid>
              <TextInput
                label="Note"
                value={linkForm.note}
                onChange={(event) => setLinkForm((prev) => ({ ...prev, note: event.currentTarget.value }))}
              />
              <Button size="xs" onClick={() => void addLink()} loading={runningAction}>
                Add Link
              </Button>

              <Divider />
              <Title order={6}>Links ({taskDetail.links.length})</Title>
              <ScrollArea h={120}>
                <Stack gap="xs">
                  {taskDetail.links.length === 0 && <Text c="dimmed">No linked context.</Text>}
                  {taskDetail.links.map((item) => (
                    <Card key={item.id} withBorder radius="md" p="xs">
                      <Group justify="space-between" align="start">
                        <Stack gap={2}>
                          <Text size="sm" fw={700}>
                            {item.link_type}
                          </Text>
                          <Code>{item.link_ref}</Code>
                          {item.note && (
                            <Text size="xs" c="dimmed">
                              {item.note}
                            </Text>
                          )}
                        </Stack>
                        <Text size="xs" c="dimmed">
                          {fmtDate(item.created_at)}
                        </Text>
                      </Group>
                    </Card>
                  ))}
                </Stack>
              </ScrollArea>

              <Title order={6}>Timeline ({taskDetail.events.length})</Title>
              <ScrollArea h={200}>
                <Stack gap="xs">
                  {taskDetail.events.length === 0 && <Text c="dimmed">No events.</Text>}
                  {taskDetail.events.map((event) => (
                    <Card key={event.id} withBorder radius="md" p="xs">
                      <Group justify="space-between" align="start">
                        <Stack gap={2}>
                          <Text size="sm" fw={700}>
                            {event.event_type}
                          </Text>
                          <Text size="xs" c="dimmed">
                            {event.actor || "system"}
                          </Text>
                          <Code block>{JSON.stringify(event.payload, null, 2)}</Code>
                        </Stack>
                        <Text size="xs" c="dimmed">
                          {fmtDate(event.created_at)}
                        </Text>
                      </Group>
                    </Card>
                  ))}
                </Stack>
              </ScrollArea>
            </Stack>
          )}
        </Card>
      </SimpleGrid>
    </Paper>
  );
}
