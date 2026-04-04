import { Anchor, Badge, Button, Divider, Group, Image, Kbd, Paper, Popover, ScrollArea, Stack, Text, TextInput, Title } from "@mantine/core";
import { RichTextEditor } from "@mantine/tiptap";
import Link from "@tiptap/extension-link";
import Table from "@tiptap/extension-table";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import TableRow from "@tiptap/extension-table-row";
import StarterKit from "@tiptap/starter-kit";
import { EditorContent, useEditor } from "@tiptap/react";
import { marked } from "marked";
import { useEffect, useMemo, useRef, useState } from "react";

type WikiPageCanvasProps = {
  title: string;
  slug: string | null;
  markdown: string;
  onApplyEditedStatement: (text: string) => void;
  readonly?: boolean;
  apiBaseUrl?: string;
};

type WikiEditorCommand = {
  id: string;
  label: string;
  description: string;
  keywords: string[];
  shortcut?: string;
  run: (args: { editor: NonNullable<ReturnType<typeof useEditor>> }) => void;
};

type WikiMediaItem = {
  url: string;
  alt: string;
  source: "markdown_image" | "linked_image";
};

type WikiAttachmentItem = {
  url: string;
  label: string;
  extension: string | null;
};

function markdownToHtml(markdown: string): string {
  const raw = marked.parse(markdown || "");
  return typeof raw === "string" ? raw : "";
}

function estimateReadingTimeMinutes(text: string): number {
  const words = text
    .replace(/[^\p{L}\p{N}\s'-]/gu, " ")
    .split(/\s+/)
    .filter(Boolean).length;
  if (words <= 0) return 0;
  return Math.max(1, Math.ceil(words / 220));
}

function normalizeMediaUrl(rawUrl: string): string | null {
  const value = String(rawUrl || "").trim();
  if (!value) return null;
  const unwrapped = value.replace(/^<|>$/g, "");
  const lowered = unwrapped.toLowerCase();
  if (lowered.startsWith("javascript:")) return null;
  if (
    lowered.startsWith("http://") ||
    lowered.startsWith("https://") ||
    lowered.startsWith("/") ||
    lowered.startsWith("data:image/") ||
    lowered.startsWith("blob:")
  ) {
    return unwrapped;
  }
  return null;
}

function isImageLikeUrl(url: string): boolean {
  const normalized = url.toLowerCase().split("?")[0].split("#")[0];
  return (
    normalized.startsWith("data:image/") ||
    [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif", ".bmp"].some((suffix) => normalized.endsWith(suffix))
  );
}

function extractFileExtension(url: string): string | null {
  const normalized = url.split("?")[0].split("#")[0];
  const pieces = normalized.split("/");
  const last = pieces[pieces.length - 1] || "";
  const idx = last.lastIndexOf(".");
  if (idx <= 0 || idx === last.length - 1) return null;
  return last.slice(idx + 1).toLowerCase();
}

function resolveMediaUrl(rawUrl: string, apiBaseUrl: string | null | undefined): string {
  const value = String(rawUrl || "").trim();
  if (!value) return "";
  const lowered = value.toLowerCase();
  if (lowered.startsWith("http://") || lowered.startsWith("https://") || lowered.startsWith("data:") || lowered.startsWith("blob:")) {
    return value;
  }
  if (value.startsWith("/")) {
    const root = String(apiBaseUrl || "").replace(/\/+$/, "");
    if (root) return `${root}${value}`;
  }
  return value;
}

export default function WikiPageCanvas({
  title,
  slug,
  markdown,
  onApplyEditedStatement,
  readonly = false,
  apiBaseUrl,
}: WikiPageCanvasProps) {
  const [editMode, setEditMode] = useState(false);
  const [seedVersion, setSeedVersion] = useState(0);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [commandSearch, setCommandSearch] = useState("");
  const commandInputRef = useRef<HTMLInputElement>(null);
  const sourceHtml = useMemo(() => markdownToHtml(markdown), [markdown]);
  const media = useMemo<WikiMediaItem[]>(() => {
    const imagePattern = /!\[([^\]]*)\]\(([^)]+)\)/g;
    const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
    const seen = new Set<string>();
    const items: WikiMediaItem[] = [];
    let match: RegExpExecArray | null = null;
    while ((match = imagePattern.exec(markdown)) !== null) {
      const normalized = normalizeMediaUrl(match[2] || "");
      if (!normalized || !isImageLikeUrl(normalized)) continue;
      const key = `img:${normalized.toLowerCase()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({
        url: normalized,
        alt: String(match[1] || "").trim() || "Image attachment",
        source: "markdown_image",
      });
    }
    while ((match = linkPattern.exec(markdown)) !== null) {
      const normalized = normalizeMediaUrl(match[2] || "");
      if (!normalized || !isImageLikeUrl(normalized)) continue;
      const key = `img:${normalized.toLowerCase()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({
        url: normalized,
        alt: String(match[1] || "").trim() || "Linked image",
        source: "linked_image",
      });
    }
    return items.slice(0, 12);
  }, [markdown]);
  const attachments = useMemo<WikiAttachmentItem[]>(() => {
    const linkPattern = /\[([^\]]+)\]\(([^)]+)\)/g;
    const seen = new Set<string>();
    const items: WikiAttachmentItem[] = [];
    let match: RegExpExecArray | null = null;
    while ((match = linkPattern.exec(markdown)) !== null) {
      const normalized = normalizeMediaUrl(match[2] || "");
      if (!normalized) continue;
      if (isImageLikeUrl(normalized)) continue;
      const key = normalized.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({
        url: normalized,
        label: String(match[1] || "").trim() || normalized,
        extension: extractFileExtension(normalized),
      });
    }
    return items.slice(0, 20);
  }, [markdown]);
  const plainText = useMemo(
    () =>
      markdown
        .replace(/`{1,3}[^`]*`{1,3}/g, " ")
        .replace(/[#>*_[\]()!-]/g, " ")
        .replace(/\s+/g, " ")
        .trim(),
    [markdown],
  );
  const wordCount = useMemo(() => (plainText ? plainText.split(/\s+/).filter(Boolean).length : 0), [plainText]);
  const readingMinutes = useMemo(() => estimateReadingTimeMinutes(plainText), [plainText]);
  const editor = useEditor({
    extensions: [
      StarterKit,
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
      Link.configure({
        openOnClick: true,
      }),
    ],
    content: sourceHtml,
    editable: editMode,
    immediatelyRender: false,
  });

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!readonly && editMode);
  }, [editMode, editor, readonly]);

  useEffect(() => {
    if (!editor) return;
    editor.commands.setContent(sourceHtml || "<p></p>", false);
    setSeedVersion((value) => value + 1);
  }, [editor, sourceHtml]);

  useEffect(() => {
    if (!editor || readonly) return;
    const focusCommandInput = () => {
      window.requestAnimationFrame(() => {
        commandInputRef.current?.focus();
      });
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (!editMode) return;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          editor.chain().focus().redo().run();
        } else {
          editor.chain().focus().undo().run();
        }
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "/") {
        event.preventDefault();
        setCommandSearch("");
        setCommandPaletteOpen(true);
        focusCommandInput();
        return;
      }
      if (!event.metaKey && !event.ctrlKey && event.key === "/" && editMode) {
        const selection = editor.state.selection;
        if (selection.empty) {
          const anchor = selection.from;
          const prevChar = editor.state.doc.textBetween(Math.max(0, anchor - 1), anchor, "\n", " ");
          if (!prevChar || /\s/.test(prevChar)) {
            event.preventDefault();
            setCommandSearch("");
            setCommandPaletteOpen(true);
            focusCommandInput();
            return;
          }
        }
        return;
      }
      if (event.shiftKey && event.key.toLowerCase() === "i") {
        event.preventDefault();
        editor.chain().focus().insertContent('<blockquote><p><strong>Info:</strong> </p></blockquote>').run();
        return;
      }
      if (event.shiftKey && event.key.toLowerCase() === "w") {
        event.preventDefault();
        editor.chain().focus().insertContent('<blockquote><p><strong>Warning:</strong> </p></blockquote>').run();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editMode, editor, readonly]);

  const commands = useMemo<WikiEditorCommand[]>(
    () => [
      {
        id: "heading-2",
        label: "Heading 2",
        description: "Section title for policy or runbook blocks.",
        keywords: ["heading", "section", "h2", "title"],
        run: ({ editor: target }) => {
          target.chain().focus().toggleHeading({ level: 2 }).run();
        },
      },
      {
        id: "callout-info",
        label: "Callout: Info",
        description: "Insert informational callout block.",
        keywords: ["callout", "info", "note", "block"],
        shortcut: "Ctrl/Cmd+Shift+I",
        run: ({ editor: target }) => {
          target.chain().focus().insertContent('<blockquote><p><strong>Info:</strong> </p></blockquote>').run();
        },
      },
      {
        id: "callout-warning",
        label: "Callout: Warning",
        description: "Insert warning callout block.",
        keywords: ["callout", "warning", "risk", "alert"],
        shortcut: "Ctrl/Cmd+Shift+W",
        run: ({ editor: target }) => {
          target.chain().focus().insertContent('<blockquote><p><strong>Warning:</strong> </p></blockquote>').run();
        },
      },
      {
        id: "incident-template",
        label: "Incident Template",
        description: "Insert standard incident status section.",
        keywords: ["incident", "ops", "template", "status"],
        run: ({ editor: target }) => {
          target
            .chain()
            .focus()
            .insertContent(
              "<h2>Operations Incident</h2><ul><li>Status: active</li><li>Impact:</li><li>Mitigation:</li><li>ETA:</li></ul>",
            )
            .run();
        },
      },
      {
        id: "decision-template",
        label: "Decision Log Entry",
        description: "Insert ADR-like decision entry.",
        keywords: ["decision", "adr", "log", "template"],
        run: ({ editor: target }) => {
          target
            .chain()
            .focus()
            .insertContent(
              "<h2>Decision Log</h2><ul><li>Context:</li><li>Decision:</li><li>Alternatives considered:</li><li>Owner:</li></ul>",
            )
            .run();
        },
      },
      {
        id: "table-3x3",
        label: "Table 3 x 3",
        description: "Insert comparison/summary table.",
        keywords: ["table", "matrix", "grid", "compare"],
        run: ({ editor: target }) => {
          target.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
        },
      },
      {
        id: "table-add-row",
        label: "Table: Add Row",
        description: "Add row below current table row.",
        keywords: ["table", "row", "append"],
        run: ({ editor: target }) => {
          target.chain().focus().addRowAfter().run();
        },
      },
      {
        id: "table-add-column",
        label: "Table: Add Column",
        description: "Add column after current cell.",
        keywords: ["table", "column", "append"],
        run: ({ editor: target }) => {
          target.chain().focus().addColumnAfter().run();
        },
      },
      {
        id: "table-delete",
        label: "Table: Delete Current",
        description: "Remove the active table.",
        keywords: ["table", "delete", "remove"],
        run: ({ editor: target }) => {
          target.chain().focus().deleteTable().run();
        },
      },
      {
        id: "media-image-template",
        label: "Media: Image Embed",
        description: "Insert markdown image template.",
        keywords: ["media", "image", "attachment", "embed"],
        run: ({ editor: target }) => {
          target.chain().focus().insertContent("<p>![Image description](https://example.com/image.png)</p>").run();
        },
      },
      {
        id: "media-file-template",
        label: "Media: File Link",
        description: "Insert markdown attachment link template.",
        keywords: ["media", "file", "pdf", "attachment", "link"],
        run: ({ editor: target }) => {
          target.chain().focus().insertContent("<p>[Runbook PDF](https://example.com/runbook.pdf)</p>").run();
        },
      },
    ],
    [],
  );

  const filteredCommands = useMemo(() => {
    const needle = commandSearch.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((command) => {
      const hay = `${command.label} ${command.description} ${command.keywords.join(" ")}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [commandSearch, commands]);

  const commandById = useMemo(() => {
    const map = new Map<string, WikiEditorCommand>();
    commands.forEach((command) => map.set(command.id, command));
    return map;
  }, [commands]);

  const runCommand = (id: string) => {
    if (!editor) return;
    const command = commandById.get(id);
    if (!command) return;
    command.run({ editor });
  };

  return (
    <Paper withBorder p="md" radius="md" className="wiki-canvas-card">
      <Group justify="space-between" align="flex-start" mb="sm">
        <Stack gap={2}>
          <Title order={6}>Page</Title>
          <Text size="xs" c="dimmed">
            {slug ? `${title} (${slug})` : title}
          </Text>
          <Group gap={6}>
            <Badge variant="light" color="violet">
              {wordCount} words
            </Badge>
            <Badge variant="light" color="indigo">
              {readingMinutes > 0 ? `~${readingMinutes} min read` : "no text"}
            </Badge>
          </Group>
        </Stack>
        <Group gap="xs">
          <Badge variant="light" color={readonly ? "indigo" : editMode ? "orange" : "teal"}>
            {readonly ? "wiki preview" : editMode ? "edit mode" : "read mode"}
          </Badge>
          {!readonly && (
            <Button size="xs" variant="light" onClick={() => setEditMode((value) => !value)}>
              {editMode ? "Switch to read" : "Switch to edit"}
            </Button>
          )}
        </Group>
      </Group>

      {editor && (
        <RichTextEditor editor={editor} className="wiki-canvas-content">
          {!readonly && editMode && (
            <>
              <Group justify="space-between" align="center" mb="xs">
                <Group gap={6} wrap="wrap">
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    color="gray"
                    onClick={() => editor.chain().focus().undo().run()}
                    disabled={!editor.can().chain().focus().undo().run()}
                  >
                    Undo
                  </Button>
                  <Button
                    size="compact-xs"
                    variant="subtle"
                    color="gray"
                    onClick={() => editor.chain().focus().redo().run()}
                    disabled={!editor.can().chain().focus().redo().run()}
                  >
                    Redo
                  </Button>
                  <Button size="compact-xs" variant="light" color="blue" onClick={() => runCommand("callout-info")}>
                    Info callout
                  </Button>
                  <Button size="compact-xs" variant="light" color="orange" onClick={() => runCommand("callout-warning")}>
                    Warning callout
                  </Button>
                  <Button size="compact-xs" variant="light" color="grape" onClick={() => runCommand("table-3x3")}>
                    Insert table
                  </Button>
                  <Button size="compact-xs" variant="subtle" color="grape" onClick={() => runCommand("table-add-row")}>
                    Add row
                  </Button>
                  <Button size="compact-xs" variant="subtle" color="grape" onClick={() => runCommand("table-add-column")}>
                    Add column
                  </Button>
                  <Button size="compact-xs" variant="subtle" color="red" onClick={() => runCommand("table-delete")}>
                    Delete table
                  </Button>
                  <Button size="compact-xs" variant="subtle" color="indigo" onClick={() => runCommand("media-image-template")}>
                    Image link
                  </Button>
                  <Button size="compact-xs" variant="subtle" color="indigo" onClick={() => runCommand("media-file-template")}>
                    File link
                  </Button>
                  <Button size="compact-xs" variant="subtle" color="gray" onClick={() => setCommandPaletteOpen(true)}>
                    Slash commands
                  </Button>
                </Group>
                <Text size="xs" c="dimmed">
                  Start line with <Kbd>/</Kbd> or use <Kbd>Ctrl/Cmd</Kbd> + <Kbd>/</Kbd>
                </Text>
              </Group>
              <Popover
                opened={commandPaletteOpen}
                onChange={setCommandPaletteOpen}
                width={440}
                position="bottom-start"
                withArrow
                shadow="md"
              >
                <Popover.Target>
                  <TextInput
                    ref={commandInputRef}
                    size="xs"
                    value={commandSearch}
                    onChange={(event) => setCommandSearch(event.currentTarget.value)}
                    onFocus={() => setCommandPaletteOpen(true)}
                    placeholder="Type command: table, callout, incident..."
                    label="Command Palette"
                  />
                </Popover.Target>
                <Popover.Dropdown>
                  <ScrollArea.Autosize mah={240}>
                    <Stack gap={4}>
                      {filteredCommands.length === 0 ? (
                        <Text size="xs" c="dimmed">
                          No commands match this query.
                        </Text>
                      ) : (
                        filteredCommands.map((command) => (
                          <Button
                            key={command.id}
                            variant="subtle"
                            justify="space-between"
                            fullWidth
                            onClick={() => {
                              command.run({ editor });
                              setCommandPaletteOpen(false);
                              setCommandSearch("");
                            }}
                          >
                            <Stack gap={0} align="flex-start">
                              <Text size="xs" fw={700}>
                                {command.label}
                              </Text>
                              <Text size="xs" c="dimmed">
                                {command.description}
                              </Text>
                            </Stack>
                            {command.shortcut ? (
                              <Text size="xs" c="dimmed">
                                {command.shortcut}
                              </Text>
                            ) : null}
                          </Button>
                        ))
                      )}
                    </Stack>
                  </ScrollArea.Autosize>
                </Popover.Dropdown>
              </Popover>
              <Divider my="xs" />
              <RichTextEditor.Toolbar sticky stickyOffset={56}>
                <RichTextEditor.ControlsGroup>
                  <RichTextEditor.Undo />
                  <RichTextEditor.Redo />
                </RichTextEditor.ControlsGroup>
                <RichTextEditor.ControlsGroup>
                  <RichTextEditor.Bold />
                  <RichTextEditor.Italic />
                  <RichTextEditor.Underline />
                  <RichTextEditor.Strikethrough />
                  <RichTextEditor.Code />
                </RichTextEditor.ControlsGroup>
                <RichTextEditor.ControlsGroup>
                  <RichTextEditor.H1 />
                  <RichTextEditor.H2 />
                  <RichTextEditor.H3 />
                  <RichTextEditor.Blockquote />
                  <RichTextEditor.Hr />
                </RichTextEditor.ControlsGroup>
                <RichTextEditor.ControlsGroup>
                  <RichTextEditor.BulletList />
                  <RichTextEditor.OrderedList />
                  <RichTextEditor.Link />
                  <RichTextEditor.Unlink />
                </RichTextEditor.ControlsGroup>
              </RichTextEditor.Toolbar>
            </>
          )}
          <EditorContent editor={editor} key={`wiki-canvas-${seedVersion}`} />
        </RichTextEditor>
      )}

      {(media.length > 0 || attachments.length > 0) && (
        <Paper withBorder p="sm" radius="md" mt="sm" className="wiki-media-preview-card">
          <Stack gap="xs">
            <Group justify="space-between" align="center">
              <Text size="xs" fw={700}>
                Attachments & Media
              </Text>
              <Group gap={6}>
                <Badge size="xs" variant="light" color="indigo">
                  images {media.length}
                </Badge>
                <Badge size="xs" variant="light" color="gray">
                  files {attachments.length}
                </Badge>
              </Group>
            </Group>

            {media.length > 0 && (
              <div className="wiki-media-grid">
                {media.map((item) => (
                  <Paper key={`wiki-media-${item.url}`} withBorder p={6} radius="sm" className="wiki-media-card">
                    <Stack gap={6}>
                      <Image src={resolveMediaUrl(item.url, apiBaseUrl)} alt={item.alt} radius="sm" h={120} fit="cover" />
                      <Text size="xs" lineClamp={2} c="dimmed">
                        {item.alt}
                      </Text>
                      <Anchor href={resolveMediaUrl(item.url, apiBaseUrl)} target="_blank" rel="noreferrer" size="xs">
                        Open
                      </Anchor>
                    </Stack>
                  </Paper>
                ))}
              </div>
            )}

            {attachments.length > 0 && (
              <Stack gap={4}>
                {attachments.map((item) => (
                  <Group key={`wiki-attachment-${item.url}`} justify="space-between" align="center" wrap="nowrap">
                    <Stack gap={0} style={{ flex: 1 }}>
                      <Text size="xs" fw={600} lineClamp={1}>
                        {item.label}
                      </Text>
                      <Text size="xs" c="dimmed" lineClamp={1}>
                        {item.url}
                      </Text>
                    </Stack>
                    <Group gap={6} wrap="nowrap">
                      {item.extension ? (
                        <Badge size="xs" variant="outline" color="gray">
                          {item.extension}
                        </Badge>
                      ) : null}
                      <Anchor href={resolveMediaUrl(item.url, apiBaseUrl)} target="_blank" rel="noreferrer" size="xs">
                        Open
                      </Anchor>
                    </Group>
                  </Group>
                ))}
              </Stack>
            )}
          </Stack>
        </Paper>
      )}

      {!readonly && (
        <Group mt="sm" justify="space-between" align="center">
          <Text size="xs" c="dimmed">
            Use edit mode to prepare corrected statement text and pass it to moderation.
          </Text>
          <Button
            size="xs"
            onClick={() => {
              if (!editor) return;
              const text = editor.getText({ blockSeparator: "\n" }).trim();
              if (!text) return;
              onApplyEditedStatement(text);
            }}
          >
            Apply text to Approve form
          </Button>
        </Group>
      )}
    </Paper>
  );
}
